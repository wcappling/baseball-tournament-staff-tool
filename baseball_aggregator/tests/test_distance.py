from baseball_aggregator.distance import estimate_distance_miles


def test_estimates_distance_for_single_city():
    distance = estimate_distance_miles("Madison, AL")
    assert distance is not None
    assert distance < 25


def test_estimates_distance_from_first_city_for_multi_city_location():
    distance = estimate_distance_miles("Scottsboro / Gadsden, AL")
    assert distance is not None
    assert 30 <= distance <= 40


def test_estimates_distance_from_nearest_city_for_comma_delimited_location():
    distance = estimate_distance_miles("Gadsden, Scottsboro, AL")
    assert distance is not None
    assert 30 <= distance <= 40


def test_estimates_distance_for_out_of_state_tournament_locations():
    examples = {
        "Marietta, GA": (120, 135),
        "Jackson, TN": (130, 155),
        "Southaven, MS": (175, 205),
        "Horn Lake, MS": (175, 205),
        "Germantown, TN": (170, 200),
        "Murray and Benton, KY": (140, 175),
    }

    for location, expected_range in examples.items():
        distance = estimate_distance_miles(location)

        assert distance is not None, location
        assert expected_range[0] <= distance <= expected_range[1], location


def test_estimates_distance_for_multi_city_locations_by_nearest_known_city():
    distance = estimate_distance_miles("Fort Payne / Rainsville, AL")

    assert distance is not None
    assert 40 <= distance <= 55


def test_unknown_distance_returns_none():
    assert estimate_distance_miles("Somewhere Else") is None
