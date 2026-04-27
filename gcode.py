def generate_gcode(layout):

    g = ["G21", "G90"]

    for poly in layout:
        coords = list(poly.exterior.coords)

        start = coords[0]
        g.append(f"G0 X{start[0]:.2f} Y{start[1]:.2f}")
        g.append("M3")

        for x, y in coords:
            g.append(f"G1 X{x:.2f} Y{y:.2f}")

        g.append("M5")

    return "\n".join(g)
