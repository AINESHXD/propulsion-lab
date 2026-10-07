"""Generate the 2D engine cross-section SVGs for /lab/sections/.

Geometry is a representative single-spool turbojet (proportions only, not traced from
any real engine). The gas path is coloured by the stagnation temperature and pressure
that the PropulsionLab cycle solver returns for its default operating point, so the
drawing and the console agree.

Run from the repo root:  .venv/Scripts/python scripts/build_engine_sections.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.main import run_turbojet_simulation
from app.schemas import TurbojetInput

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "sections"

# Drawing frame: engine x = 0..1000 maps to px 110..1110; radius r maps to axis -/+ r.
X0, AXIS, W, H = 110.0, 270.0, 1220, 560


def px(x: float) -> float:
    return X0 + x


def smooth(points: list[tuple[float, float]], sign: int = -1) -> str:
    """Catmull-Rom spline through (x, r) points as an SVG cubic path (no leading M)."""
    p = [(px(x), AXIS + sign * r) for x, r in points]
    out = []
    for i in range(len(p) - 1):
        p0, p1, p2 = p[max(i - 1, 0)], p[i], p[i + 1]
        p3 = p[min(i + 2, len(p) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(out)


def interp(points: list[tuple[float, float]], x: float) -> float:
    for (xa, ra), (xb, rb) in zip(points, points[1:]):
        if xa <= x <= xb:
            return ra + (rb - ra) * (x - xa) / (xb - xa)
    return points[0][1] if x < points[0][0] else points[-1][1]


def lerp_color(stops: list[tuple[float, str]], t: float) -> str:
    t = min(max(t, 0.0), 1.0)
    for (ta, ca), (tb, cb) in zip(stops, stops[1:]):
        if ta <= t <= tb:
            f = (t - ta) / (tb - ta)
            a = [int(ca[i:i + 2], 16) for i in (1, 3, 5)]
            b = [int(cb[i:i + 2], 16) for i in (1, 3, 5)]
            return "#" + "".join(f"{round(u + (v - u) * f):02x}" for u, v in zip(a, b))
    return stops[-1][1]


# Site palette: cool accent blue through the chart temperature orange.
TEMP_MAP = [(0.0, "#1d2c47"), (0.25, "#3f6aa8"), (0.5, "#b99a6a"), (0.8, "#d97757"), (1.0, "#f6d2bd")]
PRES_MAP = [(0.0, "#17202e"), (0.5, "#3f6aa8"), (1.0, "#cfe0fa")]

# ---- Turbojet geometry (engine units, r = radius from the axis) ---------------------
TIP = [(0, 141), (40, 145), (120, 150), (150, 147), (420, 117), (445, 118), (472, 158),
       (640, 158), (660, 128), (742, 141), (790, 138), (1000, 106)]
HUB = [(28, 0), (40, 26), (70, 46), (120, 62), (420, 96), (445, 96), (472, 72), (640, 72),
       (660, 92), (742, 86), (790, 82), (900, 38), (955, 0)]
SKIN = [(0, 153), (40, 168), (120, 176), (430, 176), (470, 187), (640, 187), (700, 177),
        (760, 160), (1000, 113)]
COMP_STAGES = [(135 + 35 * i) for i in range(8)]          # rotor leading edges
TURB_ROWS = [(648, "stator"), (667, "rotor"), (690, "stator"), (709, "rotor")]
STATION_X = {"0": -70, "2": 120, "3": 430, "4": 648, "5": 742, "9": 1000}
COMPONENTS = [
    ("Inlet", 55, "Diffuses the incoming air, slowing it and raising its pressure ahead of the compressor."),
    ("Compressor", 270, "Eight axial stages, each a rotor then a stator, raise the pressure about twelvefold."),
    ("Combustor", 560, "Fuel burns inside an annular liner; air outside the liner cools it and enters through dilution holes."),
    ("Turbine", 695, "Two stages extract just enough work from the hot gas to drive the compressor on the shared shaft."),
    ("Nozzle", 880, "The convergent nozzle accelerates the remaining hot gas into the thrust-producing jet."),
]


def blade(x: float, width: float, lean: float, cls: str, sign: int) -> str:
    """One blade row, hub to tip, as a leaned quadrilateral."""
    rh0, rt0 = interp(HUB, x) + 1, interp(TIP, x) - 2
    rh1, rt1 = interp(HUB, x + width) + 1, interp(TIP, x + width) - 2
    pts = [(x, rh0), (x + lean, rt0), (x + width + lean, rt1), (x + width, rh1)]
    d = " ".join(f"{px(a):.1f},{AXIS + sign * r:.1f}" for a, r in pts)
    return f'<polygon class="{cls}" points="{d}"/>'


def band(outer: list, inner: list, sign: int) -> str:
    """Closed path between two (x, r) profiles, on one side of the axis."""
    o0, i_rev = outer[0], list(reversed(inner))
    return (f"M{px(o0[0]):.1f},{AXIS + sign * o0[1]:.1f} {smooth(outer, sign)} "
            f"L{px(i_rev[0][0]):.1f},{AXIS + sign * i_rev[0][1]:.1f} {smooth(i_rev, sign)} Z")


def build_turbojet() -> dict:
    res = run_turbojet_simulation(TurbojetInput()).model_dump()
    table = {str(k): v for k, v in res["station_table"].items()}   # keys are ints in the model
    temps = {k: v["stagnation_temperature_K"] for k, v in table.items()}
    pres = {k: v["stagnation_pressure_Pa"] for k, v in table.items()}
    t_lo, t_hi = min(temps.values()), max(temps.values())
    p_lo, p_hi = math.log(min(pres.values())), math.log(max(pres.values()))

    # Gradient stops along the gas path. Inside the combustor the temperature rises from
    # T3 at the dome to T4 at the turbine inlet; elsewhere it is held at the station value.
    t_prof = [(-80, temps["0"]), (120, temps["2"]), (430, temps["3"]), (480, temps["3"]),
              (640, temps["4"]), (648, temps["4"]), (742, temps["5"]), (1000, temps["9"])]
    p_prof = [(-80, pres["0"]), (120, pres["2"]), (430, pres["3"]), (640, pres["4"]),
              (742, pres["5"]), (1000, pres["9"])]

    def gradient(gid: str, prof, norm, cmap) -> str:
        stops = "".join(
            f'<stop offset="{(px(x) - px(-80)) / (px(1000) - px(-80)):.4f}" '
            f'stop-color="{lerp_color(cmap, norm(v))}"/>' for x, v in prof)
        return (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{px(-80):.0f}" '
                f'y1="0" x2="{px(1000):.0f}" y2="0">{stops}</linearGradient>')

    tnorm = lambda t: (t - t_lo) / (t_hi - t_lo)
    pnorm = lambda p: (math.log(p) - p_lo) / (p_hi - p_lo)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
             f'aria-labelledby="tj-title tj-desc" class="engine-section">',
             '<title id="tj-title">Turbojet cross-section</title>',
             '<desc id="tj-desc">Side cross-section of a single-spool turbojet: inlet, eight-stage '
             'axial compressor, annular combustor, two-stage turbine and convergent nozzle, with '
             'the gas path coloured by stagnation temperature from the PropulsionLab cycle solver.</desc>',
             "<defs>",
             gradient("grad-temp", t_prof, tnorm, TEMP_MAP),
             gradient("grad-pres", p_prof, pnorm, PRES_MAP),
             '<pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" '
             'patternTransform="rotate(45)"><rect width="7" height="7" class="metal-fill"/>'
             '<line x1="0" y1="0" x2="0" y2="7" class="hatch-line"/></pattern>',
             '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
             'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="arrow-head"/></marker>',
             "</defs>"]

    # Freestream arrows and centreline.
    for dy in (-110, 0, 110):
        parts.append(f'<line class="freestream" x1="{px(-100):.0f}" y1="{AXIS + dy}" '
                     f'x2="{px(-30):.0f}" y2="{AXIS + dy}" marker-end="url(#arrow)"/>')
    parts.append(f'<line class="centreline" x1="{px(-100):.0f}" y1="{AXIS}" x2="{px(1080):.0f}" y2="{AXIS}"/>')

    for sign in (-1, 1):
        # Gas path (coloured), then blades, liner, casing and hub on top.
        # Close the gas path along the inlet face (x = 0) rather than diagonally from the lip
        # to the spinner tip.
        gas = band(TIP, HUB, sign).replace(" Z", f" L{px(0):.1f},{AXIS:.1f} Z")
        parts.append(f'<path class="gas" d="{gas}"/>')
        for x0 in COMP_STAGES:
            parts.append(blade(x0, 13, 4, "blade rotor", sign))
            parts.append(blade(x0 + 18, 10, -3, "blade stator", sign))
        for x0, kind in TURB_ROWS:
            parts.append(blade(x0, 14, -5 if kind == "stator" else 5, f"blade turbine {kind}", sign))
        # Combustor liner: dome at x=482, walls to the turbine nozzle guide vanes.
        lo = [(482, 146), (520, 148), (600, 144), (646, 130)]
        li = [(482, 86), (520, 84), (600, 86), (646, 91)]
        d_liner = (f"M{px(646):.1f},{AXIS + sign * 130:.1f} " + smooth(list(reversed(lo)), sign)
                   + f" Q{px(466):.1f},{AXIS + sign * 116:.1f} {px(482):.1f},{AXIS + sign * 86:.1f} "
                   + smooth(li, sign))
        parts.append(f'<path class="liner" d="{d_liner}"/>')
        for x in (535, 565, 595):   # dilution holes
            for r in (interp(lo, x) + 1, interp(li, x) - 1):
                parts.append(f'<circle class="dilution" cx="{px(x):.1f}" cy="{AXIS + sign * r:.1f}" r="2.6"/>')
        # Fuel injector through the casing to the dome, with a spray cone.
        parts.append(f'<path class="injector" d="M{px(470):.1f},{AXIS + sign * 186:.1f} '
                     f'L{px(470):.1f},{AXIS + sign * 128:.1f} L{px(484):.1f},{AXIS + sign * 116:.1f}"/>')
        parts.append(f'<path class="spray" d="M{px(486):.1f},{AXIS + sign * 116:.1f} '
                     f'L{px(520):.1f},{AXIS + sign * 104:.1f} M{px(486):.1f},{AXIS + sign * 116:.1f} '
                     f'L{px(520):.1f},{AXIS + sign * 128:.1f}"/>')
        # Casing (cut metal, hatched) with a rounded inlet lip.
        casing = (f"M{px(0):.1f},{AXIS + sign * 141:.1f} "
                  f"Q{px(-9):.1f},{AXIS + sign * 147:.1f} {px(0):.1f},{AXIS + sign * 153:.1f} "
                  + smooth(SKIN, sign)
                  + f" L{px(1000):.1f},{AXIS + sign * 106:.1f} " + smooth(list(reversed(TIP)), sign) + " Z")
        parts.append(f'<path class="metal" d="{casing}"/>')
        # Hub: spinner, compressor drum, inner combustor casing, turbine disc, tail cone.
        hub = (f"M{px(HUB[0][0]):.1f},{AXIS:.1f} " + smooth(HUB, sign) + " Z")
        parts.append(f'<path class="metal hub" d="{hub}"/>')

    # Shaft and bearings, drawn once across the axis (visible through the hatched hub).
    parts.append(f'<rect class="shaft" x="{px(135):.1f}" y="{AXIS - 11}" width="{px(725) - px(135):.1f}" height="22" rx="4"/>')
    for x in (140, 722):
        parts.append(f'<circle class="bearing" cx="{px(x):.1f}" cy="{AXIS}" r="9"/>')

    # Component labels with leader lines (hover target carries the explanation).
    for name, x, text in COMPONENTS:
        top = AXIS - interp(SKIN, x) - 6
        parts.append(
            f'<g class="component" tabindex="0" data-name="{name}" data-text="{text}">'
            f'<line class="leader" x1="{px(x):.1f}" y1="44" x2="{px(x):.1f}" y2="{top:.1f}"/>'
            f'<text class="label" x="{px(x):.1f}" y="36" text-anchor="middle">{name}</text></g>')

    # Station markers below the engine, carrying the solver values.
    for key, x in STATION_X.items():
        s = table[key]
        bottom = AXIS + (interp(SKIN, x) if 0 <= x <= 1000 else 60) + 8
        parts.append(
            f'<g class="station" tabindex="0" data-station="{key}" data-name="{s["name"]}" '
            f'data-t0="{s["stagnation_temperature_K"]:.1f}" data-p0="{s["stagnation_pressure_Pa"]:.0f}">'
            f'<line class="station-line" x1="{px(x):.1f}" y1="{AXIS - 30 if x < 0 else AXIS}" '
            f'x2="{px(x):.1f}" y2="{H - 50}"/>'
            f'<circle class="station-dot" cx="{px(x):.1f}" cy="{H - 34}" r="13"/>'
            f'<text class="station-num" x="{px(x):.1f}" y="{H - 29.5}" text-anchor="middle">{key}</text></g>')
    parts.append("</svg>")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "turbojet.svg").write_text("\n".join(parts), encoding="utf-8")
    meta = {
        "operating_point": {"altitude_m": 10000, "mach": 0.8, "compressor_pressure_ratio": 12,
                            "turbine_inlet_temperature_K": 1400},
        "thrust_kN": res["thrust_kN"], "TSFC_kg_per_kN_hr": res["TSFC_kg_per_kN_hr"],
        "exit_velocity_m_s": res["exit_velocity_m_s"],
        "temperature_range_K": [t_lo, t_hi], "pressure_range_Pa": [min(pres.values()), max(pres.values())],
        "temp_colormap": TEMP_MAP, "pres_colormap": PRES_MAP,
    }
    (OUT / "turbojet.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    print(json.dumps(build_turbojet(), indent=2))
