from shapely.affinity import translate
from shapely.ops import unary_union

class ProNester:

    def __init__(self, gap=3, margin=5):
        self.gap = gap
        self.margin = margin

    def nest(self, parts):

        parts = [p.buffer(self.gap/2) for p in parts]
        placed = []

        x_offset = self.margin

        for p in parts:
            placed.append(translate(p, x_offset, self.margin))
            x_offset += p.bounds[2] + self.gap

        union = unary_union(placed)
        minx, miny, maxx, maxy = union.bounds

        W = maxx - minx + self.margin
        H = maxy - miny + self.margin

        return W, H, placed
