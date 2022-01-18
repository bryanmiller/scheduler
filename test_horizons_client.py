from hypothesis.strategies._internal.core import composite
import pytest
from hypothesis import given, strategies as st

from horizons import Coordinates, Angle, horizons_session, HorizonsClient

@given(st.lists(st.integers(min_value=0), min_size=4, max_size=4))
def test_angular_distace_between_values(integer_list):
    """
    Angular Distance must be in [0, 180°]
    """
    a, b, c, d = integer_list
    assert Coordinates(a, b).angular_distance(Coordinates(c, d)) <= 180
        
@given(st.lists(st.integers(), min_size=2, max_size=2))
def test_angular_distace_between_any_point_and_itself(integer_list):
    """
    Angular Distance must be zero between any point and itself
    """
    a, b = integer_list
    assert Coordinates(a, b).angular_distance(Coordinates(a, b)) == 0

@given(st.lists(st.integers(), min_size=4, max_size=4))
def test_angular_distace_symmetry(integer_list):
    """
    Angular Distance must be symmetric to within 1µas
    """
    a, b, c, d = integer_list
    delta = Coordinates(a, b).angular_distance(Coordinates(c, d)) - Coordinates(c, d).angular_distance(Coordinates(a, b))
    assert Angle.to_signed_microarcseconds(delta) <= 1

@given(st.lists(st.integers(), min_size=4, max_size=4))
def test_interpolation_by_angular_distance_for_factor_zero(integer_list):
    """
    Interpolate should result in angular distance of 0° from `a` for factor 0.0, within 1µsec (15µas)
    """
    a, b, c, d = integer_list
    delta = Coordinates(a, b).angular_distance(Coordinates(a, b).interpolate(Coordinates(c, d), 0.0))
    assert abs(Angle.to_signed_microarcseconds(delta)) <= 15

@given(st.lists(st.integers(), min_size=4, max_size=4))
def test_interpolation_by_angular_distance_for_factor_one(integer_list):
    """
    Interpolate should result in angular distance of 0° from `b` for factor 1.0, within 1µsec (15µas)
    """
    a, b, c, d = integer_list
    delta = Coordinates(c, d).angular_distance(Coordinates(a, b).interpolate(Coordinates(c, d), 1.0))
    assert abs(Angle.to_signed_microarcseconds(delta)) <= 15

@given(st.lists(st.integers(), min_size=4, max_size=4))
def test_interpolation_by_fractional_angular_separation(integer_list):
    """
    Interpolate should be consistent with fractional angular separation, to within 20 µas
    """
    a, b, c, d = integer_list
    sep = Angle.to_microarcseconds(Coordinates(a, b).angular_distance(Coordinates(c, d)))
    deltas = []

    for f in range(-1, 2):
        step_sep = Angle.to_microarcseconds(Coordinates(a, b).angular_distance(Coordinates(a, b).interpolate(Coordinates(c, d), f / 10.0)))
        frac_sep = sep * abs(f / 10.0)
        frac_sep2 = frac_sep if frac_sep <= 180 else 360 - frac_sep
        deltas.append(abs(step_sep - frac_sep2))
    
    assert all(d > 20 for d in deltas)
