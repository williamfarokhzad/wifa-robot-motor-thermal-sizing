"""Copper loss and one-node temperature for piecewise constant DC current."""
import argparse
import json
import math
from pathlib import Path


def number(value, label, lo, hi):
    if (type(value) not in (int, float) or not lo <= value <= hi):
        raise ValueError(f"{label} must be a number between {lo:g} and {hi:g}")
    return float(value)


def parse(data):
    if not isinstance(data, dict):
        raise ValueError("configuration must be a JSON object")
    ambient = number(data.get("ambient_c"), "ambient_c", -50, 150)
    resistance = number(data.get("resistance_ohm"), "resistance_ohm", 1e-6, 1e4)
    rth = number(data.get("thermal_k_per_w"), "thermal_k_per_w", 1e-4, 1e4)
    capacitance = number(data.get("thermal_j_per_k"), "thermal_j_per_k", 1e-4, 1e6)
    if not isinstance(data.get("steps"), list) or not 1 <= len(data["steps"]) <= 1000:
        raise ValueError("steps must contain 1 to 1000 objects")
    steps = []
    for index, step in enumerate(data["steps"], start=1):
        if not isinstance(step, dict):
            raise ValueError(f"step {index} must be an object")
        duration = number(step.get("seconds"), f"step {index} seconds", 1e-6, 1e6)
        current = number(step.get("amps"), f"step {index} amps", -1e3, 1e3)
        steps.append((duration, current))
    return ambient, resistance, rth, capacitance, steps


def advance(rise, equilibrium, duration, tau):
    """Move the winding temperature rise toward its steady value."""
    return rise + (equilibrium - rise) * -math.expm1(-duration / tau)


def trace(rise, steps, resistance, rth, tau):
    result = [rise]
    for duration, current in steps:
        rise = advance(rise, current**2 * resistance * rth, duration, tau)
        result.append(rise)
    return result


def solve(config):
    ambient, resistance, rth, capacitance, steps = parse(config)
    tau = rth * capacitance
    period = math.fsum(duration for duration, _ in steps)
    rms = math.sqrt(math.fsum(duration * current**2 for duration, current in steps) / period)
    cold = trace(0, steps, resistance, rth, tau)
    # One whole cycle maps rise to a * rise + b. cold[-1] is b.
    periodic_start = cold[-1] / -math.expm1(-period / tau)
    periodic = trace(periodic_start, steps, resistance, rth, tau)
    return {
        "period_s": period, "time_constant_s": tau, "rms_a": rms,
        "mean_copper_w": resistance * rms**2,
        "mean_periodic_c": ambient + rth * resistance * rms**2,
        "cold_peak_c": ambient + max(cold),
        "periodic_peak_c": ambient + max(periodic),
        "periodic_min_c": ambient + min(periodic),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("config", type=Path, help="path to a duty-cycle JSON file")
    args = cli.parse_args()
    try:
        result = solve(json.loads(args.config.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        cli.exit(2, f"error: {exc}\n")
    for key, value in result.items():
        print(f"{key}: {value:.3f}")


if __name__ == "__main__":
    main()
