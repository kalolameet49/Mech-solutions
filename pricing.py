def calculate_cost(area, thickness, density, cost_per_kg):

    volume = area * (thickness / 1000)
    weight = volume * density

    return weight, weight * cost_per_kg
