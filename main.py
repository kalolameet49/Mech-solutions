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
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET
import uuid

st.set_page_config(page_title="ProNester Industrial", layout="wide")

# ---------------- SESSION ----------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ---------------- ENGINE ----------------
class ProNester:

    def __init__(self, gap=3.0, margin=5.0):
        self.gap = gap
        self.margin = margin

    def generate_rotations(self, part):
        angles = [0, 90, 180, 270]
        result = []
        for a in angles:
            r = rotate(part, a, origin='centroid')
            minx, miny, maxx, maxy = r.bounds
            result.append(translate(r, -minx, -miny))
        return result

    def get_candidates(self, placed):
        pts = [(self.margin, self.margin)]
        for p in placed:
            minx, miny, maxx, maxy = p.bounds
            pts.append((maxx, miny))
            pts.append((minx, maxy))
        return pts

    def place_part(self, part, placed):
        best = None
        best_y, best_x = float('inf'), float('inf')

        for r in self.generate_rotations(part):
            for cx, cy in self.get_candidates(placed):
                trial = translate(r, cx, cy)

                if placed and trial.intersects(unary_union(placed)):
                    continue

                tx, ty = trial.bounds[0], trial.bounds[1]

                if ty < best_y or (ty == best_y and tx < best_x):
                    best, best_y, best_x = trial, ty, tx

        return best

    def nest(self, parts):
        parts = sorted(parts, key=lambda p: p.area, reverse=True)
        parts = [p.buffer(self.gap / 2) for p in parts]

        placed = []
        for part in parts:
            pos = self.place_part(part, placed)
            placed.append(pos if pos else translate(part, self.margin, self.margin))

        union = unary_union(placed)
        _, _, maxx, maxy = union.bounds

        W = maxx + self.margin
        H = maxy + self.margin

        util = (sum(p.area for p in parts) / (W * H)) * 100
        return W, H, placed, util


# ---------------- CACHED FILE READ ----------------
@st.cache_data(show_spinner=False)
def extract_svg(file_bytes):
    svg = svgelements.SVG.parse(io.StringIO(file_bytes.decode()))
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


@st.cache_data(show_spinner=False)
def extract_dxf(file_bytes):
    doc = ezdxf.read(io.BytesIO(file_bytes))
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


# ---------------- DEEPNEST ----------------
DEEPNEST_CMD = ["deepnest"]  # change if needed

def run_deepnest(svg_text):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, "input.svg")
            out = os.path.join(tmp, "output.svg")

            with open(inp, "w") as f:
                f.write(svg_text)

            cmd = DEEPNEST_CMD + [inp, "-o", out, "--rotations", "8", "--spacing", "3"]
            subprocess.run(cmd, check=True)

            with open(out, "r") as f:
                return f.read()

    except Exception as e:
        st.error(f"Deepnest error: {e}")
        return None


def polygons_to_svg(polys):
    svg = ['<svg xmlns="http://www.w3.org/2000/svg">']
    for p in polys:
        coords = " ".join([f"{x},{y}" for x, y in p.exterior.coords])
        svg.append(f'<polygon points="{coords}" fill="none" stroke="black"/>')
    svg.append("</svg>")
    return "\n".join(svg)


def parse_svg(svg_text):
    root = ET.fromstring(svg_text)
    polys = []

    for elem in root.findall(".//{http://www.w3.org/2000/svg}polygon"):
        pts = elem.attrib["points"].split()
        coords = [(float(p.split(",")[0]), float(p.split(",")[1])) for p in pts]
        polys.append(Polygon(coords))

    return polys


# ---------------- METRICS ----------------
def calculate_metrics(parts, W, H, density, thickness, cost, scrap_rate):
    part_area = sum(p.area for p in parts) / 1e6
    sheet_area = (W * H) / 1e6

    t = thickness / 1000

    part_weight = part_area * t * density
    sheet_weight = sheet_area * t * density
    scrap_weight = sheet_weight - part_weight

    return {
        "sheet_weight": sheet_weight,
        "part_weight": part_weight,
        "cost": sheet_weight * cost,
        "scrap_value": scrap_weight * scrap_rate,
        "scrap_percent": (sheet_area - part_area) / sheet_area * 100
    }


# ---------------- UI ----------------
st.title("⚙️ ProNester – Hybrid Nesting (Fast + Deepnest)")

with st.sidebar:
    GAP = st.slider("Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Margin (mm)", 0.0, 20.0, 5.0)

    density = st.number_input("Density", value=7850)
    thickness = st.number_input("Thickness", value=2.0)
    cost = st.number_input("Cost ₹/kg", value=70.0)
    scrap_rate = st.number_input("Scrap ₹/kg", value=25.0)

    files = st.file_uploader("Upload DXF/SVG", type=["dxf","svg"], accept_multiple_files=True)

if files:
    engine = ProNester(GAP, MARGIN)
    parts = []

    for f in files:
        data = f.getvalue()
        shapes = extract_svg(data) if f.name.endswith(".svg") else extract_dxf(data)

        if shapes:
            qty = st.number_input(f"{f.name} Qty", 1, 100, 1, key=f.name)
            for _ in range(qty):
                parts.extend(shapes)

    col1, col2 = st.columns(2)

    if col1.button("⚡ Quick Nest"):
        W, H, layout, util = engine.nest(parts)
        st.session_state.quick = (W, H, layout, util)

    if col2.button("🔥 Deepnest Optimize"):
        svg = polygons_to_svg(parts)
        result = run_deepnest(svg)

        if result:
            layout = parse_svg(result)
            union = unary_union(layout)
            _, _, maxx, maxy = union.bounds
            st.session_state.deep = (maxx, maxy, layout)

# ---------------- DISPLAY ----------------
def show_result(title, W, H, layout):
    st.subheader(title)
    st.write(f"📐 {W:.0f} x {H:.0f} mm")

    fig, ax = plt.subplots(figsize=(10,5))
    ax.set_aspect('equal')

    for p in layout:
        x,y = p.exterior.xy
        ax.fill(x,y,alpha=0.5)

    st.pyplot(fig)

if "quick" in st.session_state:
    W,H,layout,util = st.session_state.quick
    show_result("⚡ Quick Nest", W, H, layout)

    m = calculate_metrics(layout, W, H, density, thickness, cost, scrap_rate)
    st.write(m)

if "deep" in st.session_state:
    W,H,layout = st.session_state.deep
    show_result("🔥 Deepnest Result", W, H, layout)

    m = calculate_metrics(layout, W, H, density, thickness, cost, scrap_rate)
    st.success(f"Utilization improved")
    st.write(m)
