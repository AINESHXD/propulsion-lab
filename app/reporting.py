"""Simple PDF report generation for PropulsionLab."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

MODEL_ASSUMPTIONS = [
    "Steady one-dimensional cycle model.",
    "Perfect gas model with constant cp and gamma by gas region.",
    "Educational preliminary analysis, not certified design software.",
    "No blade-row CFD, compressor maps, transient spool dynamics, or chemistry equilibrium.",
]


def _escape_pdf_text(value: object) -> str:
    """Escape text for use inside a PDF text literal."""

    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _optional_float(result: dict[str, Any], key: str, digits: int = 2) -> str:
    """Format an optional floating point value for report text."""

    value = result.get(key)
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _station_lines(result: dict[str, Any]) -> list[str]:
    """Build compact station-table lines for the report."""

    lines = ["Stations:"]
    for station in sorted(result["station_table"].values(), key=lambda item: item["station"]):
        static_temperature = station.get("static_temperature_K")
        static_pressure = station.get("static_pressure_Pa")
        line = (
            "  "
            f"{station['station']} {station['name']} | "
            f"Tt={station['stagnation_temperature_K']:.1f} K | "
            f"Pt={station['stagnation_pressure_Pa'] / 1000:.1f} kPa"
        )
        if static_temperature is not None and static_pressure is not None:
            line += f" | T={static_temperature:.1f} K | P={static_pressure / 1000:.1f} kPa"
        lines.append(line)
    return lines


def _input_lines(inputs: dict[str, Any] | None) -> list[str]:
    """Build compact input summary lines for report text."""

    if not inputs:
        return ["Input summary: n/a"]
    preferred_keys = [
        "engine_variant",
        "altitude_m",
        "mach",
        "mass_flow_air_kg_s",
        "total_mass_flow_air_kg_s",
        "compressor_pressure_ratio",
        "core_compressor_pressure_ratio",
        "turbine_inlet_temperature_K",
        "bypass_ratio",
        "fan_pressure_ratio",
        "nozzle_exit_area_m2",
        "nozzle_throat_area_m2",
    ]
    lines = ["Input summary:"]
    for key in preferred_keys:
        if key in inputs and inputs[key] is not None:
            lines.append(f"  {key}: {inputs[key]}")
    return lines


def _page_stream(lines: list[str], heading: str) -> bytes:
    """Create a branded PDF content stream for one page."""

    text_commands = [
        "q",
        "0.02 0.08 0.16 rg",
        "0 800 612 42 re f",
        "0.21 0.74 0.97 rg",
        "0 796 612 3 re f",
        "Q",
        "BT",
        "/F1 16 Tf",
        "0.96 0.98 1 rg",
        "50 815 Td",
        f"({_escape_pdf_text(heading)}) Tj",
        "/F1 9 Tf",
        "0.05 0.10 0.16 rg",
        "0 -46 Td",
        "12 TL",
    ]
    for index, line in enumerate(lines[:55]):
        if index:
            text_commands.append("T*")
        text_commands.append(f"({_escape_pdf_text(line)}) Tj")
    text_commands.append("ET")
    return "\n".join(text_commands).encode("latin-1", errors="replace")


def _pdf_page_lines(lines: list[str], max_lines: int = 55) -> list[list[str]]:
    """Split report lines into page-sized groups."""

    return [lines[index : index + max_lines] for index in range(0, len(lines), max_lines)]


def build_turbojet_pdf_report(
    result: dict[str, Any],
    title: str = "PropulsionLab Report",
    inputs: dict[str, Any] | None = None,
) -> bytes:
    """Return a compact branded PDF performance report as bytes."""

    warning_lines = result["warnings"] or ["None"]
    engine_label = result.get("engine_variant") or result.get("engine_type", "turbojet")
    effective_mass_flow = result.get("effective_mass_flow_air_kg_s") or 0.0
    created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    summary_lines = [
        "DAS LABS / PropulsionLab",
        "Educational preliminary-performance report",
        f"Generated: {created_at}",
        "",
        f"Engine: {engine_label}",
        f"Thrust: {result['thrust_kN']:.2f} kN",
        f"Specific thrust: {result['specific_thrust_N_per_kg_s']:.2f} N/(kg/s)",
        f"Effective air mass flow: {effective_mass_flow:.2f} kg/s",
        f"Fuel-air ratio: {result['fuel_air_ratio']:.5f}",
        f"Fuel flow: {result['fuel_flow_kg_s']:.3f} kg/s",
        f"TSFC: {result['TSFC_kg_per_kN_hr']:.2f} kg/kN/hr",
        f"Exit velocity: {result['exit_velocity_m_s']:.2f} m/s",
        f"Nozzle choked: {result['nozzle_choked']}",
        f"Nozzle expansion status: {result.get('nozzle_expansion_status', 'n/a')}",
        f"Nozzle pressure ratio: {_optional_float(result, 'nozzle_pressure_ratio')}",
        f"Nozzle exit area: {_optional_float(result, 'nozzle_exit_area_m2', 4)} m2",
        f"Thermal efficiency estimate: {result['thermal_efficiency_estimate'] * 100:.2f}%",
        f"Propulsive efficiency estimate: {result['propulsive_efficiency_estimate'] * 100:.2f}%",
        f"Overall efficiency estimate: {result['overall_efficiency_estimate'] * 100:.2f}%",
        "",
        *_input_lines(inputs),
        "",
        "Graphs included in the web dashboard:",
        "  Station Tt, station Pt, T-s, P-v, thrust sweep, TSFC sweep.",
    ]
    detail_lines = [
        *_station_lines(result),
        "",
        "Warnings:",
        *[f"  {warning}" for warning in warning_lines],
        "",
        "Model assumptions:",
        *[f"  {assumption}" for assumption in MODEL_ASSUMPTIONS],
        "",
        "Educational disclaimer:",
        "  Values are trend-oriented preliminary calculations. They are not",
        "  manufacturer-certified data and must not be used for certification.",
    ]

    page_line_groups = [summary_lines, *_pdf_page_lines(detail_lines)]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_refs: list[str] = []
    for page_index, page_lines in enumerate(page_line_groups, start=1):
        page_object_number = len(objects) + 1
        content_object_number = page_object_number + 1
        page_refs.append(f"{page_object_number} 0 R")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + f"{content_object_number} 0 R".encode("ascii")
            + b" >>"
        )
        page_content = _page_stream(page_lines, f"{title} - Page {page_index}")
        objects.append(
            b"<< /Length "
            + str(len(page_content)).encode("ascii")
            + b" >>\nstream\n"
            + page_content
            + b"\nendstream"
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
