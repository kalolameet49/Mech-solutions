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

st.set_page_config(page_title="ProNester NFP Engine", layout="wide")

# ---------------- ENGINE ----------------
class NFPNester:

    def __init__(self, gap=3.0, margin=5.0):
        self.gap = gap
        self.margin = margin

    # ---------- FILE READ ----------
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

    # ---------- APPROX NFP ----------
    def create_nfp_region(self, placed_parts):
        """
        Create forbidden region using buffered union (approx Minkowski sum)
        """
        if not placed_parts:
            return None
        return unary_union([p.buffer(self.gap) for p in placed_parts])

    # ---------- PLACEMENT ----------
    def place_part_nfp(self, part, placed_parts):
        """
        Bottom-left placement using NFP approximation
        """
        nfp_region = self.create_nfp_region(placed_parts)

        LIMIT = 5000
        step = max(5, int(min(part.bounds[2]-part.bounds[0],
                              part.bounds[3]-part.bounds[1]) / 4))

        best_pos = None

        for y in range(int(self.margin), LIMIT, step):
            for x in range(int(self.margin), LIMIT, step):

                trial = translate(part, x, y)

                if nfp_region:
                    if trial.intersects(nfp_region):
                        continue

                best_pos = trial
                return best_pos

        return None

    # ---------- MAIN NEST ----------
    def nest_nfp(self, parts):

        parts = sorted(parts, key=lambda p: p.area, reverse=True)
        parts = [p.buffer(self.gap/2) for p in parts]

        placed = []

        for part in parts:

            placed_flag = False

            for angle in [0, 90]:
                r = rotate(part, angle, origin='centroid')
                minx, miny, maxx, maxy = r.bounds
                r = translate(r, -minx, -miny)

                pos = self.place_part_nfp(r, placed)

                if pos:
                    placed.append(pos)
                    placed_flag = True
                    break

            if not placed_flag:
                # fallback
                placed.append(translate(r, self.margin, self.margin))

        # ---------- BOUNDING ----------
        union = unary_union(placed)
        minx, miny, maxx, maxy = union.bounds

        W = maxx + self.margin
        H = maxy + self.margin

        total_area = sum(p.area for p in parts)
        util = (total_area / (W * H)) * 100

        return W, H, placed, util


# ---------------- UI ----------------
st.title("⚙️ ProNester – NFP Based Nesting")

with st.sidebar:
    GAP = st.slider("Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Margin (mm)", 0.0, 20.0, 5.0)

    files = st.file_uploader("Upload DXF / SVG", type=["dxf","svg"], accept_multiple_files=True)

if files:
    engine = NFPNester(GAP, MARGIN)
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

    if st.button("🚀 Run NFP Nesting"):

        with st.spinner("Running NFP nesting..."):
            W, H, layout, util = engine.nest_nfp(parts)

        st.success(f"""
        📐 Minimum Sheet Size: **{W:.0f} x {H:.0f} mm**  
        📊 Utilization: **{util:.2f}%**
        """)

        fig, ax = plt.subplots(figsize=(12,6))
        ax.set_aspect('equal')

        ax.add_patch(patches.Rectangle((0,0), W, H, fill=False))

        for poly in layout:
            x,y = poly.exterior.xy
            ax.fill(x, y, alpha=0.5)

        st.pyplot(fig)

        # DXF Export
        doc = ezdxf.new()
        msp = doc.modelspace()

        for poly in layout:
            msp.add_lwpolyline(list(poly.exterior.coords))

        dxf_io = io.StringIO()
        doc.write(dxf_io)

        st.download_button("📥 Download DXF", dxf_io.getvalue(), "nfp_output.dxf")

else:
    st.info("Upload files to begin")
