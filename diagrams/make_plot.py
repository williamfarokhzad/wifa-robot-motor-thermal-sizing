"""Regenerate the editable temperature chart from the two JSON examples."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from thermal import advance, parse, trace  # noqa: E402

svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="560" viewBox="0 0 960 560" role="img" aria-labelledby="title desc">',
       '<title id="title">Equal RMS current, different peak winding temperatures</title>',
       '<desc id="desc">Simulated periodic temperatures over 120 seconds. Short pulses peak at 47.6 degrees Celsius, long pulses at 98.4 degrees Celsius. Both average 45 degrees Celsius.</desc>',
       '<rect width="960" height="560" rx="24" fill="#edf5f3"/>',
       '<g font-family="DejaVu Sans, sans-serif" fill="#173c3f">',
       '<text x="55" y="63" font-size="34" font-weight="700">Same RMS current, different peaks</text>',
       '<text x="55" y="102" font-size="24">Both cycles: 2.5 A RMS and 5 W mean copper loss</text>']

def x(t): return 105 + t / 120 * 775
def y(temp): return 432 - (temp - 20) / 80 * 280

for temp in (20, 40, 60, 80, 100):
    yy = y(temp)
    svg += [f'<path d="M105 {yy}H880" stroke="#b2c9c6"/>',
            f'<text x="94" y="{yy+7}" text-anchor="end" font-size="21">{temp}</text>']
for t in range(0, 121, 30):
    xx = x(t)
    svg += [f'<path d="M{xx} 152V432" stroke="#b2c9c6"/>',
            f'<text x="{xx}" y="466" text-anchor="middle" font-size="21">{t}</text>']
svg += ['<text x="108" y="138" font-size="21">Winding (°C)</text>',
        '<text x="907" y="466" font-size="21">s</text>']
for name, color, n, caption, legend_x in [
        ("short-pulses", "#006b72", 30, "Short pulses: 47.6 °C peak", 105),
        ("long-pulses", "#a54215", 1, "Long pulses: 98.4 °C peak", 510)]:
    ambient, resistance, rth, cap, steps = parse(json.loads((root / "examples" / (name + ".json")).read_text()))
    tau = rth * cap
    from math import expm1
    rise = trace(0, steps, resistance, rth, tau)[-1] / -expm1(-sum(d for d, _ in steps) / tau)
    points, t = [f"{x(0):.1f},{y(ambient + rise):.1f}"], 0
    for duration, current in steps * n:
        eq = current**2 * resistance * rth
        for i in range(1, int(duration * 4) + 1):
            dt = i / 4
            points.append(f"{x(t + dt):.1f},{y(ambient + advance(rise, eq, dt, tau)):.1f}")
        rise = advance(rise, eq, duration, tau)
        t += duration
    svg += [f'<polyline fill="none" stroke="{color}" stroke-width="4" points="{" ".join(points)}"/>',
            f'<path d="M{legend_x} 516h39" stroke="{color}" stroke-width="5"/>',
            f'<text x="{legend_x+49}" y="525" font-size="23" fill="{color}">{caption}</text>']
svg += ['</g></svg>']
Path(__file__).with_name("pulse-comparison.svg").write_text("\n".join(svg) + "\n")
