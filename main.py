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

st.set_page_config(page_title="ProNester Industrial", layout="wide")

# ---------------- ENGINE ----------------
class ProNester:

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

    # ---------- ROTATIONS ----------
    def generate_rotations(self, part):
        angles = [0, 90, 180, 270]
        result = []

        for a in angles:
            r = rotate(part, a, origin='centroid')
            minx, miny, maxx, maxy = r.bounds
            r = translate(r, -minx, -miny)
            result.append(r)

        return result

    # ---------- CANDIDATE POINTS ----------
    def get_candidates(self, placed):
        pts = [(self.margin, self.margin)]

        for p in placed:
            minx, miny, maxx, maxy = p.bounds
            pts.append((maxx, miny))
            pts.append((minx, maxy))

        return pts

    # ---------- PLACEMENT ----------
    def place_part(self, part, placed):

        best = None
        best_y = float('inf')
        best_x = float('inf')

        rotations = self.generate_rotations(part)
        candidates = self.get_candidates(placed)

        for r in rotations:
            for cx, cy in candidates:

                trial = translate(r, cx, cy)

                if any(trial.intersects(p) for p in placed):
                    continue

                tx, ty = trial.bounds[0], trial.bounds[1]

                if ty < best_y or (ty == best_y and tx < best_x):
                    best = trial
                    best_y = ty
                    best_x = tx

        return best

    # ---------- NEST ----------
    def nest(self, parts):

        parts = sorted(parts, key=lambda p: p.area, reverse=True)
        parts = [p.buffer(self.gap / 2) for p in parts]

        placed = []

        for part in parts:
            pos = self.place_part(part, placed)

            if pos:
                placed.append(pos)
            else:
                placed.append(translate(part, self.margin, self.margin))

        union = unary_union(placed)
        minx, miny, maxx, maxy = union.bounds

        W = maxx + self.margin
        H = maxy + self.margin

        total_area = sum(p.area for p in parts)
        util = (total_area / (W * H)) * 100

        return W, H, placed, util


# ---------- METRICS ----------
def calculate_metrics(parts, W, H, density, thickness, cost_per_kg, scrap_rate):

    part_area = sum(p.area for p in parts) / 1e6
    sheet_area = (W * H) / 1e6

    thickness_m = thickness / 1000

    part_weight = part_area * thickness_m * density
    sheet_weight = sheet_area * thickness_m * density

    scrap_weight = sheet_weight - part_weight

    total_cost = sheet_weight * cost_per_kg
    used_cost = part_weight * cost_per_kg
    scrap_value = scrap_weight * scrap_rate

    scrap_percent = (sheet_area - part_area) / sheet_area * 100

    return {
        "part_weight": part_weight,
        "sheet_weight": sheet_weight,
        "scrap_weight": scrap_weight,
        "total_cost": total_cost,
        "used_cost": used_cost,
        "scrap_value": scrap_value,
        "scrap_percent": scrap_percent
    }


# ---------------- UI ----------------
st.title("⚙️ ProNester – Smart Nesting + Costing")

with st.sidebar:
    st.header("Settings")

    GAP = st.slider("Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Margin (mm)", 0.0, 20.0, 5.0)

    st.header("Material")

    density = st.number_input("Density (kg/m³)", value=7850)
    thickness = st.number_input("Thickness (mm)", value=2.0)
    cost_per_kg = st.number_input("Cost (₹/kg)", value=70.0)
    scrap_rate = st.number_input("Scrap Value (₹/kg)", value=25.0)

    files = st.file_uploader("Upload DXF / SVG", type=["dxf", "svg"], accept_multiple_files=True)

if files:
    engine = ProNester(GAP, MARGIN)
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

    if st.button("🚀 Run Nesting"):

        with st.spinner("Nesting in progress..."):
            W, H, layout, util = engine.nest(parts)

        metrics = calculate_metrics(parts, W, H, density, thickness, cost_per_kg, scrap_rate)

        st.success(f"""
        📐 Sheet Size: **{W:.0f} x {H:.0f} mm**  
        📊 Utilization: **{util:.2f}%**
        """)

        # -------- METRICS --------
        st.subheader("📊 Production Metrics")

        c1, c2, c3 = st.columns(3)

        c1.metric("Part Weight (kg)", f"{metrics['part_weight']:.2f}")
        c1.metric("Sheet Weight (kg)", f"{metrics['sheet_weight']:.2f}")

        c2.metric("Material Cost (₹)", f"{metrics['total_cost']:.0f}")
        c2.metric("Used Cost (₹)", f"{metrics['used_cost']:.0f}")

        c3.metric("Scrap %", f"{metrics['scrap_percent']:.2f}%")
        c3.metric("Scrap Value (₹)", f"{metrics['scrap_value']:.0f}")

        # -------- VISUAL --------
        fig, ax = plt.subplots(figsize=(12,6))
        ax.set_aspect('equal')

        ax.add_patch(patches.Rectangle((0,0), W, H, fill=False))

        for poly in layout:
            x,y = poly.exterior.xy
            ax.fill(x, y, alpha=0.5)

        st.pyplot(fig)

        # -------- DXF --------
        doc = ezdxf.new()
        msp = doc.modelspace()

        for poly in layout:
            msp.add_lwpolyline(list(poly.exterior.coords))

        dxf_io = io.StringIO()
        doc.write(dxf_io)

        st.download_button("📥 Download DXF", dxf_io.getvalue(), "nest_output.dxf")

else:
    st.info("Upload DXF or SVG files to start.")
