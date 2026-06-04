"""PDF report generation for PropulsionLab.

A small, dependency-free PDF writer (raw object/stream construction, no reportlab
or Pillow) so the report endpoint works in the slim production image. The visual
language mirrors the website: a near-black page, off-white headings, a dim-grey
body in a monospaced face so data columns line up, a single blue accent rule, and
a vector DAS LABS logo lockup in the header (drawn as paths, so it scales cleanly
and needs no raster decoding).
"""

from __future__ import annotations

import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ASSETS = Path(__file__).resolve().parent / "static" / "assets"

# --- Palette, lifted from the site's design tokens -------------------------
_BG = "0.039 0.043 0.055"        # --bg   #0a0b0e
_BAND = "0.067 0.075 0.090"      # header band, a touch above the page
_OFFWHITE = "0.953 0.957 0.965"  # --text #f3f4f6
_BODY = "0.78 0.80 0.84"         # readable body grey
_DIM = "0.569 0.592 0.631"       # --dim  #9197a1
_ACCENT = "0.482 0.654 0.922"    # --accent #7ba7eb
_RULE = "0.16 0.17 0.20"         # hairline rules

# --- Page geometry (A4) ----------------------------------------------------
_W, _H = 595.0, 842.0
_MARGIN = 46.0
_BODY_TOP = 716.0
_BODY_BOTTOM = 74.0

# Vertical advance per element kind.
_LEADING = {
    "h1": 27.0,
    "sub": 14.0,
    "h2": 22.0,
    "data": 11.6,
    "body": 13.0,
    "blank": 8.0,
}

MODEL_ASSUMPTIONS = [
    "Steady one-dimensional cycle model.",
    "Perfect gas with constant cp and gamma by gas region.",
    "Educational preliminary analysis, not certified design software.",
    "No blade-row CFD, compressor maps, transient dynamics, or chemistry equilibrium.",
]


def _escape_pdf_text(value: object) -> str:
    """Escape text for a PDF string literal."""

    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _optional_float(result: dict[str, Any], key: str, digits: int = 2) -> str:
    value = result.get(key)
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _kv(label: str, value: object) -> tuple[str, str]:
    """A monospaced key/value data line, label column padded with a guaranteed gap."""

    gap = max(2, 24 - len(label))
    return ("data", f"{label}{' ' * gap}{value}")


# ---------------------------------------------------------------------------
# Content assembly
# ---------------------------------------------------------------------------


def _station_elements(result: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [("h2", "Stations")]
    rows.append(("data", f"{'#':<3}{'name':<30}{'Tt[K]':>9}{'Pt[kPa]':>11}{'T[K]':>9}{'P[kPa]':>10}"))
    for station in sorted(result["station_table"].values(), key=lambda item: item["station"]):
        st_t = station.get("static_temperature_K")
        st_p = station.get("static_pressure_Pa")
        t_txt = f"{st_t:.1f}" if st_t is not None else "-"
        p_txt = f"{st_p / 1000:.1f}" if st_p is not None else "-"
        name = str(station["name"])[:28]
        rows.append((
            "data",
            f"{station['station']:<3}{name:<30}"
            f"{station['stagnation_temperature_K']:>9.1f}"
            f"{station['stagnation_pressure_Pa'] / 1000:>11.1f}"
            f"{t_txt:>9}{p_txt:>10}",
        ))
    return rows


def _input_elements(inputs: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not inputs:
        return [("h2", "Input summary"), ("body", "n/a")]
    preferred_keys = [
        "engine_variant", "altitude_m", "mach", "mass_flow_air_kg_s",
        "total_mass_flow_air_kg_s", "compressor_pressure_ratio",
        "core_compressor_pressure_ratio", "turbine_inlet_temperature_K",
        "bypass_ratio", "fan_pressure_ratio", "nozzle_exit_area_m2",
        "nozzle_throat_area_m2",
    ]
    rows: list[tuple[str, str]] = [("h2", "Input summary")]
    for key in preferred_keys:
        if key in inputs and inputs[key] is not None:
            rows.append(_kv(key, inputs[key]))
    if len(rows) == 1:
        rows.append(("body", "n/a"))
    return rows


def _build_elements(
    result: dict[str, Any], title: str, inputs: dict[str, Any] | None
) -> list[tuple[str, str]]:
    """Flatten the whole report into a styled element list."""

    engine_label = result.get("engine_variant") or result.get("engine_type", "turbojet")
    eff_flow = result.get("effective_mass_flow_air_kg_s") or 0.0
    created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    warnings = result["warnings"] or ["None"]

    elements: list[tuple[str, str]] = [
        ("h1", title),
        ("sub", "Educational preliminary-performance report"),
        ("sub", f"Generated {created_at}"),
        ("blank", ""),

        ("h2", "Performance summary"),
        _kv("Engine", engine_label),
        _kv("Thrust", f"{result['thrust_kN']:.2f} kN"),
        _kv("Specific thrust", f"{result['specific_thrust_N_per_kg_s']:.2f} N/(kg/s)"),
        _kv("Effective air flow", f"{eff_flow:.2f} kg/s"),
        _kv("Fuel-air ratio", f"{result['fuel_air_ratio']:.5f}"),
        _kv("Fuel flow", f"{result['fuel_flow_kg_s']:.3f} kg/s"),
        _kv("TSFC", f"{result['TSFC_kg_per_kN_hr']:.2f} kg/kN/hr"),
        _kv("Exit velocity", f"{result['exit_velocity_m_s']:.2f} m/s"),
        _kv("Nozzle choked", result["nozzle_choked"]),
        _kv("Expansion status", result.get("nozzle_expansion_status", "n/a")),
        _kv("Nozzle PR", _optional_float(result, "nozzle_pressure_ratio")),
        _kv("Nozzle exit area", f"{_optional_float(result, 'nozzle_exit_area_m2', 4)} m2"),
        ("blank", ""),

        ("h2", "Efficiency"),
        _kv("Thermal", f"{result['thermal_efficiency_estimate'] * 100:.2f} %"),
        _kv("Propulsive", f"{result['propulsive_efficiency_estimate'] * 100:.2f} %"),
        _kv("Overall", f"{result['overall_efficiency_estimate'] * 100:.2f} %"),
        ("blank", ""),

        *_input_elements(inputs),
        ("blank", ""),

        *_station_elements(result),
        ("blank", ""),

        ("h2", "Warnings"),
        *[("body", str(w)) for w in warnings],
        ("blank", ""),

        ("h2", "Model assumptions"),
        *[("body", a) for a in MODEL_ASSUMPTIONS],
        ("blank", ""),

        ("h2", "Disclaimer"),
        ("body", "Trend-oriented preliminary calculations. Not manufacturer-certified"),
        ("body", "data; must not be used for certification."),
    ]
    return elements


def _flow(elements: list[tuple[str, str]]) -> list[list[tuple[str, str, float]]]:
    """Place elements onto pages, returning (kind, text, y) per page."""

    pages: list[list[tuple[str, str, float]]] = []
    current: list[tuple[str, str, float]] = []
    y = _BODY_TOP
    for kind, text in elements:
        advance = _LEADING.get(kind, 13.0)
        # h2 sections get a little breathing room above them.
        if kind == "h2" and current:
            y -= 6.0
        if y - advance < _BODY_BOTTOM:
            pages.append(current)
            current = []
            y = _BODY_TOP
        current.append((kind, text, y))
        y -= advance
    if current:
        pages.append(current)
    return pages or [[]]


# ---------------------------------------------------------------------------
# Vector logo + page chrome
# ---------------------------------------------------------------------------


def _load_logo_image(filename: str, max_width_px: int) -> dict[str, Any] | None:
    """Decode a transparent PNG into PDF-ready RGB + alpha streams.

    Returns flate-compressed colour and soft-mask data plus pixel size, or
    ``None`` if Pillow or the file is unavailable (the caller then falls back to
    the vector mark, so the report endpoint never fails over a missing asset).
    """

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - PIL absent
        return None

    path = _ASSETS / filename
    if not path.exists():  # pragma: no cover - asset missing
        return None
    try:
        im = Image.open(path).convert("RGBA")
    except Exception:  # pragma: no cover - unreadable asset
        return None

    if im.width > max_width_px:
        new_h = max(1, round(im.height * max_width_px / im.width))
        im = im.resize((max_width_px, new_h), Image.LANCZOS)

    rgb = im.convert("RGB").tobytes()
    alpha = im.getchannel("A").tobytes()
    return {
        "w": im.width,
        "h": im.height,
        "rgb": zlib.compress(rgb, 9),
        "alpha": zlib.compress(alpha, 9),
    }


def _logo_commands(x: float, y: float, height: float) -> list[str]:
    """Draw the DAS LABS swoosh mark as vector paths.

    Recreated from the site's brand mark (viewBox 96x48, y-down). The trail is a
    stroked line; the dart and its fin are filled triangles. Origin (x, y) is the
    bottom-left; the mark is `height` tall.
    """

    s = height / 48.0

    def p(sx: float, sy: float) -> str:
        return f"{x + sx * s:.2f} {y + (48 - sy) * s:.2f}"

    return [
        "q",
        # trail
        f"{1.6 * s:.2f} w",
        f"{_ACCENT} RG",
        f"{p(2, 29)} m {p(30, 29)} l S",
        # main dart
        f"{_ACCENT} rg",
        f"{p(30, 29)} m {p(86, 8)} l {p(52, 29)} l f",
        # lower fin, dimmer
        "0.30 0.43 0.62 rg",
        f"{p(30, 29)} m {p(52, 29)} l {p(44, 35)} l f",
        "Q",
    ]


def _text(font: str, size: float, color: str, x: float, y: float, text: str,
          charspace: float = 0.0) -> str:
    return (
        f"/{font} {size:.1f} Tf\n{color} rg\n{charspace:.2f} Tc\n"
        f"1 0 0 1 {x:.1f} {y:.1f} Tm\n({_escape_pdf_text(text)}) Tj"
    )


def _courier_width(text: str, size: float) -> float:
    return len(text) * size * 0.6  # Courier is monospaced at 0.6 em


def _page_stream(
    page: list[tuple[str, str, float]],
    page_index: int,
    page_count: int,
    header_graphics: list[str],
    header_text: list[str],
) -> bytes:
    g: list[str] = []  # graphics ops (paths/fills) before the text block

    # Page background + header band + accent rule + footer hairline.
    g.append(f"{_BG} rg")
    g.append(f"0 0 {_W:.0f} {_H:.0f} re f")
    g.append(f"{_BAND} rg")
    g.append(f"0 752 {_W:.0f} 90 re f")
    g.append(f"{_ACCENT} rg")
    g.append(f"0 750 {_W:.0f} 1.6 re f")
    g.append(f"{_RULE} rg")
    g.append(f"{_MARGIN:.0f} 60 {_W - 2 * _MARGIN:.0f} 0.7 re f")
    g.extend(header_graphics)  # logo images (or vector mark fallback)

    # Text block.
    t: list[str] = ["BT"]
    t.extend(header_text)  # wordmark / eyebrow when no images are embedded

    # Body elements.
    for kind, text, y in page:
        if kind == "blank":
            continue
        if kind == "h1":
            t.append(_text("F2", 19.0, _OFFWHITE, _MARGIN, y, text, charspace=0.2))
        elif kind == "sub":
            t.append(_text("F1", 9.5, _DIM, _MARGIN, y, text))
        elif kind == "h2":
            # accent tick is graphics; emit it after the text block instead.
            g.append(f"{_ACCENT} rg")
            g.append(f"{_MARGIN:.0f} {y - 1.5:.1f} 3 11 re f")
            t.append(_text("F2", 10.5, _OFFWHITE, _MARGIN + 11, y, text, charspace=0.4))
        elif kind == "data":
            t.append(_text("F3", 8.5, _BODY, _MARGIN, y, text))
        else:  # body
            t.append(_text("F1", 9.0, _BODY, _MARGIN, y, text))

    # Footer.
    foot_left = "DAS LABS / PropulsionLab - educational, not certified"
    foot_right = f"Page {page_index} of {page_count}"
    t.append(_text("F1", 7.5, _DIM, _MARGIN, 47.0, foot_left))
    t.append(_text("F3", 7.5, _DIM, _W - _MARGIN - _courier_width(foot_right, 7.5), 47.0, foot_right))
    t.append("ET")

    return ("\n".join(g + t)).encode("latin-1", errors="replace")


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_turbojet_pdf_report(
    result: dict[str, Any],
    title: str = "PropulsionLab Report",
    inputs: dict[str, Any] | None = None,
) -> bytes:
    """Return a branded, site-themed PDF performance report as bytes."""

    pages = _flow(_build_elements(result, title, inputs))

    # Objects 1=Catalog, 2=Pages, 3/4/5 = fonts (Helvetica, Helvetica-Bold, Courier).
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # Pages, filled once kids are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    ]

    # Header artwork: try the real PNG logos (DAS LABS lockup, left; PropulsionLab
    # wordmark, right). Each becomes an image XObject + a grayscale soft mask from
    # its alpha, so the transparent art sits cleanly on the header band. If Pillow
    # or the assets are unavailable, fall back to the vector mark + text.
    header_graphics: list[str] = []
    header_text: list[str] = []
    xobject_entries: list[str] = []
    band_mid = 797.0
    logo_layout = [
        ("das_labs_logo_dark.png", 330, 15.0, "left", _MARGIN),
        ("propulsionlab_wordmark.png", 320, 10.5, "right", _W - _MARGIN),
    ]
    for idx, (fname, max_px, disp_h, align, anchor) in enumerate(logo_layout):
        img = _load_logo_image(fname, max_px)
        if img is None:
            continue
        disp_w = disp_h * img["w"] / img["h"]
        x = anchor if align == "left" else anchor - disp_w
        y = band_mid - disp_h / 2
        res_name = f"Im{idx}"
        # soft mask object, then the image object that references it
        objects.append(
            b"<< /Type /XObject /Subtype /Image /Width " + str(img["w"]).encode()
            + b" /Height " + str(img["h"]).encode()
            + b" /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length "
            + str(len(img["alpha"])).encode() + b" >>\nstream\n" + img["alpha"] + b"\nendstream"
        )
        smask_num = len(objects)
        objects.append(
            b"<< /Type /XObject /Subtype /Image /Width " + str(img["w"]).encode()
            + b" /Height " + str(img["h"]).encode()
            + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /SMask "
            + f"{smask_num} 0 R".encode() + b" /Filter /FlateDecode /Length "
            + str(len(img["rgb"])).encode() + b" >>\nstream\n" + img["rgb"] + b"\nendstream"
        )
        image_num = len(objects)
        xobject_entries.append(f"/{res_name} {image_num} 0 R")
        header_graphics += [
            "q", f"{disp_w:.2f} 0 0 {disp_h:.2f} {x:.2f} {y:.2f} cm", f"/{res_name} Do", "Q",
        ]

    if not header_graphics:
        # Fallback: vector dart + text wordmark + mono eyebrow.
        header_graphics = _logo_commands(_MARGIN, 786.0, 22.0)
        header_text = [
            _text("F2", 15.0, _OFFWHITE, _MARGIN + 40, 791.0, "DAS LABS", charspace=1.4),
            _text("F3", 7.5, _ACCENT, _W - _MARGIN - _courier_width("PROPULSIONLAB", 7.5), 800.0, "PROPULSIONLAB"),
            _text("F3", 7.0, _DIM, _W - _MARGIN - _courier_width("PERFORMANCE REPORT", 7.0), 788.0, "PERFORMANCE REPORT"),
        ]

    xobject_res = (
        b" /XObject << " + " ".join(xobject_entries).encode("ascii") + b" >>"
        if xobject_entries else b""
    )

    page_refs: list[str] = []
    for page_index, page in enumerate(pages, start=1):
        page_object_number = len(objects) + 1
        content_object_number = page_object_number + 1
        page_refs.append(f"{page_object_number} 0 R")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >>"
            + xobject_res
            + b" >> /Contents "
            + f"{content_object_number} 0 R".encode("ascii")
            + b" >>"
        )
        content = _page_stream(page, page_index, len(pages), header_graphics, header_text)
        objects.append(
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
            + content + b"\nendstream"
        )

    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>"
    ).encode("ascii")

    pdf_parts = [b"%PDF-1.4\n"]
    offsets: list[int] = []
    for object_number, object_body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in pdf_parts))
        pdf_parts.append(f"{object_number} 0 obj\n".encode("ascii"))
        pdf_parts.append(object_body)
        pdf_parts.append(b"\nendobj\n")

    xref_offset = sum(len(part) for part in pdf_parts)
    pdf_parts.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_parts.append(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf_parts.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf_parts.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return b"".join(pdf_parts)
