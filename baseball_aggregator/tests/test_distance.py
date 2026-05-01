from baseball_aggregator.distance import estimate_distance_miles


def test_estimates_distance_for_single_city():
    distance = estimate_distance_miles("Madison, AL")
    assert distance is not None
    assert distance < 25


def test_estimates_distance_from_first_city_for_multi_city_location():
    distance = estimate_distance_miles("Scottsboro / Gadsden, AL")
    assert distance is not None
    assert 30 <= distance <= 40


def test_estimates_distance_from_first_city_for_comma_delimited_location():
    distance = estimate_distance_miles("Gadsden, Scottsboro, AL")
    assert distance is not None
    assert 55 <= distance <= 65


def test_unknown_distance_returns_none():
    assert estimate_distance_miles("Somewhere Else") is None
