"""Pure geometry for geo-fenced attendance: is a GPS point inside a site's
boundary? No database, no HTTP — just the math."""
import pytest

from app.services.geofence import point_in_circle, point_in_polygon

pytestmark = pytest.mark.unit


class TestCircle:
    def test_point_at_center_is_inside(self):
        assert point_in_circle(26.5775, 93.1711, center_lat=26.5775, center_lng=93.1711, radius_m=100)

    def test_point_well_outside_radius_is_outside(self):
        # ~1.1 km north of the center, radius 100 m.
        assert not point_in_circle(26.5875, 93.1711, center_lat=26.5775, center_lng=93.1711, radius_m=100)

    def test_point_just_inside_radius_is_inside(self):
        # ~50 m north, well within a 100 m radius.
        assert point_in_circle(26.57795, 93.1711, center_lat=26.5775, center_lng=93.1711, radius_m=100)

    def test_point_on_the_boundary_counts_as_inside(self):
        # 100 m north is ~0.0009009 degrees of latitude.
        assert point_in_circle(26.5775 + 0.0009009, 93.1711, center_lat=26.5775, center_lng=93.1711, radius_m=100.5)


class TestPolygon:
    # A simple square: (0,0) (0,10) (10,10) (10,0) in (lat, lng).
    SQUARE = [(0, 0), (0, 10), (10, 10), (10, 0)]

    def test_point_inside_square_is_inside(self):
        assert point_in_polygon(5, 5, self.SQUARE)

    def test_point_outside_square_is_outside(self):
        assert not point_in_polygon(20, 20, self.SQUARE)

    def test_point_far_outside_is_outside(self):
        assert not point_in_polygon(-5, -5, self.SQUARE)

    def test_too_few_points_is_never_inside(self):
        assert not point_in_polygon(5, 5, [(0, 0), (0, 10)])

    def test_concave_polygon(self):
        # An L-shape: inside the notch should be outside.
        l_shape = [(0, 0), (0, 10), (10, 10), (10, 5), (5, 5), (5, 0)]
        assert point_in_polygon(2, 2, l_shape)   # inside the foot of the L
        assert not point_in_polygon(8, 2, l_shape)  # inside the notch, outside the shape
