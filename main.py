import streamlit as st
import ezdxf
from ezdxf import path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon, MultiLineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import rotate, translate
import time
import io
import svgelements

# --- PAGE SETUP ---
st.set_page_config(page_title="ProNester Industrial", layout="wide")

class ProNesterEngine:
    def __init__(self, sheet_w, sheet_h, gap=3.0, margin=5.0):
        self.sheet_w = sheet_w
        self.sheet_h = sheet_h
        self.gap = gap
        self.margin = margin
        self.sheets = [[]]
        self.utilization = 0

    def extract_from_svg(self, uploaded_file):
        try:
            svg_text = uploaded_file.getvalue().decode("utf-8")
            svg = svgelements.SVG.parse(io.StringIO(svg_text))
            polys = []

            for element in svg.elements():
                if isinstance(element, svgelements.Path):
                    pts = [(p.x, p.y) for p in element.as_points()]
                    if len(pts) > 2:
                        poly = Polygon(pts)
                        if not poly.is_valid:
                            poly = poly.buffer(0)
                        if poly.area > 1.0:
                            min_x, min_y, _, _ = poly.bounds
                            polys.append(translate(poly, -min_x, -min_y))
            return polys

        except Exception as e:
            st.error(f"SVG Error: {e}")
            return []

    def extract_from_dxf(self, uploaded_file):
        try:
            doc = ezdxf.read(io.BytesIO(uploaded_file.getvalue()))
            msp = doc.modelspace()
            all_segments = []

            for entity in msp:
                try:
                    entity_paths = path.make_paths(entity)
                    for p in entity_paths:
                        vertices = list(p.flattening(distance=0.1))
                        for i in range(len(vertices) - 1):
                            v1, v2 = vertices[i], vertices[i+1]
                            all_segments.append([
                                (round(v1.x, 3), round(v1.y, 3)),
                                (round(v2.x, 3), round(v2.y, 3))
                            ])
                except:
                    continue

            merged = unary_union(MultiLineString(all_segments))
            healed = merged.buffer(0.02).buffer(-0.02)
            found_polys = list(polygonize(healed))

            return [
                translate(p, -p.bounds[0], -p.bounds[1])
                for p in found_polys if p.area > 1.0
            ]

        except Exception as e:
            st.error(f"DXF Error: {e}")
            return []

    def nest(self, parts_list):
        parts_list.sort(key=lambda p: p.area, reverse=True)

        buffered_parts = [
            p.buffer(self.gap / 2, join_style=2)
            for p in parts_list
        ]

        total_placed_area = 0
        total_part_area = sum(p.area for p in parts_list)

        for part in buffered_parts:
            placed = False

            for angle in [0, 90]:  # optimized rotations
                if placed:
                    break

                rot = rotate(part, angle, origin='centroid')
                min_x, min_y, max_x, max_y = rot.bounds
                poly_norm = translate(rot, -min_x, -min_y)

                w, h = max_x - min_x, max_y - min_y

                step = max(10, int(min(w, h) / 3))  # adaptive step

                for s_id, sheet_content in enumerate(self.sheets):

                    for y in range(int(self.margin), int(self.sheet_h - h - self.margin), step):
                        for x in range(int(self.margin), int(self.sheet_w - w - self.margin), step):

                            trial = translate(poly_norm, x, y)

                            if not any(trial.intersects(p) for p in sheet_content):
                                self.sheets[s_id].append(trial)
                                total_placed_area += part.area
                                placed = True
                                break

                        if placed:
                            break
                    if placed:
                        break

            if not placed:
                self.sheets.append([translate(part, self.margin, self.margin)])
                total_placed_area += part.area

        total_sheets = len(self.sheets)
        sheet_area_total = self.sheet_w * self.sheet_h * total_sheets

        self.utilization = (total_placed_area / sheet_area_total) * 100
        estimated_sheets = total_part_area / (self.sheet_w * self.sheet_h)

        return {
            "layouts": self.sheets,
            "total_sheets": total_sheets,
            "utilization": self.utilization,
            "estimated_sheets": estimated_sheets,
            "total_part_area": total_part_area
        }

# --- UI ---
st.title("⚙️ ProNester: DXF & SVG Optimizer")

with st.sidebar:
    st.header("1. Sheet Setup")
    SW = st.number_input("Sheet Width (mm)", min_value=100, value=2500)
    SH = st.number_input("Sheet Height (mm)", min_value=100, value=1250)
    GAP = st.slider("Part Gap (mm)", 0.0, 10.0, 3.0)
    MARGIN = st.slider("Sheet Margin (mm)", 0.0, 20.0, 5.0)

    st.header("2. Files")
    uploaded_files = st.file_uploader(
        "Upload Files",
        type=["dxf", "svg"],
        accept_multiple_files=True
    )

if uploaded_files:
    nester = ProNesterEngine(SW, SH, GAP, MARGIN)
    master_list = []

    st.subheader("3. Set Quantities")

    for f in uploaded_files:
        if f.name.endswith('.svg'):
            shapes = nester.extract_from_svg(f)
        else:
            shapes = nester.extract_from_dxf(f)

        if shapes:
            c1, c2 = st.columns([3, 1])
            c1.write(f"✅ **{f.name}** ({len(shapes)} shapes)")
            qty = c2.number_input(f"Qty", 1, 100, 1, key=f"q_{f.name}")

            for _ in range(qty):
                master_list.extend(shapes)
        else:
            st.error(f"❌ No valid shapes in {f.name}")

    st.markdown("---")

    if st.button("🚀 Start Nesting", use_container_width=True) and master_list:
        with st.spinner("Nesting in progress..."):
            result = nester.nest(master_list)

        actual_sheets = result["total_sheets"]
        estimated_sheets = result["estimated_sheets"]

        st.success(
            f"""
            ✅ Nesting Completed  
            📄 Actual Sheets Required: **{actual_sheets}**  
            ⚡ Estimated Sheets (Ideal): **{estimated_sheets:.2f}**  
            📊 Utilization: **{result['utilization']:.2f}%**
            """
        )

        # --- Visualization ---
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_aspect('equal')

        out_doc = ezdxf.new('R2010')
        msp = out_doc.modelspace()

        for i, sheet in enumerate(result["layouts"]):
            off_x = i * (SW + 200)

            ax.add_patch(
                patches.Rectangle((off_x, 0), SW, SH, fill=False)
            )

            for poly in sheet:
                x, y = poly.exterior.xy

                ax.fill(
                    [px + off_x for px in x],
                    y,
                    alpha=0.5
                )

                msp.add_lwpolyline([
                    (px + off_x, py)
                    for px, py in poly.exterior.coords
                ])

        st.pyplot(fig)

        # --- Download ---
        dxf_io = io.StringIO()
        out_doc.write(dxf_io)

        st.download_button(
            "📥 Download Result DXF",
            dxf_io.getvalue(),
            "nest_output.dxf"
        )

else:
    st.info("Please upload DXF or SVG files in the sidebar.")
