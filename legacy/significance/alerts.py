"""
significance/alerts.py

Triage alert level mapping for clinical concept significance.

Provides a static dictionary-driven mapping from SignificanceLevel to AlertLevel.
"""

from __future__ import annotations

from significance.models import AlertLevel, SignificanceLevel

# Static mapping from clinical significance level to triage alert level.
#
# Clinical Rationale for Alert Assignments:
# ----------------------------------------
# - INFORMATIONAL -> GREEN:
#     Findings reported as normal or explicitly absent (e.g., 'No RWMA', 'Normal RV function')
#     represent baseline/reassuring facts.
# - WITHIN_REPORTED_RANGE -> GREEN:
#     Quantitative metrics that fall squarely inside the laboratory or clinical reference
#     interval (e.g., EF = 60%) represent expected physiological parameters.
# - NOTABLE_FINDING -> YELLOW:
#     A qualitative finding reported as PRESENT (e.g., 'Mild TR', 'Concentric LVH').
#     Assigned YELLOW to indicate clinical note/awareness without automatically
#     asserting high-urgency risk or immediate intervention.
# - OUTSIDE_REPORTED_RANGE -> ORANGE:
#     A quantitative parameter that directly violates reported reference limits
#     (e.g., IVSd = 13 mm against ref 6-11 mm). Assigned ORANGE to reflect an objective,
#     measured numerical deviation warranting clinician review.
# - REQUIRES_CONTEXT -> GREY:
#     Measurements reported without an accompanying reference interval (e.g., PASP = 34 mmHg,
#     Aortic Velocity = 1.47 m/s). Clinical significance cannot be established in isolation
#     and depends entirely on overall patient context.
# - UNRESOLVED -> GREY:
#     Ambiguous, possible, or unmapped concepts where diagnostic certainty is insufficient.
# - CRITICAL -> RED:
#     Explicitly reserved for acute, life-threatening, emergency findings requiring immediate
#     clinical intervention (never auto-assigned in this initial pass).
SIGNIFICANCE_ALERT_MAP: dict[SignificanceLevel, AlertLevel] = {
    SignificanceLevel.INFORMATIONAL: AlertLevel.GREEN,
    SignificanceLevel.WITHIN_REPORTED_RANGE: AlertLevel.GREEN,
    SignificanceLevel.NOTABLE_FINDING: AlertLevel.YELLOW,
    SignificanceLevel.OUTSIDE_REPORTED_RANGE: AlertLevel.ORANGE,
    SignificanceLevel.REQUIRES_CONTEXT: AlertLevel.GREY,
    SignificanceLevel.UNRESOLVED: AlertLevel.GREY,
    SignificanceLevel.CRITICAL: AlertLevel.RED,
}


def map_to_alert(significance: SignificanceLevel) -> AlertLevel:
    """
    Map a SignificanceLevel to an AlertLevel via static dictionary lookup.

    Parameters
    ----------
    significance:
        Evaluated significance level of the concept.

    Returns
    -------
    AlertLevel:
        Corresponding triage alert color category (GREEN, YELLOW, ORANGE, RED, GREY).
    """
    return SIGNIFICANCE_ALERT_MAP.get(significance, AlertLevel.GREY)
