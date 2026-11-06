import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from thermal import solve

ROOT = Path(__file__).resolve().parents[1]


def example(name):
    return json.loads((ROOT / "examples" / (name + ".json")).read_text())


class ThermalTests(unittest.TestCase):
    def test_equilibrium_constant_load(self):
        c = example("short-pulses")
        c["steps"] = [{"seconds": 12, "amps": 2}]
        y = solve(c)
        self.assertAlmostEqual(y["periodic_peak_c"], 37.8)
        self.assertAlmostEqual(y["periodic_min_c"], 37.8)
        self.assertAlmostEqual(y["cold_peak_c"], 25 + 12.8 * (1 - 1 / math.e))

    def test_zero_current_does_not_heat(self):
        c = example("short-pulses")
        c["steps"][0]["amps"] = 0
        self.assertEqual(solve(c)["periodic_peak_c"], 25)

    def test_current_sign_changes_no_copper_loss(self):
        c = example("long-pulses")
        y = solve(c)
        c["steps"][0]["amps"] *= -1
        self.assertEqual(y, solve(c))

    def test_same_rms_different_peak(self):
        a, b = (solve(example(x)) for x in ("short-pulses", "long-pulses"))
        self.assertEqual(a["rms_a"], 2.5)
        self.assertEqual(a["rms_a"], b["rms_a"])
        self.assertEqual(a["mean_copper_w"], b["mean_copper_w"])
        self.assertEqual(a["mean_periodic_c"], b["mean_periodic_c"])
        self.assertGreater(b["periodic_peak_c"] - a["periodic_peak_c"], 50)

    def test_periodic_peaks_against_independent_euler_integrator(self):
        # Integrate the heat balance directly, without the production recurrence.
        for case in ("short-pulses", "long-pulses"):
            with self.subTest(case=case):
                c = example(case)
                rise = 0.0
                for _ in range(100):
                    peak = rise
                    for step in c["steps"]:
                        n = round(step["seconds"] / 0.01)
                        dt = step["seconds"] / n
                        for _ in range(n):
                            rise += (step["amps"] ** 2 * 0.8 - rise / 4) * dt / 3
                            peak = max(peak, rise)
                self.assertAlmostEqual(peak + 25, solve(c)["periodic_peak_c"], delta=0.015)

    def test_enclosure_shifts_every_absolute_temperature(self):
        a, b = (solve(example(x)) for x in ("long-pulses", "warm-enclosure"))
        for key in ("cold_peak_c", "periodic_peak_c", "periodic_min_c", "mean_periodic_c"):
            self.assertAlmostEqual(b[key] - a[key], 20)

    def test_small_period_remains_numerically_stable(self):
        c = dict(ambient_c=0, resistance_ohm=1, thermal_k_per_w=1e4,
                 thermal_j_per_k=1e6, steps=[{"seconds": 1e-6, "amps": 1}])
        self.assertAlmostEqual(solve(c)["periodic_peak_c"], 1e4)

    def test_validation_rejects_unphysical_inputs_and_non_numeric_json(self):
        for field, value in [("resistance_ohm", -1), ("ambient_c", True),
                             ("thermal_j_per_k", math.inf), ("steps", []),
                             ("thermal_k_per_w", "4"), ("steps", [{"seconds": 0, "amps": 1}])]:
            with self.subTest(field=field, value=value):
                c = example("short-pulses")
                c[field] = value
                with self.assertRaises(ValueError):
                    solve(c)

    def test_cli_success_and_malformed_input(self):
        command = [sys.executable, str(ROOT / "thermal.py")]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text("{")
            result = subprocess.run(command + [str(p)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("error:", result.stderr)
        result = subprocess.run(command + [str(ROOT / "examples" / "long-pulses.json")],
                                capture_output=True, text=True, check=True)
        self.assertIn("periodic_peak_c: 98.437", result.stdout)
