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

st.set_page_config(page_title="ProNester Smart Planner", layout="wide")

# -------- ENGINE --------
class SmartNester:

    def __init__(self, gap=3.0, margin=5.0):
        self.gap = gap
        self.margin = margin

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

    def nest_on_sheet(self, parts, W, H):
        sheets = [[]]
        parts = sorted(parts, key=lambda p: p.area, reverse=True)
        parts = [p.buffer(self.gap/2) for p in parts]

        for part in parts:
            placed = False

            for angle in [0, 90]:
                if placed: break

                r = rotate(part, angle, origin='centroid')
                minx, miny, maxx, maxy = r.bounds
                r = translate(r, -minx, -miny)

                w, h = maxx-minx, maxy-miny
                step = max(10, int(min(w,h)/3))

                for sid, sheet in enumerate(sheets):
                    for y in range(int(self.margin), int(H-h-self.margin), step):
                        for x in range(int(self.margin), int(W-w-self.margin), step):

                            trial = translate(r, x, y)

                            if not any(trial.intersects(p) for p in sheet):
                                sheets[sid].append(trial)
                                placed = True
                                break
                        if placed: break
                    if placed: break

            if not placed:
                sheets.append([translate(part, self.margin, self.margin)])

        total_area = sum(p.area for p in parts)
        total_sheet_area = len(sheets) * W * H
        utilization = (total_area / total_sheet_area) * 100

        return sheets, utilization

    def optimize_standard_sheets(self, parts):

        standard_sizes = [
            (2500,1250),
            (3000,1500),
            (2000,1000),
            (1500,3000)
        ]

        best = None

        for W, H in standard_sizes:

            sheets, util = self.nest_on_sheet(parts, W, H)

            result = {
                "W": W,
                "H": H,
                "sheets": len(sheets),
                "util": util,
                "layouts": sheets
            }

            if best is None:
                best = result
            else:
                # priority: fewer sheets, then higher utilization
                if result["sheets"] < best["sheets"] or (
                    result["sheets"] == best["sheets"] and result["util"] > best["util"]
                ):
                    best = result

        return best

# -------- UI --------
st.title("⚙️ ProNester – Smart Sheet Optimizer")

with st.sidebar:
    GAP = st.slider("Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Margin (mm)", 0.0, 20.0, 5.0)

    files = st.file_uploader("Upload DXF/SVG", type=["dxf","svg"], accept_multiple_files=True)

if files:
    engine = SmartNester(GAP, MARGIN)
    parts = []

    st.subheader("Set Quantity")

    for f in files:
        shapes = engine.extract_from_svg(f) if f.name.endswith(".svg") else engine.extract_from_dxf(f)

        if shapes:
            c1,c2 = st.columns([3,1])
            c1.write(f"✅ {f.name}")
            qty = c2.number_input("Qty",1,100,1,key=f.name)

            for _ in range(qty):
                parts.extend(shapes)

    if st.button("🚀 Optimize Sheet Selection"):

        with st.spinner("Finding best sheet size..."):
            best = engine.optimize_standard_sheets(parts)

        st.success(
            f"""
            🏆 Best Sheet Size: **{best['W']} x {best['H']} mm**  
            📄 Sheets Required: **{best['sheets']}**  
            📊 Utilization: **{best['util']:.2f}%**
            """
        )

        fig, ax = plt.subplots(figsize=(12,6))
        ax.set_aspect('equal')

        for i, sheet in enumerate(best["layouts"]):
            offset = i * (best["W"] + 200)

            ax.add_patch(patches.Rectangle((offset,0), best["W"], best["H"], fill=False))

            for poly in sheet:
                x,y = poly.exterior.xy
                ax.fill([px+offset for px in x], y, alpha=0.5)

        st.pyplot(fig)

else:
    st.info("Upload files to begin")
