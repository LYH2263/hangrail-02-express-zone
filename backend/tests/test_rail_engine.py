from app.services.rail_engine import Segment, first_fit, free_gaps, valid_zone

ZONE_0_60 = Segment(0, 60)


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

def test_normal_skips_empty_zone_gap():
    """普通衣即使专区空着也不得使用：空杆专区 [0,60)，普通衣从 60 开始。"""
    p = first_fit(160, [], 30, express_zone=ZONE_0_60, is_express=False)
    assert p is not None
    assert p.start_cm == 60
    assert p.end_cm == 90


def test_normal_skips_zone_gap_between_orders():
    """专区内 [25,60) 有 35cm 空隙且 30cm 普通衣本可放入，必须跳到专区外 100。"""
    occ = [Segment(0, 25), Segment(60, 100)]
    p = first_fit(160, occ, 30, express_zone=ZONE_0_60, is_express=False)
    assert p is not None
    assert p.start_cm == 100
    assert p.end_cm == 130


def test_express_lands_inside_zone():
    """加急短衣优先落入专区空隙 [25,60)。"""
    occ = [Segment(0, 25), Segment(60, 100)]
    p = first_fit(160, occ, 20, express_zone=ZONE_0_60, is_express=True)
    assert p is not None
    assert p.start_cm == 25
    assert p.end_cm == 45


def test_express_prefers_zone_over_earlier_free_gap():
    """杆头 0 起点虽在专区内；专区位于中段时加急衣仍优先专区而非外侧更左空隙。"""
    zone = Segment(60, 100)
    p = first_fit(160, [], 20, express_zone=zone, is_express=True)
    assert p is not None
    assert p.start_cm == 60


def test_express_zone_full_falls_back_to_general_gap():
    """专区放不下时，加急衣按现网规则扫描专区外空隙。"""
    occ = [Segment(0, 60)]
    p = first_fit(160, occ, 30, express_zone=ZONE_0_60, is_express=True)
    assert p is not None
    assert p.start_cm == 60


def test_express_zone_too_tight_falls_back():
    """专区剩余 20cm 容不下 30cm 加急衣，落到专区外 60。"""
    occ = [Segment(0, 40)]
    p = first_fit(160, occ, 30, express_zone=ZONE_0_60, is_express=True)
    assert p is not None
    assert p.start_cm == 60


def test_rail_without_zone_stays_fully_usable():
    """未划专区的杆保持全杆可挂，普通衣从 0 开始。"""
    p = first_fit(160, [], 30, express_zone=None, is_express=False)
    assert p is not None
    assert p.start_cm == 0


def test_zone_does_not_split_normal_placement_across_boundary():
    """普通衣不得跨越专区边界：[0,60) 专区前不可能有段；外侧 100 起的空隙才可用。"""
    occ = [Segment(60, 100)]
    p = first_fit(160, occ, 40, express_zone=ZONE_0_60, is_express=False)
    assert p is not None
    assert p.start_cm == 100


def test_zone_only_pass_fits_inside_zone():
    """跨杆专区优先轮：专区内有空隙即可放入。"""
    occ = [Segment(0, 25)]
    p = first_fit(160, occ, 20, express_zone=ZONE_0_60, is_express=True, zone_only=True)
    assert p is not None
    assert p.start_cm == 25
    assert p.end_cm == 45


def test_zone_only_pass_none_when_zone_full():
    """专区放不下时，专区优先轮返回 None（即便专区外有大空隙），交由现网轮处理。"""
    occ = [Segment(0, 60)]
    assert first_fit(160, occ, 30, express_zone=ZONE_0_60, is_express=True, zone_only=True) is None


def test_zone_only_without_zone_never_fits():
    """未划专区的杆在专区优先轮不接单。"""
    assert first_fit(200, [], 20, express_zone=None, is_express=True, zone_only=True) is None


def test_valid_zone_rules():
    assert valid_zone(160, None, None) is True
    assert valid_zone(160, 0, 60) is True
    assert valid_zone(160, 0, 160) is True
    assert valid_zone(160, 60, 60) is False       # 空区间
    assert valid_zone(160, 80, 60) is False       # 起点 > 终点
    assert valid_zone(160, 0, 200) is False       # 越过杆长
    assert valid_zone(160, -5, 60) is False       # 负起点
    assert valid_zone(160, 0, None) is False      # 只填一端
