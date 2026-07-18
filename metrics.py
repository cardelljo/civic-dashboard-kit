"""
metric_id registry: documents what each observations-store metric means.

Add an entry here whenever a pipeline is retrofitted to write to the store
(see docs/OBSERVATIONS_STORE_DESIGN.md's migration path). Only metrics that
are actually written to data/observations/ belong here — this registry
should never get ahead of what the pipelines produce.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDef:
    metric_id: str
    label: str
    unit: str
    good_direction: str | None  # "up", "down", or None if purely descriptive
    description: str


REGISTRY: dict[str, MetricDef] = {
    m.metric_id: m
    for m in (
        MetricDef(
            "ela-proficiency",
            "ELA proficiency (% on/mastered)",
            "%",
            "up",
            "Share of tested students meeting or exceeding expectations on the "
            "TDOE TCAP/ACH ELA assessment. subject='ela'; grade is the TDOE "
            "grade-band label ('all-grades' for the district-wide All Students row).",
        ),
        MetricDef(
            "math-proficiency",
            "Math proficiency (% on/mastered)",
            "%",
            "up",
            "Same definition as ela-proficiency for the Math assessment. subject='math'.",
        ),
        MetricDef(
            "enrollment-share",
            "Share of district enrollment",
            "%",
            None,  # descriptive, not a KPI with a preferred direction
            "What fraction of District 792's enrollment a student_group represents. "
            "Used as context alongside a group's proficiency, not a KPI on its own.",
        ),
    )
}
