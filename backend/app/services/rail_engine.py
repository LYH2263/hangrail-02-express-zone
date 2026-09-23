"""1D First-Fit placement by garment length on a hang rail.

Express zone（快递专区）: a half-open interval [start_cm, end_cm) on a rail
reserved for express work orders. Normal orders must skip zone-internal gaps
even when the zone is empty; express orders try the zone first and fall back
to the regular scan when the zone has no fitting gap.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start_cm: float
    end_cm: float  # exclusive

    @property
    def length(self) -> float:
        return self.end_cm - self.start_cm


@dataclass(frozen=True)
class Placement:
    start_cm: float
    end_cm: float


def free_gaps(rail_length: float, occupied: list[Segment]) -> list[Segment]:
    occ = sorted(occupied, key=lambda s: s.start_cm)
    gaps: list[Segment] = []
    cursor = 0.0
    for seg in occ:
        if seg.start_cm > cursor:
            gaps.append(Segment(cursor, seg.start_cm))
        cursor = max(cursor, seg.end_cm)
    if cursor < rail_length:
        gaps.append(Segment(cursor, rail_length))
    return gaps


def gaps_within(window: Segment, occupied: list[Segment]) -> list[Segment]:
    """Free gaps clipped to [window.start_cm, window.end_cm)."""
    clipped: list[Segment] = []
    for seg in occupied:
        lo = max(seg.start_cm, window.start_cm)
        hi = min(seg.end_cm, window.end_cm)
        if hi > lo:
            clipped.append(Segment(lo, hi))
    gaps: list[Segment] = []
    cursor = window.start_cm
    for seg in sorted(clipped, key=lambda s: s.start_cm):
        if seg.start_cm > cursor:
            gaps.append(Segment(cursor, seg.start_cm))
        cursor = max(cursor, seg.end_cm)
    if cursor < window.end_cm:
        gaps.append(Segment(cursor, window.end_cm))
    return gaps


def _fit_in_gaps(gaps: list[Segment], garment_cm: float) -> Placement | None:
    for gap in gaps:
        if gap.length + 1e-9 >= garment_cm:
            return Placement(gap.start_cm, gap.start_cm + garment_cm)
    return None


def fit_in_zone(zone: Segment, occupied: list[Segment], garment_cm: float) -> Placement | None:
    """Leftmost placement fully inside the express zone, or None."""
    if garment_cm <= 0 or garment_cm > zone.length:
        return None
    return _fit_in_gaps(gaps_within(zone, occupied), garment_cm)


def first_fit(
    rail_length: float,
    occupied: list[Segment],
    garment_cm: float,
    express_zone: Segment | None = None,
    is_express: bool = False,
) -> Placement | None:
    """Leftmost placement on one rail.

    - Normal orders: the express zone (if any) is treated as occupied, so
      zone-internal gaps are skipped even when empty.
    - Express orders: try the zone interior first; if nothing fits there,
      fall back to the same scan as a normal order (zone stays reserved).
    """
    if garment_cm <= 0 or garment_cm > rail_length:
        return None
    if is_express and express_zone is not None:
        placed = fit_in_zone(express_zone, occupied, garment_cm)
        if placed is not None:
            return placed
    blocked = list(occupied)
    if express_zone is not None:
        blocked.append(express_zone)
    return _fit_in_gaps(free_gaps(rail_length, blocked), garment_cm)


def overlaps(a: Segment, b: Segment) -> bool:
    return not (a.end_cm <= b.start_cm or b.end_cm <= a.start_cm)
