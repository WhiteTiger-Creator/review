"""Independent reference helpers for Sky Kingdom Fleet Campaign verifier checks."""

HULLS = {
    "SCOUT": {"atk": 4, "def": 2, "fuel_cap": 6, "base_range": 3, "upkeep": 1},
    "FRIGATE": {"atk": 7, "def": 5, "fuel_cap": 10, "base_range": 2, "upkeep": 2},
    "GALLEON": {"atk": 11, "def": 8, "fuel_cap": 14, "base_range": 2, "upkeep": 3},
    "FORTRESS": {"atk": 9, "def": 14, "fuel_cap": 12, "base_range": 1, "upkeep": 4},
}

WEATHER_MOVE = {"CLEAR": 100, "THERMAL": 80, "FOG": 120, "GALE": 150, "STORM": 200}


def reference_edge_cost(weather: str) -> int:
    """Return ceil weather move multiplier for a unit-length edge."""
    mul = WEATHER_MOVE[weather]
    return (mul + 99) // 100


def reference_paid_fuel(raw_cost: int, discount_pct: int) -> int:
    """Apply fuel discount with a minimum paid cost of 1 when raw_cost > 0."""
    if raw_cost == 0:
        return 0
    paid = raw_cost * (100 - discount_pct) // 100
    return max(1, paid)
