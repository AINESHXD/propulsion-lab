"""Response models for the certified-engine validation report.

The report is computed server-side from the same solver the console calls, so
the page can never quietly drift from the physics it claims to be reporting on.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationCaseOutput(BaseModel):
    """One certified engine, and how far the solver is from it."""

    icao_uid: str = Field(..., description="ICAO engine UID — check any figure against the databank.")
    name: str
    manufacturer: str
    bypass_ratio: float = Field(..., description="Published.")
    overall_pressure_ratio: float = Field(..., description="Published.")
    turbine_inlet_temperature_K: float = Field(
        ..., description="Assumed from published pressure ratio, not databank data."
    )
    reference_tsfc_kg_per_N_s: float = Field(
        ..., description="Certified: takeoff fuel flow divided by rated sea-level-static thrust."
    )
    predicted_tsfc_kg_per_N_s: float = Field(..., description="PropulsionLab, at the shared assumption set.")
    error_percent: float = Field(..., description="Signed: positive means the solver over-predicts fuel burn.")


class ValidationSummaryOutput(BaseModel):
    """Headline agreement, including the parts that do not flatter the model."""

    count: int
    mean_signed_error_percent: float
    mean_absolute_error_percent: float
    median_absolute_error_percent: float
    worst_absolute_error_percent: float
    rank_correlation: float = Field(
        ...,
        description=(
            "Spearman rank correlation against certified TSFC. This is the trend "
            "question — whether the solver orders real engines the way "
            "certification does — and it survives a systematic offset."
        ),
    )


class ValidationReportOutput(BaseModel):
    """The full report: what was compared, against what, and how it went."""

    summary: ValidationSummaryOutput
    cases: list[ValidationCaseOutput]
    assumptions: dict[str, float] = Field(
        ..., description="Applied identically to every engine. Never fitted per engine."
    )
    validated_quantity: str
    not_validated: str
    primary_source: str
    intermediary_source: str
    source_note: str
