import streamlit as st
import ezdxf
from ezdxf import path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon, MultiLineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import rotate, translate
import svgelements
import io
import random
import math

st.set_page_config(page_title="ProNester Advanced", layout="wide")

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
                    v = list(p.flattening(0.5))
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
        for _ in range(3):
            angles.append(random.uniform(0, 360))

        result = []
        for a in angles:
            r = rotate(part, a, origin='centroid')
            minx, miny, _, _ = r.bounds
            r = translate(r, -minx, -miny)
            result.append(r)

        return result

    # ---------- CANDIDATES ----------
    def get_candidates(self, placed):
        pts = [(self.margin, self.margin)]

        for p in placed:
            minx, miny, maxx, maxy = p.bounds
            pts.extend([
                (maxx, miny),
                (minx, maxy),
                (maxx, maxy)
            ])

        return pts

    # ---------- SCORING ----------
    def score_layout(self, placed):
        union = unary_union(placed)
        minx, miny, maxx, maxy = union.bounds

        W = maxx + self.margin
        H = maxy + self.margin

        area = W * H
        perimeter = 2 * (W + H)

        return area + perimeter * 0.3, W, H

    # ---------- INITIAL PACK ----------
    def initial_pack(self, parts):
        placed = []

        for part in parts:
            best = None
            best_score = float('inf')

            for r in self.generate_rotations(part):
                for cx, cy in self.get_candidates(placed):

                    trial = translate(r, cx, cy)

                    if any(trial.intersects(p) for p in placed):
                        continue

                    temp = placed + [trial]
                    score, _, _ = self.score_layout(temp)

                    if score < best_score:
                        best = trial
                        best_score = score

            if best:
                placed.append(best)
            else:
                placed.append(translate(part, self.margin, self.margin))

        return placed

    # ---------- REFINEMENT ----------
    def refine_layout(self, placed, iterations=200):

        current = placed[:]
        best = placed[:]

        best_score, _, _ = self.score_layout(best)

        T = 100.0

        for _ in range(iterations):

            i = random.randint(0, len(current) - 1)
            new_layout = current[:]

            part = new_layout.pop(i)

            r = rotate(part, random.uniform(0, 360), origin='centroid')
            dx = random.uniform(-20, 20)
            dy = random.uniform(-20, 20)

            moved = translate(r, dx, dy)

            if any(moved.intersects(p) for p in new_layout):
                continue

            new_layout.append(moved)

            score, _, _ = self.score_layout(new_layout)

            if score < best_score or random.random() < math.exp((best_score - score) / T):
                current = new_layout

                if score < best_score:
                    best = new_layout
                    best_score = score

            T *= 0.97

        return best

    # ---------- MAIN ----------
    def nest(self, parts, attempts=15):

        best_layout = None
        best_score = float('inf')
        best_W, best_H = 0, 0

        parts = [p.buffer(self.gap / 2) for p in parts]

        for _ in range(attempts):

            random.shuffle(parts)

            placed = self.initial_pack(parts)
            placed = self.refine_layout(placed)

            score, W, H = self.score_layout(placed)

            if score < best_score:
                best_score = score
                best_layout = placed
                best_W, best_H = W, H

        util = (sum(p.area for p in parts) / (best_W * best_H)) * 100

        return best_W, best_H, best_layout, util


# ---------------- UI ----------------
st.title("⚙️ ProNester – Advanced Nesting Engine")

with st.sidebar:
    GAP = st.slider("Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Margin (mm)", 0.0, 20.0, 5.0)
    files = st.file_uploader("Upload DXF / SVG", type=["dxf", "svg"], accept_multiple_files=True)

if files:
    engine = ProNester(GAP, MARGIN)
    parts = []

    for f in files:
        shapes = engine.extract_from_svg(f) if f.name.endswith(".svg") else engine.extract_from_dxf(f)
        parts.extend(shapes)

    if st.button("🚀 Run Nesting"):

        with st.spinner("Optimizing nesting..."):
            W, H, layout, util = engine.nest(parts)

        st.success(f"📐 Sheet Size: {W:.0f} x {H:.0f} mm | Utilization: {util:.2f}%")

        fig, ax = plt.subplots(figsize=(10,5))
        ax.set_aspect('equal')

        ax.add_patch(patches.Rectangle((0,0), W, H, fill=False))

        for poly in layout:
            x,y = poly.exterior.xy
            ax.fill(x, y, alpha=0.5)

        st.pyplot(fig)

else:
    st.info("Upload DXF or SVG files to start.")
