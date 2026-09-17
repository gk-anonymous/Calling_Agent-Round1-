from scripts.generate_traffic import target_rate


def test_traffic_profile_baseline_ramp_and_hold():
    assert target_rate(0) == 10
    assert target_rate(8 * 60) == 10
    assert target_rate(8 * 60 + 7.5) == 30
    assert target_rate(8 * 60 + 15) == 50
    assert target_rate(9 * 60) == 50
    assert target_rate(10 * 60) == 10
    assert target_rate(14 * 60 + 15) == 50
    assert target_rate(16 * 60) == 10
    assert target_rate(0, start_hour=8) == 10
    assert target_rate(15, start_hour=8) == 50
