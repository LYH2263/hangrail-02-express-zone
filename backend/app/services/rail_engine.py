"""1D First-Fit placement by garment length on a hang rail.

A rail may declare one half-open express zone ``[zone_start, zone_end)``.
Only express (快递加急) garments may occupy that interval; normal garments'
First-Fit scan skips every gap falling inside the zone even when it is empty.
Express garments prefer the zone first, and only when the zone cannot fit
them do they fall back to the ordinary scan over the rest of the rail.
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


_EPS = 1e-9


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


def valid_zone(
    rail_length: float, zone_start: float | None, zone_end: float | None
) -> bool:
    """A zone is absent (both None) or a non-empty interval within the rail."""
    if zone_start is None and zone_end is None:
        return True
    if zone_start is None or zone_end is None:
        return False
    return (
        zone_start + _EPS >= 0
        and zone_end <= rail_length + _EPS
        and zone_end - zone_start > _EPS
    )


def _intersect(gap: Segment, zone: Segment) -> Segment | None:
    lo = max(gap.start_cm, zone.start_cm)
    hi = min(gap.end_cm, zone.end_cm)
    if hi - lo > _EPS:
        return Segment(lo, hi)
    return None


def _outside_zone(gap: Segment, zone: Segment) -> list[Segment]:
    """Pieces of ``gap`` that do not lie inside the express zone."""
    pieces: list[Segment] = []
    if gap.start_cm < zone.start_cm:
        pieces.append(Segment(gap.start_cm, min(gap.end_cm, zone.start_cm)))
    if gap.end_cm > zone.end_cm:
        pieces.append(Segment(max(gap.start_cm, zone.end_cm), gap.end_cm))
    return [p for p in pieces if p.length > _EPS]


def first_fit(
    rail_length: float,
    occupied: list[Segment],
    garment_cm: float,
    express_zone: Segment | None = None,
    is_express: bool = False,
    zone_only: bool = False,
) -> Placement | None:
    """First-Fit with an optional express zone.

    - ``zone_only=True``: only fit inside ``express_zone`` (used for the
      cross-rail first pass of express orders); no zone → no fit.
    - ``is_express`` on a single rail: try the zone first, then fall back to
      the zone-exclusive gaps of the same rail.
    - normal garments never land inside the zone, even when it is empty.
    """
    if garment_cm <= 0 or garment_cm > rail_length:
        return None
    gaps = free_gaps(rail_length, occupied)

    if zone_only:
        if express_zone is None:
            return None
        for gap in gaps:
            inside = _intersect(gap, express_zone)
            if inside is not None and inside.length + _EPS >= garment_cm:
                return Placement(inside.start_cm, inside.start_cm + garment_cm)
        return None

    # Express garments: try the zone first, left to right, before the rest.
    if is_express and express_zone is not None:
        for gap in gaps:
            inside = _intersect(gap, express_zone)
            if inside is not None and inside.length + _EPS >= garment_cm:
                return Placement(inside.start_cm, inside.start_cm + garment_cm)

    # Normal garments may never land inside the zone; express garments only
    # reach this scan (zone-exclusive pieces included) when the zone failed.
    for gap in gaps:
        candidates = _outside_zone(gap, express_zone) if express_zone else [gap]
        for cand in candidates:
            if cand.length + _EPS >= garment_cm:
                return Placement(cand.start_cm, cand.start_cm + garment_cm)
    return None


def overlaps(a: Segment, b: Segment) -> bool:
    return not (a.end_cm <= b.start_cm or b.end_cm <= a.start_cm)
