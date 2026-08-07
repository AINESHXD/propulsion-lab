"""Regenerate ``app/data/validation_cases.json`` from certified engine data.

This script exists so the validation library's provenance is reproducible
rather than asserted. It copies published quantities only — bypass ratio,
overall pressure ratio, rated sea-level-static thrust and takeoff fuel flow —
and derives reference TSFC arithmetically from the last two. Nothing is
estimated, smoothed or hand-edited on the way through.

Usage
-----
The source table is the OpenAP engine database (TU Delft, LGPL-3.0), itself
derived from the ICAO Aircraft Engine Emissions Databank. It is deliberately
*not* vendored into this MIT-licensed repository; fetch it first::

    curl -sLo engines.csv https://raw.githubusercontent.com/\
TUDelft-CNS-ATM/openap/master/openap/data/engine/engines.csv
    python scripts/build_validation_set.py engines.csv

Each case keeps its ICAO engine UID, so every figure in the generated file can
be checked against the primary source without going through OpenAP at all.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "validation_cases.json"

# One representative per engine family, chosen to span bypass ratio, overall
# pressure ratio and four decades of design practice — not to flatter the model.
WANTED = [
    "1PW002",   # JT3D-7             1960s low bypass
    "8RR043",   # SPEY Mk511         1960s low bypass
    "1PW007",   # JT8D-9             1960s low bypass
    "1PW038",   # JT15D-5C           small business-jet turbofan
    "1AS002",   # TFE731-3           small geared business-jet turbofan
    "4PW071",   # JT8D-219           refanned JT8D
    "3RR033",   # TAY 651
    "6BR010",   # BR700-710C4-11
    "10AL026",  # AE3007A2
    "1GE034",   # CF34-3A
    "1CM005",   # CFM56-3B-2         1980s
    "3CM032",   # CFM56-7B24         1990s
    "3CM020",   # CFM56-5B1/2P
    "1IA001",   # V2500-A1
    "10IA013",  # V2527-A5
    "1PW030",   # JT9D-7R4H1         widebody, 1970s
    "1RR011",   # RB211-524H
    "1PW042",   # PW4056
    "4PW072",   # PW2037
    "2GE038",   # CF6-80C2A3
    "14RR071",  # Trent 772
    "5RR040",   # Trent 895
    "9GE126",   # GE90-85B
    "17GE179",  # GEnx-1B76/P2       2010s very high bypass
    "20CM090",  # LEAP-1A            2010s very high bypass
    "18PW125",  # PW1133GA-JM        geared turbofan, highest bypass here
]

G_PER_N_S_TO_SI = 1.0e-3   # cruise SFC column is g/(N s)


def build(src: Path) -> dict:
    rows = {r["uid"]: r for r in csv.DictReader(src.open(encoding="utf-8"))}
    missing = [uid for uid in WANTED if uid not in rows]
    if missing:
        raise SystemExit(f"source table is missing engine UIDs: {missing}")

    cases = []
    for uid in WANTED:
        r = rows[uid]
        thrust_N = float(r["max_thrust"])
        ff_to = float(r["ff_to"])
        case = {
            "icao_uid": uid,
            "name": r["name"],
            "manufacturer": r["manufacturer"],
            "engine_type": r["type"],
            # published inputs
            "bypass_ratio": float(r["bpr"]),
            "overall_pressure_ratio": float(r["pr"]),
            # published reference outputs, sea-level static takeoff
            "rated_thrust_N": thrust_N,
            "fuel_flow_takeoff_kg_s": ff_to,
            "reference_tsfc_kg_per_N_s": ff_to / thrust_N,
        }
        if r["cruise_sfc"]:
            case["cruise"] = {
                "mach": float(r["cruise_mach"]),
                "altitude_ft": float(r["cruise_alt"]),
                "reference_tsfc_kg_per_N_s": float(r["cruise_sfc"]) * G_PER_N_S_TO_SI,
            }
        cases.append(case)

    cases.sort(key=lambda c: c["bypass_ratio"])
    return {
        "source_note": (
            "Reference figures are the certified sea-level-static takeoff rating "
            "and fuel flow from the ICAO Aircraft Engine Emissions Databank, "
            "reached via the OpenAP engine table (TU Delft, LGPL-3.0). Each case "
            "keeps its ICAO engine UID so every number here can be checked "
            "against the primary source. Bypass ratio and overall pressure ratio "
            "are published inputs. Reference TSFC is derived arithmetically as "
            "fuel flow divided by rated thrust — it is not a PropulsionLab "
            "output and is not tuned. Nothing in this file is estimated: any "
            "quantity the databank does not publish (turbine inlet temperature, "
            "component efficiencies, mass flow) is supplied by the validation "
            "harness as a single fixed assumption set applied identically to "
            "every engine, never fitted per engine."
        ),
        "primary_source": (
            "ICAO Aircraft Engine Emissions Databank, "
            "https://www.easa.europa.eu/en/domains/environment/"
            "icao-aircraft-engine-emissions-databank"
        ),
        "intermediary_source": (
            "OpenAP engine table, https://github.com/TUDelft-CNS-ATM/openap "
            "(LGPL-3.0). Used to read the databank in machine-readable form; no "
            "OpenAP code or file is redistributed here."
        ),
        "regenerate_with": "python scripts/build_validation_set.py engines.csv",
        "units": {
            "rated_thrust_N": "newtons, sea-level static",
            "fuel_flow_takeoff_kg_s": "kg/s at 100% rated thrust",
            "reference_tsfc_kg_per_N_s": "kg per newton-second",
        },
        "cases": cases,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = build(Path(sys.argv[1]))
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(doc['cases'])} cases -> {OUT}")


if __name__ == "__main__":
    main()
