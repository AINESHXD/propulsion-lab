#!/usr/bin/env python3
"""Static long-form case-study page generator (Days 27-28).

Renders one crawlable HTML page per engine into ``app/static/case-studies/``
from the CONTENT dataset below. Original technical prose; every numeric figure
is public-estimated / approximate and labelled as such. Re-run after editing
content:  ``python build_case_studies.py``
"""

from __future__ import annotations

import html
from pathlib import Path

CACHE = "20260530-cs28"

_BRAND = (
    '<a class="brand" href="/lab/" aria-label="DAS LABS · PropulsionLab">'
    '<span class="brand-mark">DAS&nbsp;LABS</span></a>'
)
OUT_DIR = Path(__file__).resolve().parent / "app" / "static" / "case-studies"

# Engines whose long-form pages exist, in narrative order (used for the index,
# cross-links, and the render loop). Day 28 completes the set of ten.
LIVE_IDS = [
    "jt8d", "cf6", "pw4000", "v2500", "cfm56",
    "ge90", "genx", "leap", "gtf", "trentxwb",
]

CONTENT: dict[str, dict] = {
    "jt8d": {
        "name": "Pratt & Whitney JT8D",
        "maker": "Pratt & Whitney",
        "family": "Low-bypass turbofan",
        "eis": "1964",
        "bypass": "≈ 1.0 – 1.7",
        "opr": "≈ 16 – 21",
        "thrust": "62 – 96 kN",
        "fan": "≈ 1.0 m",
        "spools": "2-spool",
        "applications": "Boeing 727, 737-100/-200 · Douglas DC-9 · McDonnell Douglas MD-80",
        "meta": "The Pratt & Whitney JT8D low-bypass turbofan: architecture, cycle, "
                "and why it became the workhorse of the early jet age.",
        "lede": "The engine that made the short- and medium-haul jetliner economic. "
                "A rugged low-bypass turbofan, the JT8D was for two decades the most "
                "common commercial jet engine in the Western world.",
        "sections": [
            ("Architecture", [
                "The JT8D is a two-spool low-bypass turbofan derived from the J52 "
                "turbojet that powered the A-6 Intruder. A two-stage front fan "
                "pressurises a bypass duct whose bypass ratio sits near unity — so "
                "unlike a modern high-bypass fan, the hot core jet still produces "
                "most of the thrust.",
                "Core and bypass streams are not exhausted separately. They mix in a "
                "long common cowl ahead of a single convergent nozzle, the classic "
                "low-bypass mixed-flow layout. The low-pressure spool carries the fan "
                "and the rear (low-pressure) turbine stages; the high-pressure spool "
                "carries the high-pressure compressor and the first turbine stages.",
            ]),
            ("The cycle", [
                "By the standards of a modern engine the JT8D runs a modest cycle: an "
                "overall pressure ratio of roughly 16–21 and comparatively cool "
                "turbine temperatures. That keeps the thermal efficiency — and the "
                "fuel economy — well below today's engines, and the near-unity bypass "
                "ratio means a fast, hot exhaust jet that is inherently loud.",
                "Those two facts framed the JT8D's later life. The -200 series 'refan' "
                "raised the bypass ratio to improve fuel burn and noise, and external "
                "hush-kits were retrofitted to chase tightening community-noise rules "
                "into the 1990s.",
            ]),
            ("Engineering significance", [
                "The JT8D's importance is sheer volume and durability. More than "
                "14,000 were built — for a long stretch the most-produced commercial "
                "turbofan anywhere — and the engine earned a reputation for taking "
                "abuse and staying on-wing. It was the powerplant that turned the jet "
                "from a long-haul luxury into everyday transport.",
            ]),
        ],
    },
    "v2500": {
        "name": "IAE V2500",
        "maker": "International Aero Engines",
        "family": "High-bypass turbofan",
        "eis": "1989",
        "bypass": "≈ 4.6",
        "opr": "≈ 33",
        "thrust": "98 – 147 kN",
        "fan": "≈ 1.6 m",
        "spools": "2-spool",
        "applications": "Airbus A320 family · McDonnell Douglas MD-90",
        "meta": "The IAE V2500 high-bypass turbofan: a five-nation consortium engine "
                "and the A320's efficient alternative to the CFM56.",
        "lede": "A clean, efficient high-bypass turbofan built by a five-nation "
                "consortium — and for three decades the A320 family's other engine "
                "choice alongside the CFM56.",
        "sections": [
            ("Architecture", [
                "The V2500 is a two-spool high-bypass turbofan from International Aero "
                "Engines, a consortium of Pratt & Whitney, Rolls-Royce, Japanese Aero "
                "Engines and German and Italian partners. It pairs a wide-chord fan "
                "with a high-pressure-ratio high-pressure compressor — the source of "
                "much of its efficiency for the thrust class.",
                "A bypass ratio near 4.6 and an overall pressure ratio around 33 place "
                "it squarely in the modern single-aisle bracket: most thrust now comes "
                "from the cool, efficient bypass stream rather than the core jet.",
            ]),
            ("The cycle", [
                "The V2500's calling card was a notably efficient HP core. A high "
                "compressor pressure ratio raises the thermal efficiency, and the "
                "engine became known for low cruise fuel burn and long on-wing life — "
                "the metrics that matter most to a narrowbody operator flying many "
                "short cycles a day.",
            ]),
            ("Engineering significance", [
                "On the A320 the V2500 went head-to-head with the CFM56, and the two "
                "split the market for two decades. Beyond the sales contest, the "
                "consortium's HP-core experience fed directly into Pratt & Whitney's "
                "thinking on the geared turbofan that would eventually follow.",
            ]),
        ],
    },
    "cfm56": {
        "name": "CFM56-5B / -7B",
        "maker": "CFM International (GE + Safran)",
        "family": "High-bypass turbofan",
        "eis": "1996",
        "bypass": "≈ 5.0 – 5.5",
        "opr": "≈ 32 – 38",
        "thrust": "97 – 142 kN",
        "fan": "≈ 1.55 – 1.73 m",
        "spools": "2-spool",
        "applications": "Airbus A320 family · Boeing 737 Classic / NG",
        "meta": "The CFM56 — the best-selling jet engine in history. Its two-spool "
                "architecture, cycle and the GE-Safran partnership behind it.",
        "lede": "The best-selling jet engine in history. The CFM56 powered the "
                "narrowbody market for three decades and proved the GE-Safran "
                "partnership that went on to build the LEAP.",
        "sections": [
            ("Architecture", [
                "The CFM56 is a two-spool high-bypass turbofan that grafts GE's F101 "
                "core — developed for the B-1 bomber — onto a Snecma (now Safran) "
                "low-pressure system. A single fan and booster sit on the LP shaft; a "
                "nine-stage high-pressure compressor, annular combustor and cooled "
                "high-pressure turbine make up the core.",
                "The combustor was offered in single-annular form and, on later "
                "low-emissions variants, a dual-annular configuration to cut NOₓ. "
                "Bypass ratio sits around 5 and the overall pressure ratio climbed "
                "steadily across the -5B and -7B variants as the family matured.",
            ]),
            ("The cycle", [
                "The CFM56's success was as much about robustness as raw efficiency. A "
                "conservative, well-understood cycle gave long on-wing life and low "
                "maintenance cost — exactly what a narrowbody operator values — while "
                "incremental pressure-ratio and material improvements kept fuel burn "
                "competitive across a thirty-year production run.",
            ]),
            ("Engineering significance", [
                "Tens of thousands of CFM56s were built, making it the best-selling "
                "jet engine ever produced. Just as important, it was the proving "
                "ground for CFM International — the GE-Safran joint venture — whose "
                "next engine, the LEAP, would inherit the narrowbody crown.",
            ]),
        ],
    },
    "leap": {
        "name": "CFM LEAP-1A / -1B",
        "maker": "CFM International (GE + Safran)",
        "family": "High-bypass turbofan",
        "eis": "2016",
        "bypass": "≈ 9 – 11",
        "opr": "≈ 40 – 50",
        "thrust": "100 – 156 kN",
        "fan": "≈ 1.76 – 1.98 m",
        "spools": "2-spool",
        "applications": "Airbus A320neo · Boeing 737 MAX",
        "meta": "The CFM LEAP turbofan: woven carbon-fibre fan blades, ceramic-matrix "
                "composites and a ~15% fuel-burn gain over the CFM56.",
        "lede": "The CFM56's successor and a showcase of aerospace materials: woven "
                "carbon-fibre fan blades, ceramic-matrix composites in the hot "
                "section, and roughly 15% better fuel burn.",
        "sections": [
            ("Architecture", [
                "The LEAP keeps the proven two-spool layout but rebuilds it in modern "
                "materials. Its fan blades are three-dimensionally woven carbon-fibre, "
                "made by resin transfer moulding, so the fan can grow larger and "
                "lighter and push the bypass ratio toward 11 without a weight penalty.",
                "In the hot section, ceramic-matrix-composite (CMC) shrouds tolerate "
                "higher turbine temperatures than nickel alloys, and a higher overall "
                "pressure ratio lifts thermal efficiency. A Twin-Annular Pre-Swirl "
                "(TAPS) combustor keeps NOₓ low at those temperatures.",
            ]),
            ("The cycle", [
                "Higher bypass ratio improves propulsive efficiency; higher pressure "
                "ratio and turbine temperature improve thermal efficiency. The LEAP "
                "pushes both at once, which is why it delivers about 15% lower fuel "
                "burn than the CFM56 it replaces, with lower emissions.",
            ]),
            ("Engineering significance", [
                "The LEAP is now one of the two dominant powerplants on the latest "
                "single-aisle jets, sharing that market with Pratt & Whitney's geared "
                "turbofan. It marks the point where composites and ceramics moved from "
                "exotic to mainstream in a high-volume commercial engine.",
            ]),
        ],
    },
    "gtf": {
        "name": "Pratt & Whitney GTF (PW1000G)",
        "maker": "Pratt & Whitney",
        "family": "Geared high-bypass turbofan",
        "eis": "2016",
        "bypass": "≈ 9 – 12",
        "opr": "≈ 40 – 50",
        "thrust": "67 – 156 kN",
        "fan": "≈ 1.42 – 2.06 m",
        "spools": "2-spool + reduction gear",
        "applications": "Airbus A320neo · Airbus A220 · Embraer E-Jets E2",
        "meta": "The Pratt & Whitney geared turbofan (PW1000G): how a reduction "
                "gearbox lets the fan and low-pressure spool each run at its optimum.",
        "lede": "The defining efficiency idea of the 2010s narrowbody generation: a "
                "reduction gearbox that lets the fan turn slowly and the low-pressure "
                "spool turn fast, each near its own aerodynamic optimum.",
        "sections": [
            ("Architecture", [
                "A planetary reduction gearbox of roughly 3:1 sits between the fan and "
                "the low-pressure spool. A large fan is most efficient turning slowly; "
                "a low-pressure compressor and turbine are most efficient turning "
                "fast. In a conventional engine they are locked to the same shaft and "
                "neither gets its wish. The gear decouples them.",
                "Because the LP spool can now spin fast, it needs far fewer compressor "
                "and turbine stages, cutting part count and weight, while the slow fan "
                "can be large for a high bypass ratio and quiet operation.",
            ]),
            ("The cycle", [
                "The pay-off is a double-digit fuel-burn improvement at entry, plus a "
                "marked noise reduction from the slow fan tip speed. The engineering "
                "price is a heavily loaded gearbox that must transmit tens of "
                "thousands of horsepower and shed significant heat reliably — the "
                "focus of much of the programme's early service experience.",
            ]),
            ("Engineering significance", [
                "The geared turbofan reopened a design space the industry had largely "
                "set aside, and proved a gearbox could be made durable at large-engine "
                "power levels. It now competes directly with the LEAP across the "
                "single-aisle and regional-jet market.",
            ]),
        ],
    },
    "cf6": {
        "name": "General Electric CF6",
        "maker": "General Electric",
        "family": "High-bypass turbofan",
        "eis": "1971",
        "bypass": "≈ 4.3 – 5.3",
        "opr": "≈ 28 – 32",
        "thrust": "227 – 320 kN",
        "fan": "≈ 2.2 – 2.7 m",
        "spools": "2-spool",
        "applications": "Boeing 747 · 767 · Airbus A300 / A310 / A330 · "
                        "McDonnell Douglas DC-10 / MD-11",
        "meta": "The General Electric CF6 high-bypass turbofan: the civil engine "
                "derived from the C-5 Galaxy's TF39 that put GE into the widebody era.",
        "lede": "The engine that took GE from the military into the heart of the "
                "widebody market. Derived from the TF39 that powered the C-5 Galaxy, "
                "the CF6 spent five decades under the wings of nearly every long-haul "
                "twin and tri-jet.",
        "sections": [
            ("Architecture", [
                "The CF6 is a two-spool high-bypass turbofan whose lineage runs back to "
                "the TF39, the first large high-bypass engine, built for the C-5 "
                "military transport. A single large fan on the low-pressure spool feeds "
                "the bypass duct; a high-pressure compressor, annular combustor and "
                "air-cooled high-pressure turbine make up the core.",
                "Across the -6, -50, -80A, -80C2 and -80E1 variants the family grew its "
                "fan, raised its pressure ratio and climbed in thrust, but the basic "
                "two-spool widebody layout stayed constant — a textbook example of "
                "stretching one sound architecture across a generation of aircraft.",
            ]),
            ("The cycle", [
                "By widebody standards the CF6 ran a moderate, robust cycle: a bypass "
                "ratio in the four-to-five range and an overall pressure ratio near "
                "thirty. That balance favoured durability and predictable maintenance "
                "over chasing the last percentage point of fuel burn, which suited the "
                "long-haul operators that flew it hardest.",
                "Successive variants lifted the core pressure ratio and turbine "
                "temperature as materials improved, keeping the engine competitive long "
                "after its 1971 debut.",
            ]),
            ("Engineering significance", [
                "The CF6 established General Electric as a first-rank supplier of large "
                "commercial engines and seeded the core technology GE would carry into "
                "the CFM56 and, later, the GE90. Its long production run and broad "
                "airframe coverage made it one of the most widely flown widebody "
                "engines ever built.",
            ]),
        ],
    },
    "pw4000": {
        "name": "Pratt & Whitney PW4000",
        "maker": "Pratt & Whitney",
        "family": "High-bypass turbofan",
        "eis": "1987",
        "bypass": "≈ 4.8 – 6.4",
        "opr": "≈ 27 – 35",
        "thrust": "222 – 436 kN",
        "fan": "≈ 2.4 – 2.8 m",
        "spools": "2-spool",
        "applications": "Boeing 747-400 · 767 · 777 · Airbus A300 / A310 / A330 · MD-11",
        "meta": "The Pratt & Whitney PW4000 family: three fan sizes spanning the "
                "widebody market and the successor to the JT9D.",
        "lede": "Pratt & Whitney's widebody mainstay of the 1990s. Built in three fan "
                "diameters from one design philosophy, the PW4000 succeeded the JT9D "
                "and powered almost every long-haul airframe of its era.",
        "sections": [
            ("Architecture", [
                "The PW4000 is a two-spool high-bypass turbofan offered in three fan "
                "sizes — nominally 94, 100 and 112 inches — each tuned to a different "
                "thrust class. The smallest serves the 767 and A310; the largest, with "
                "a fan well over two and a half metres across, was developed for the "
                "Boeing 777.",
                "It succeeded the JT9D and was among the early civil engines designed "
                "around full-authority digital engine control (FADEC), which sharpened "
                "fuel scheduling and protection across the flight envelope.",
            ]),
            ("The cycle", [
                "Spanning such a wide thrust range meant the family covered a broad band "
                "of bypass and pressure ratios. The larger-fan members pushed bypass "
                "ratio up for better cruise efficiency on long sectors, while the whole "
                "family leaned on Pratt & Whitney's core experience to keep on-wing "
                "life long.",
            ]),
            ("Engineering significance", [
                "The PW4000 kept Pratt & Whitney competitive across the entire widebody "
                "market through the 1990s and 2000s, and the 112-inch variant put the "
                "company on the 777 alongside the GE90 and the Trent 800 — a three-way "
                "contest that pushed all three manufacturers' large-fan technology "
                "forward.",
            ]),
        ],
    },
    "ge90": {
        "name": "General Electric GE90",
        "maker": "General Electric",
        "family": "High-bypass turbofan",
        "eis": "1995",
        "bypass": "≈ 8 – 9",
        "opr": "≈ 40 – 42",
        "thrust": "330 – 510 kN",
        "fan": "≈ 3.1 – 3.4 m",
        "spools": "2-spool",
        "applications": "Boeing 777",
        "meta": "The General Electric GE90: the most powerful turbofan ever certified, "
                "and the first airliner engine with carbon-fibre composite fan blades.",
        "lede": "The most powerful jet engine ever flown, and the one that made "
                "composite fan blades mainstream. Built exclusively for the Boeing 777, "
                "the GE90 set a thrust record that still stands.",
        "sections": [
            ("Architecture", [
                "The GE90 is a two-spool high-bypass turbofan built around an enormous "
                "fan — over three metres in diameter on the largest variant. Its "
                "defining innovation was the fan blade itself: swept, wide-chord and "
                "made of carbon-fibre composite rather than titanium, a first for a "
                "commercial engine and the technology that let the fan grow so large "
                "without becoming impossibly heavy.",
                "Behind the fan sits a high-pressure-ratio core with an advanced "
                "high-pressure compressor and a cooled high-pressure turbine, giving an "
                "overall pressure ratio around forty and a bypass ratio approaching "
                "nine.",
            ]),
            ("The cycle", [
                "A very high bypass ratio gives the GE90 excellent propulsive "
                "efficiency, while the high overall pressure ratio lifts thermal "
                "efficiency — the combination behind its strong long-haul fuel economy. "
                "The largest member, the GE90-115B, is certified above 110,000 pounds "
                "of thrust, a level no other turbofan has matched.",
            ]),
            ("Engineering significance", [
                "The GE90 proved that composite fan blades could be safe, durable and "
                "manufacturable at scale, a lesson that flowed directly into the GEnx "
                "and LEAP. As the exclusive engine on the 777-300ER and 777-200LR, it "
                "also tied one of the most successful long-haul twins to a single "
                "powerplant family.",
            ]),
        ],
    },
    "genx": {
        "name": "General Electric GEnx",
        "maker": "General Electric",
        "family": "High-bypass turbofan",
        "eis": "2011",
        "bypass": "≈ 8 – 9.6",
        "opr": "≈ 40 – 58",
        "thrust": "296 – 339 kN",
        "fan": "≈ 2.66 – 2.82 m",
        "spools": "2-spool",
        "applications": "Boeing 787 Dreamliner · 747-8",
        "meta": "The General Electric GEnx: composite fan and fan case, a TAPS "
                "low-emissions combustor, and the bleedless engine of the 787.",
        "lede": "The GE90's technology distilled into a lighter, cleaner engine for the "
                "787 and 747-8. The GEnx carried composites further, added a "
                "low-emissions combustor, and dropped engine bleed air entirely on the "
                "Dreamliner.",
        "sections": [
            ("Architecture", [
                "The GEnx is a two-spool high-bypass turbofan that takes the GE90's "
                "composite fan blades and goes a step further, making the fan case from "
                "composite as well to save weight. The fan blade count is reduced "
                "relative to earlier large fans, easing manufacture and maintenance.",
                "Its combustor is the Twin-Annular Pre-Swirl (TAPS) design, which mixes "
                "fuel and air more thoroughly to cut oxides of nitrogen at high "
                "pressure-ratio conditions. On the 787 the engine runs a 'bleedless' "
                "architecture: cabin air comes from electric compressors rather than "
                "engine bleed, so the core is optimised without that off-take.",
            ]),
            ("The cycle", [
                "A high bypass ratio and a high overall pressure ratio — among the "
                "highest in service on the 787 variant — combine for a marked fuel-burn "
                "improvement over the previous widebody generation, with lower noise and "
                "emissions to match.",
            ]),
            ("Engineering significance", [
                "The GEnx made all-composite fan modules and bleedless operation routine "
                "on a high-volume widebody, and became one of the two engine choices on "
                "the 787 while powering the final passenger 747. It is the bridge "
                "between the record-setting GE90 and the high-volume LEAP.",
            ]),
        ],
    },
    "trentxwb": {
        "name": "Rolls-Royce Trent XWB",
        "maker": "Rolls-Royce",
        "family": "High-bypass turbofan",
        "eis": "2015",
        "bypass": "≈ 9.3",
        "opr": "≈ 50",
        "thrust": "330 – 432 kN",
        "fan": "≈ 3.0 m",
        "spools": "3-spool",
        "applications": "Airbus A350 XWB",
        "meta": "The Rolls-Royce Trent XWB: the three-spool architecture explained, and "
                "the most efficient large civil engine in service at its launch.",
        "lede": "Rolls-Royce's three-spool answer for the Airbus A350. At entry the "
                "most efficient large civil engine flying, the Trent XWB showcases an "
                "architecture no other manufacturer uses at this scale.",
        "sections": [
            ("Architecture", [
                "The Trent XWB is a three-spool high-bypass turbofan — the Rolls-Royce "
                "signature. Where GE and Pratt & Whitney use two concentric shafts, "
                "Rolls splits the compression across three: a fan on the low-pressure "
                "spool, a separate intermediate-pressure compressor and turbine, and a "
                "high-pressure spool. Each spool can run nearer its own optimum speed.",
                "The reward is shorter, stiffer shafts and fewer compressor stages for a "
                "given pressure ratio; the price is mechanical complexity and a third "
                "set of bearings. The XWB pairs this with a roughly three-metre fan and "
                "an overall pressure ratio around fifty.",
            ]),
            ("The cycle", [
                "A bypass ratio near nine and a high overall pressure ratio give the "
                "Trent XWB excellent cruise efficiency, and at service entry Rolls-Royce "
                "could claim it as the most efficient large civil engine in operation. "
                "The three-spool layout lets the intermediate and high-pressure "
                "compressors each turn at a speed that keeps their stages aerodynamically "
                "well matched.",
            ]),
            ("Engineering significance", [
                "As the sole engine for the Airbus A350 XWB, the Trent XWB is central to "
                "one of the most successful modern widebodies. It is also the clearest "
                "in-service demonstration of the three-spool philosophy that "
                "distinguishes Rolls-Royce's large engines from its American "
                "competitors.",
            ]),
        ],
    },
}


def _spec_items(c: dict) -> str:
    rows = [
        ("Family", c["family"]),
        ("Bypass ratio", c["bypass"]),
        ("Overall PR", c["opr"]),
        ("Max thrust", c["thrust"]),
        ("Fan diameter", c["fan"]),
        ("Entered service", c["eis"]),
    ]
    return "".join(
        f"<div><dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd></div>" for k, v in rows
    )


def _sections(c: dict) -> str:
    out = []
    for heading, paragraphs in c["sections"]:
        out.append(f"<h2>{html.escape(heading)}</h2>")
        out.extend(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    out.append("<h2>Applications</h2>")
    out.append(f"<p>{html.escape(c['applications'])}</p>")
    return "\n      ".join(out)


def _related(engine_id: str) -> str:
    links = []
    for other in LIVE_IDS:
        if other == engine_id:
            continue
        links.append(
            f'<a href="/lab/case-studies/{other}.html">{html.escape(CONTENT[other]["name"])}</a>'
        )
    return "".join(links)


def render(engine_id: str, c: dict) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#08090b" />
    <meta name="description" content="{html.escape(c['meta'])}" />
    <title>{html.escape(c['name'])} — PropulsionLab case study</title>
    <link rel="stylesheet" href="/lab/styles.css?v={CACHE}" />
    <link rel="stylesheet" href="/lab/case-study.css?v={CACHE}" />
  </head>
  <body>
    <header class="cs-page-bar">
      {_BRAND}
      <nav class="cs-page-nav">
        <a href="/lab/">Console</a>
      </nav>
    </header>
    <article class="cs-article">
      <p class="eyebrow">{html.escape(c['maker'])} · Case study</p>
      <h1>{html.escape(c['name'])}</h1>
      <p class="cs-sub">{html.escape(c['lede'])}</p>
      <dl class="cs-specbar">{_spec_items(c)}</dl>
      {_sections(c)}
      <div class="cs-cta">
        <p>Explore a representative turbofan cycle for this engine class in the
           interactive console.</p>
        <a href="/lab/">Open the simulator →</a>
      </div>
      <div class="cs-related">
        <h2>More case studies</h2>
        <div class="cs-related-links">{_related(engine_id)}</div>
      </div>
      <p class="cs-disclaimer">
        All figures are public-estimated and approximate, given for a
        representative variant; exact values vary by sub-model and rating.
        PropulsionLab is an educational project and is not affiliated with any
        engine manufacturer. Engine names are the trademarks of their respective
        owners.
      </p>
    </article>
  </body>
</html>
"""


def _index_cards() -> str:
    cards = []
    for engine_id in LIVE_IDS:
        c = CONTENT[engine_id]
        cards.append(
            f'<a class="cs-index-card" href="/lab/case-studies/{engine_id}.html">'
            f'<span class="cs-index-eyebrow">{html.escape(c["maker"])} · {html.escape(c["eis"])}</span>'
            f'<span class="cs-index-name">{html.escape(c["name"])}</span>'
            f'<span class="cs-index-fam">{html.escape(c["family"])} · BPR {html.escape(c["bypass"])}</span>'
            f'<span class="cs-index-lede">{html.escape(c["lede"])}</span>'
            "</a>"
        )
    return "\n          ".join(cards)


def render_index() -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#08090b" />
    <meta name="description" content="Long-form engine case studies — ten landmark jet engines from the JT8D to the Trent XWB, with architecture, cycle and engineering significance." />
    <title>Engine case studies — PropulsionLab</title>
    <link rel="stylesheet" href="/lab/styles.css?v={CACHE}" />
    <link rel="stylesheet" href="/lab/case-study.css?v={CACHE}" />
  </head>
  <body>
    <header class="cs-page-bar">
      {_BRAND}
      <nav class="cs-page-nav">
        <a href="/lab/">Console</a>
      </nav>
    </header>
    <article class="cs-article">
      <p class="eyebrow">PropulsionLab · Case studies</p>
      <h1>Ten engines that shaped the jet age</h1>
      <p class="cs-sub">
        Short, original write-ups of landmark turbofans — the architecture, the
        cycle, and why each one mattered. Read in order they trace the arc from
        the loud low-bypass workhorses of the 1960s to today's high-bypass,
        composite-fan, geared and three-spool designs.
      </p>
      <div class="cs-index-grid">
          {_index_cards()}
      </div>
      <div class="cs-cta">
        <p>Each engine class is loadable as a representative cycle in the
           interactive console.</p>
        <a href="/lab/">Open the simulator →</a>
      </div>
      <p class="cs-disclaimer">
        All figures are public-estimated and approximate, given for a
        representative variant; exact values vary by sub-model and rating.
        PropulsionLab is an educational project and is not affiliated with any
        engine manufacturer. Engine names are the trademarks of their respective
        owners.
      </p>
    </article>
  </body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for engine_id in LIVE_IDS:
        page = render(engine_id, CONTENT[engine_id])
        path = OUT_DIR / f"{engine_id}.html"
        path.write_text(page, encoding="utf-8")
        written.append(path.name)
    index_path = OUT_DIR / "index.html"
    index_path.write_text(render_index(), encoding="utf-8")
    written.append(index_path.name)
    print(f"Wrote {len(written)} files to {OUT_DIR}:")
    for name in written:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
