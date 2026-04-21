import streamlit as st
import io
from shapely.geometry import Polygon
import svgelements
import ezdxf
from ezdxf import path
from shapely.geometry import MultiLineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import translate

from db import create_job, get_jobs
from tasks import run_nesting

st.set_page_config(page_title="ProNester SaaS", layout="wide")

# ---------- FILE READ ----------
@st.cache_data
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

@st.cache_data
def extract_dxf(file_bytes):
    doc = ezdxf.read(io.BytesIO(file_bytes))
    msp = doc.modelspace()
    segs = []
    for e in msp:
        try:
            for p in path.make_paths(e):
                v = list(p.flattening(0.1))
                for i in range(len(v)-1):
                    segs.append([(v[i].x, v[i].y),(v[i+1].x, v[i+1].y)])
        except:
            pass

    merged = unary_union(MultiLineString(segs))
    healed = merged.buffer(0.02).buffer(-0.02)
    polys = list(polygonize(healed))
    return [translate(p, -p.bounds[0], -p.bounds[1]) for p in polys if p.area > 1]

# ---------- UI ----------
st.title("⚙️ ProNester SaaS (Async + Storage)")

files = st.file_uploader("Upload DXF/SVG", type=["dxf","svg"], accept_multiple_files=True)

parts = []

if files:
    st.subheader("Set Quantity")

    for f in files:
        data = f.getvalue()
        shapes = extract_svg(data) if f.name.endswith(".svg") else extract_dxf(data)

        if shapes:
            col1, col2 = st.columns([3,1])
            col1.write(f"✅ {f.name}")
            qty = col2.number_input("Qty", 1, 100, 1, key=f.name)

            for _ in range(qty):
                parts.extend(shapes)

# ---------- RUN JOB ----------
if st.button("🚀 Run Nesting (Async)") and parts:

    polygons_json = [list(p.exterior.coords) for p in parts]

    job_id = create_job()
    run_nesting.delay(job_id, polygons_json)

    st.success(f"Job submitted: {job_id}")

# ---------- DASHBOARD ----------
st.markdown("---")
st.header("📊 Job History")

jobs = get_jobs()

for job in jobs[::-1]:
    col1, col2, col3, col4 = st.columns(4)

    col1.write(job.id[:8])
    col2.write(job.status)

    if job.width:
        col3.write(f"{job.width:.0f} x {job.height:.0f}")
    else:
        col3.write("-")

    if job.file_path:
        try:
            with open(job.file_path, "r") as f:
                col4.download_button("Download", f.read(), file_name=f"{job.id}.json")
        except:
            col4.write("-")
