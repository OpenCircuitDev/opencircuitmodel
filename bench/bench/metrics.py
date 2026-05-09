"""Metric types and verdict logic for OCM benchmark sandboxes."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class Thresholds(BaseModel):
    confirm_at_least: float | None = None
    refute_below: float | None = None
    confirm_at_most: float | None = None
    refute_above: float | None = None
    confirm_at_least_vs_uncompiled_pp: float | None = None
    confirm_at_most_cross_node_drift_pp: float | None = None
    refute_below_vs_uncompiled_pp: float | None = None
    refute_above_cross_node_drift_pp: float | None = None
    confirm_at_least_vs_frontier_pp: float | None = None
    refute_below_vs_frontier_pp: float | None = None

    model_config = {"extra": "allow"}


class ExpectedJson(BaseModel):
    """Schema for `expected.json` files in sandboxes."""

    hypothesis_id: str = Field(..., min_length=1)
    claim: str = Field(..., min_length=10)
    metric: str = Field(..., min_length=1)
    thresholds: Thresholds
    workload: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=600, ge=1)
    source_for_claim: str | None = None
    secondary_metric: str | None = None
    secondary_thresholds: Thresholds | None = None
    comparison_anchor: str | None = None
    decision_rule: str | None = None
    # "ACTIVE" sandboxes have docker-compose.yml + bench.py and run end-to-end.
    # "INACTIVE" sandboxes are slot-stubs committed before their underlying tech
    # is ready (mesh transport, model packaging, workload curation, etc.) — they
    # ship with just expected.json + README.md so the harness has a target later.
    status: str = "ACTIVE"
    blocked_on: list[str] | None = None

    model_config = {"extra": "allow"}


class RunResult(BaseModel):
    """One execution of a sandbox."""

    hypothesis_id: str
    repeat_index: int
    primary_value: float
    secondary_value: float | None = None
    duration_seconds: float
    raw_path: str | None = None


class SandboxSummary(BaseModel):
    """Aggregated verdict for a sandbox after `repeats` runs."""

    hypothesis_id: str
    hardware_class: str
    timestamp_utc: str
    expected: ExpectedJson
    runs: list[RunResult]
    primary_median: float
    primary_std: float | None
    secondary_median: float | None = None
    secondary_std: float | None = None
    verdict: Verdict
    verdict_reason: str


def decide_verdict(
    primary_median: float,
    expected: ExpectedJson,
    secondary_median: float | None = None,
) -> tuple[Verdict, str]:
    """Apply confirm/refute thresholds and return verdict + reason."""
    t = expected.thresholds
    primary_v: Verdict | None = None
    primary_reason = ""

    if t.confirm_at_least is not None:
        if primary_median >= t.confirm_at_least:
            primary_v = Verdict.CONFIRMED
            primary_reason = f"primary {primary_median:.3f} >= confirm_at_least {t.confirm_at_least}"
        elif t.refute_below is not None and primary_median < t.refute_below:
            primary_v = Verdict.REFUTED
            primary_reason = f"primary {primary_median:.3f} < refute_below {t.refute_below}"
        else:
            primary_v = Verdict.INCONCLUSIVE
            primary_reason = (
                f"primary {primary_median:.3f} between refute_below {t.refute_below} "
                f"and confirm_at_least {t.confirm_at_least}"
            )
    elif t.confirm_at_most is not None:
        if primary_median <= t.confirm_at_most:
            primary_v = Verdict.CONFIRMED
            primary_reason = f"primary {primary_median:.3f} <= confirm_at_most {t.confirm_at_most}"
        elif t.refute_above is not None and primary_median > t.refute_above:
            primary_v = Verdict.REFUTED
            primary_reason = f"primary {primary_median:.3f} > refute_above {t.refute_above}"
        else:
            primary_v = Verdict.INCONCLUSIVE
            primary_reason = (
                f"primary {primary_median:.3f} between confirm_at_most {t.confirm_at_most} "
                f"and refute_above {t.refute_above}"
            )

    if primary_v is None:
        return (
            Verdict.INCONCLUSIVE,
            "no applicable threshold pair found; cannot classify",
        )

    if expected.secondary_thresholds is not None and secondary_median is not None:
        st = expected.secondary_thresholds
        if st.confirm_at_most is not None and secondary_median > st.confirm_at_most:
            if st.refute_above is not None and secondary_median > st.refute_above:
                return (
                    Verdict.REFUTED,
                    f"{primary_reason}; secondary {secondary_median:.3f} > refute_above {st.refute_above}",
                )
            return (
                Verdict.INCONCLUSIVE,
                f"{primary_reason}; secondary {secondary_median:.3f} exceeds confirm_at_most {st.confirm_at_most}",
            )
        if st.confirm_at_least is not None and secondary_median < st.confirm_at_least:
            if st.refute_below is not None and secondary_median < st.refute_below:
                return (
                    Verdict.REFUTED,
                    f"{primary_reason}; secondary {secondary_median:.3f} < refute_below {st.refute_below}",
                )
            return (
                Verdict.INCONCLUSIVE,
                f"{primary_reason}; secondary {secondary_median:.3f} below confirm_at_least {st.confirm_at_least}",
            )

    return primary_v, primary_reason
