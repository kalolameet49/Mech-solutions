import streamlit as st
import ezdxf
from shapely.geometry import Polygon
import pyclipper
import io

# --- CORE LOGIC ---

def get_polygons_from_dxf(dxf_file):
    """Extracts closed loops from DXF and converts to Shapely Polygons."""
    try:
        # Load DXF from Streamlit's UploadedFile (BytesIO)
        content = dxf_file.read().decode('utf-8', errors='ignore')
        doc = ezdxf.readstr(content)
        msp = doc.modelspace()
        polygons = []
        
        for entity in msp.query('LWPOLYLINE'):
            points = [(p[0], p[1]) for p in entity.get_points()]
            if len(points) >= 3:
                polygons.append(Polygon(points))
        return polygons
    except Exception as e:
        st.error(f"Error reading DXF: {e}")
        return []

def apply_kerf_offset(polygon, tool_dia):
    """Inflates polygon using PyClipper for tool compensation."""
    scale = 1000
    pco = pyclipper.PyclipperOffset()
    scaled_coords = [(int(x * scale), int(y * scale)) for x in polygon.exterior.coords for y in x] # Flattened fix
    # Simplified coordinate handling for robust offsetting
    coords = list(polygon.exterior.coords)
    scaled_coords = pyclipper.scale_to_clipper(coords, scale)
    
    pco.AddPath(scaled_coords, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    offset_path = pco.Execute(pyclipper.scale_to_clipper(tool_dia, scale))
    
    if not offset_path:
        return polygon
    return Polygon(pyclipper.scale_from_clipper(offset_path[0], scale))

def simple_nest(parts, sheet_w, sheet_h):
    """Bottom-Left Fill algorithm."""
    nested_parts = []
    curr_x, curr_y = 0.0, 0.0
    max_h_row = 0.0
    
    for part in parts:
        minx, miny, maxx, maxy = part.bounds
        w, h = maxx - minx, maxy - miny
        
        if curr_x + w > sheet_w:
            curr_x = 0
            curr_y += max_h_row
            max_h_row = 0
            
        if curr_y + h > sheet_h:
            continue # Part doesn't fit on sheet
            
        nested_parts.append({'polygon': part, 'pos': (curr_x - minx, curr_y - miny)})
        curr_x += w
        max_h_row = max(max_h_row, h)
        
    return nested_parts

def export_to_dxf(results, sheet_w, sheet_h):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    # Sheet Border (Red)
    msp.add_lwpolyline([(0,0), (sheet_w,0), (sheet_w,sheet_h), (0,sheet_h)], dxfattribs={'closed': True, 'color': 1})
    
    for item in results:
        poly = item['polygon']
        tx, ty = item['pos']
        points = [(p[0] + tx, p[1] + ty) for p in poly.exterior.coords]
        msp.add_lwpolyline(points, dxfattribs={'closed': True, 'color': 7})
        
    out = io.StringIO()
    doc.write(out)
    return out.getvalue()

# --- STREAMLIT UI ---

st.set_page_config(page_title="Vexa Nesting Engine", layout="wide")
st.title("Vexa Engineering | CNC Nesting & Costing")

with st.sidebar:
    st.header("1. Sheet & Tool")
    s_w = st.number_input("Width (mm)", value=2440)
    s_h = st.number_input("Height (mm)", value=1220)
    kerf = st.number_input("Kerf/Tool Dia (mm)", value=3.0)
    
    st.header("2. Material Presets")
    mat_type = st.selectbox("Material", ["Mild Steel", "SS 304", "Aluminium"])
    thickness = st.selectbox("Thickness (mm)", [1, 2, 3, 5, 8, 10])
    
    # Simple logic for pricing based on material
    base_rate = 0.005 if mat_type == "Mild Steel" else 0.015
    m_cost = st.number_input("Mat Cost/sqmm", value=base_rate, format="%.4f")
    c_cost = st.number_input("Cut Cost/mm", value=0.02)
    markup = st.slider("Profit Markup %", 0, 100, 20)

uploaded_file = st.file_uploader("Upload DXF", type="dxf")

if uploaded_file:
    raw_parts = get_polygons_from_dxf(uploaded_file)
    st.info(f"Detected {len(raw_parts)} closed loops in file.")
    
    if st.button("Generate Nesting & Quote"):
        # Process
        buffered = [apply_kerf_offset(p, kerf) for p in raw_parts]
        results = simple_nest(buffered, s_w, s_h)
        
        # Metrics
        total_dist = sum(p.length for p in raw_parts)
        total_area = sum(p.area for p in raw_parts)
        usage = (total_area / (s_w * s_h)) * 100
        
        # Financials
        cost = ((s_w * s_h) * m_cost) + (total_dist * c_cost)
        quote = cost * (1 + (markup/100))
        
        # Display
        m1, m2, m3 = st.columns(3)
        m1.metric("Utilization", f"{usage:.1f}%")
        m2.metric("Cut Distance", f"{total_dist/1000:.2f} m")
        m3.metric("Estimated Quote", f"₹{quote:,.2f}")
        
        # Export
        final_dxf = export_to_dxf(results, s_w, s_h)
        st.download_button("📥 Download Nested DXF", final_dxf, "vexa_nest.dxf", "application/dxf")