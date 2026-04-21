import streamlit as st
import ezdxf
from ezdxf import path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon, MultiLineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import rotate, translate
import io
import svgelements

st.set_page_config(page_title="True Nesting - Auto Sheet Size", layout="wide")

# ---------------- ENGINE ----------------
class TrueNester:

    def __init__(self, gap=3.0, margin=5.0):
        self.gap = gap
        self.margin = margin

    # -------- FILE READERS --------
    def extract_from_svg(self, file):
        svg = svgelements.SVG.parse(io.StringIO(file.getvalue().decode()))
        polys = []

        for e in svg.elements():
            if isinstance(e, svgelements.Path):
                pts = [(p.x, p.y) for p in e.as_points()]
                if len(pts) > 2:
                    poly = Polygon(pts)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if poly.area > 1:
                        polys.append(translate(poly, -poly.bounds[0], -poly.bounds[1]))
        return polys

    def extract_from_dxf(self, file):
        doc = ezdxf.read(io.BytesIO(file.getvalue()))
        msp = doc.modelspace()
        segs = []

        for e in msp:
            try:
                for p in path.make_paths(e):
                    v = list(p.flattening(0.1))
                    for i in range(len(v)-1):
                        segs.append([(v[i].x, v[i].y), (v[i+1].x, v[i+1].y)])
            except:
                pass

        merged = unary_union(MultiLineString(segs))
        healed = merged.buffer(0.02).buffer(-0.02)
        polys = list(polygonize(healed))

        return [translate(p, -p.bounds[0], -p.bounds[1]) for p in polys if p.area > 1]

    # -------- TRUE NEST --------
    def nest_and_minimize(self, parts):

        parts = sorted(parts, key=lambda p: p.area, reverse=True)
        parts = [p.buffer(self.gap/2) for p in parts]

        placed = []

        # BIG virtual sheet
        LIMIT = 10000

        for part in parts:
            placed_flag = False

            for angle in [0, 90]:
                if placed_flag:
                    break

                r = rotate(part, angle, origin='centroid')
                minx, miny, maxx, maxy = r.bounds
                r = translate(r, -minx, -miny)

                w, h = maxx-minx, maxy-miny
                step = max(10, int(min(w,h)/3))

                for y in range(int(self.margin), LIMIT, step):
                    for x in range(int(self.margin), LIMIT, step):

                        trial = translate(r, x, y)

                        if not any(trial.intersects(p) for p in placed):
                            placed.append(trial)
                            placed_flag = True
                            break

                    if placed_flag:
                        break

            if not placed_flag:
                placed.append(r)

        # -------- BOUNDING BOX --------
        union = unary_union(placed)
        minx, miny, maxx, maxy = union.bounds

        width = maxx + self.margin
        height = maxy + self.margin

        total_part_area = sum(p.area for p in parts)
        sheet_area = width * height

        utilization = (total_part_area / sheet_area) * 100

        return width, height, placed, utilization


# ---------------- UI ----------------
st.title("⚙️ ProNester – Minimum Sheet Size Finder")

with st.sidebar:
    GAP = st.slider("Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Margin (mm)", 0.0, 20.0, 5.0)

    files = st.file_uploader("Upload DXF / SVG", type=["dxf","svg"], accept_multiple_files=True)

if files:
    engine = TrueNester(GAP, MARGIN)
    parts = []

    st.subheader("Set Quantity")

    for f in files:
        shapes = engine.extract_from_svg(f) if f.name.endswith(".svg") else engine.extract_from_dxf(f)

        if shapes:
            c1, c2 = st.columns([3,1])
            c1.write(f"✅ {f.name}")
            qty = c2.number_input("Qty", 1, 100, 1, key=f.name)

            for _ in range(qty):
                parts.extend(shapes)

    if st.button("🚀 Find Minimum Sheet Size"):

        with st.spinner("Performing true nesting..."):
            W, H, layout, util = engine.nest_and_minimize(parts)

        st.success(f"""
        📐 Minimum Required Sheet Size: **{W:.0f} x {H:.0f} mm**  
        📊 Utilization: **{util:.2f}%**
        """)

        # -------- PLOT --------
        fig, ax = plt.subplots(figsize=(12,6))
        ax.set_aspect('equal')

        ax.add_patch(patches.Rectangle((0,0), W, H, fill=False))

        for poly in layout:
            x,y = poly.exterior.xy
            ax.fill(x, y, alpha=0.5)

        st.pyplot(fig)

        # -------- DXF EXPORT --------
        doc = ezdxf.new()
        msp = doc.modelspace()

        for poly in layout:
            msp.add_lwpolyline(list(poly.exterior.coords))

        dxf_io = io.StringIO()
        doc.write(dxf_io)

        st.download_button("📥 Download Nested DXF", dxf_io.getvalue(), "nested_output.dxf")

else:
    st.info("Upload files to begin")
