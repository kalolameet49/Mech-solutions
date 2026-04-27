import streamlit as st
from core.parser import extract_from_dxf, extract_from_svg
from core.nesting import ProNester
from core.gcode import generate_gcode
from backend.jobs import create_job
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def nesting_ui():

    st.header("📐 Sheet Nesting")

    files = st.file_uploader("Upload DXF/SVG", accept_multiple_files=True)

    if files:
        parts = []

        for f in files:
            shapes = extract_from_svg(f) if f.name.endswith(".svg") else extract_from_dxf(f)
            qty = st.number_input(f"{f.name} Qty", 1, 100, 1)

            for _ in range(qty):
                parts.extend(shapes)

        if st.button("Run Nesting"):
            engine = ProNester()
            W, H, layout = engine.nest(parts)

            st.success(f"Sheet: {W:.0f} x {H:.0f}")

            # SAVE JOB
            create_job(st.session_state.user, "Nesting Job", {"W": W, "H": H})

            # DRAW
            fig, ax = plt.subplots()
            ax.set_aspect('equal')
            ax.add_patch(patches.Rectangle((0,0), W, H, fill=False))

            for poly in layout:
                x,y = poly.exterior.xy
                ax.fill(x,y,alpha=0.5)

            st.pyplot(fig)

            # GCODE
            gcode = generate_gcode(layout)
            st.download_button("Download G-Code", gcode, "output.nc")
