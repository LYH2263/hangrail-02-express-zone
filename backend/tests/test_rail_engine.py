from app.services.rail_engine import Segment, first_fit, fit_in_zone, free_gaps, gaps_within


def test_first_fit_leftmost():
    occ = [Segment(20, 40)]
    p = first_fit(100, occ, 15)
    assert p is not None
    assert p.start_cm == 0
    assert p.end_cm == 15


def test_first_fit_skips_too_small_gap():
    occ = [Segment(0, 10), Segment(18, 50)]
    p = first_fit(100, occ, 10)
    assert p is not None
    assert p.start_cm == 50


def test_no_space():
    occ = [Segment(0, 80)]
    assert first_fit(100, occ, 25) is None


def test_free_gaps_edges():
    gaps = free_gaps(50, [Segment(10, 20), Segment(30, 35)])
    assert gaps == [Segment(0, 10), Segment(20, 30), Segment(35, 50)]


# —— 快递专区 ——

def test_normal_skips_empty_zone():
    # 专区空着，普通衣也不得占用：只能落在专区之后
    p = first_fit(160, [], 50, express_zone=Segment(0, 60))
    assert p is not None
    assert p.start_cm == 60


def test_normal_skips_zone_internal_gap():
    # 专区 [20,80) 前后都有普通衣，专区内部空隙必须跳过
    occ = [Segment(0, 20), Segment(80, 95)]
    p = first_fit(160, occ, 30, express_zone=Segment(20, 80))
    assert p is not None
    assert p.start_cm == 95


def test_normal_cannot_span_zone_boundary():
    # 贴专区右侧放置，不允许横跨专区边界
    occ = [Segment(60, 70)]
    p = first_fit(160, occ, 90, express_zone=Segment(0, 60))
    assert p is not None
    assert p.start_cm == 70
    assert p.end_cm == 160


def test_normal_fills_gap_before_zone():
    occ = [Segment(20, 60)]
    p = first_fit(160, occ, 20, express_zone=Segment(60, 120))
    assert p is not None
    assert p.start_cm == 0


def test_express_lands_in_empty_zone():
    p = first_fit(160, [], 25, express_zone=Segment(0, 60), is_express=True)
    assert p is not None
    assert p.start_cm == 0
    assert p.end_cm == 25


def test_express_lands_in_zone_gap():
    occ = [Segment(0, 40)]
    p = first_fit(160, occ, 20, express_zone=Segment(0, 60), is_express=True)
    assert p is not None
    assert p.start_cm == 40
    assert p.end_cm == 60


def test_express_zone_full_falls_back_outside():
    # 专区内只剩 10cm，25cm 加急衣回退到专区外
    occ = [Segment(0, 50)]
    p = first_fit(160, occ, 25, express_zone=Segment(0, 60), is_express=True)
    assert p is not None
    assert p.start_cm == 60


def test_express_no_fit_anywhere():
    occ = [Segment(0, 50), Segment(60, 160)]
    p = first_fit(160, occ, 25, express_zone=Segment(0, 60), is_express=True)
    assert p is None


def test_no_zone_rail_unchanged():
    # 未划专区的杆：普通与加急都按现网规则全杆扫描
    occ = [Segment(10, 30)]
    p_normal = first_fit(100, occ, 10)
    p_express = first_fit(100, occ, 10, is_express=True)
    assert p_normal is not None and p_normal.start_cm == 0
    assert p_express is not None and p_express.start_cm == 0


def test_gaps_within_clips_occupancy():
    # 占位段横跨专区边界时，只裁剪专区内部部分
    gaps = gaps_within(Segment(20, 80), [Segment(10, 50), Segment(70, 90)])
    assert gaps == [Segment(50, 70)]


def test_fit_in_zone_too_long():
    assert fit_in_zone(Segment(0, 60), [], 61) is None
