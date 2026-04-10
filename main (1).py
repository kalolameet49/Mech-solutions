import ezdxf
from shapely.geometry import Polygon, LineString
from shapely.ops import linemerge, polygonize, unary_union
from shapely.affinity import translate, rotate, scale
import math
import os

class VexaNestingSystem:
    def __init__(self, sheet_w, sheet_h, spacing=2.0, feed_rate=1200, safe_z=5.0, cut_z=-2.0):
        self.sheet_w = sheet_w
        self.sheet_h = sheet_h
        self.spacing = spacing
        self.feed_rate = feed_rate
        self.safe_z = safe_z
        self.cut_z = cut_z

    def extract_shape_from_dxf(self, filepath):
        """
        Robustly reads DXF using readfile() to avoid 'readstr' attribute errors.
        """
        try:
            # CORRECTED: Use readfile for local paths
            doc = ezdxf.readfile(filepath)
            msp = doc.modelspace()
            edges = []

            for entity in msp:
                etype = entity.dxftype()
                if etype == 'LINE':
                    edges.append(LineString([entity.dxf.start, entity.dxf.end]))
                elif etype in ['LWPOLYLINE', 'POLYLINE']:
                    pts = list(entity.get_points(format='xy'))
                    if len(pts) > 1: edges.append(LineString(pts))
                elif etype == 'CIRCLE':
                    c = entity.dxf.center
                    r = entity.dxf.radius
                    pts = [(c.x+r*math.cos(a), c.y+r*math.sin(a)) for a in [i*(2*math.pi/64) for i in range(65)]]
                    edges.append(LineString(pts))
                elif etype == 'SPLINE':
                    # Flatten splines into small line segments
                    pts = list(entity.construction_tool().flattening(distance=0.1))
                    edges.append(LineString(pts))

            # Healing logic: Snap points together and find closed loops
            merged = linemerge(unary_union(edges))
            polys = list(polygonize(merged))
            
            if not polys:
                print(f"Warning: No closed loops detected in {filepath}")
                return None
                
            return max(polys, key=lambda p: p.area)
        except Exception as e:
            print(f"Error reading DXF: {e}")
            return None

    def get_optimized_variant(self, poly):
        """Finds tightest fit using 5-degree steps and mirroring."""
        best_poly = poly
        min_bbox_area = float('inf')

        for flip in [1, -1]:
            temp_poly = scale(poly, xfact=flip, origin='center')
            for angle in range(0, 360, 5):
                rotated = rotate(temp_poly, angle, origin='center')
                minx, miny, maxx, maxy = rotated.bounds
                area = (maxx - minx) * (maxy - miny)
                if area < min_bbox_area:
                    min_bbox_area = area
                    best_poly = rotated
        return best_poly

    def generate_gcode(self, nested_polys, filename="nest_output_cnc.nc"):
        with open(filename, "w") as f:
            f.write("(Vexa Engineering CNC Nesting)\n(UNITS: MM)\n")
            f.write("G21 G90 G17\n") 
            f.write(f"M03 S12000\nG00 Z{self.safe_z}\n")

            for i, p in enumerate(nested_polys):
                coords = list(p.exterior.coords)
                f.write(f"(Part {i+1})\n")
                f.write(f"G00 X{coords[0][0]:.3f} Y{coords[0][1]:.3f}\n")
                f.write(f"G01 Z{self.cut_z} F200\n")
                for x, y in coords[1:]:
                    f.write(f"G01 X{x:.3f} Y{y:.3f} F{self.feed_rate}\n")
                f.write(f"G00 Z{self.safe_z}\n")

            f.write("M05\nG00 X0 Y0\nM30\n")

    def run(self):
        # Scan folder for DXF files
        files = [f for f in os.listdir('.') if f.lower().endswith('.dxf') and 'nest_output' not in f]
        if not files:
            print("No DXF files found. Place them in the same folder as main.py")
            return

        all_requested_parts = []
        print(f"\n{'DXF File':<30} | {'Area (m2)':<12}")
        print("-" * 45)

        for f in files:
            poly = self.extract_shape_from_dxf(f)
            if poly:
                area_m2 = poly.area / 1_000_000
                print(f"{f:<30} | {area_m2:>10.4f}")
                
                try:
                    qty = int(input(f"  Enter quantity for {f}: "))
                    for _ in range(qty):
                        all_requested_parts.append(poly)
                except ValueError:
                    print("  Invalid quantity, skipping.")

        # Sort: Largest parts first
        all_requested_parts.sort(key=lambda p: p.area, reverse=True)

        # Nesting calculation
        nested_results = []
        cur_x, cur_y, row_h = 0, 0, 0

        print("\nNesting shapes... please wait.")
        for p in all_requested_parts:
            p_opt = self.get_optimized_variant(p)
            minx, miny, maxx, maxy = p_opt.bounds
            w, h = (maxx - minx) + self.spacing, (maxy - miny) + self.spacing

            if cur_x + w > self.sheet_w:
                cur_x = 0
                cur_y += row_h
                row_h = 0

            if cur_y + h > self.sheet_h:
                print("!! OUT OF MATERIAL: Sheet limit reached !!")
                break

            final_p = translate(p_opt, xoff=cur_x - minx, yoff=cur_y - miny)
            nested_results.append(final_p)
            cur_x += w
            row_h = max(row_h, h)

        # Output generation
        # 1. Visual DXF
        out_doc = ezdxf.new()
        out_msp = out_doc.modelspace()
        out_msp.add_lwpolyline([(0,0), (self.sheet_w, 0), (self.sheet_w, self.sheet_h), (0, self.sheet_h)], dxfattribs={'closed': True, 'color': 1})
        for np in nested_results:
            out_msp.add_lwpolyline(list(np.exterior.coords), dxfattribs={'closed': True, 'color': 7})
        out_doc.saveas("nest_output_visual.dxf")

        # 2. G-Code
        self.generate_gcode(nested_results)
        
        print("\n" + "="*40)
        print("NESTING COMPLETE")
        print(f"Generated G-code for {len(nested_results)} parts.")
        print("Check 'nest_output_visual.dxf' and 'nest_output_cnc.nc'")
        print("="*40)

if __name__ == "__main__":
    # Customise your sheet size and CNC settings here
    app = VexaNestingSystem(
        sheet_w=2440,   # Width in mm
        sheet_h=1220,   # Height in mm
        spacing=5.0,    # Distance between parts
        feed_rate=1500, # CNC Travel Speed
        safe_z=10.0,    # Tool lift height
        cut_z=-3.0      # Tool cut depth
    )
    app.run()
