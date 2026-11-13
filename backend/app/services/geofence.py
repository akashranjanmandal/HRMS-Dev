"""Is a GPS point inside a site's boundary?

Two shapes, matching what the administrator draws on the map:

- **circle**: a center point and a radius in metres (quick for a single
  building or small camp).
- **polygon**: an ordered ring of (lat, lng) points, for an irregular field
  site boundary.

Distances are small enough (a few kilometres at most) that a flat-earth
approximation is accurate to well under a metre, so this needs no mapping
library — only the haversine distance for circles and a standard
point-in-polygon test for polygons.
"""
import math

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def point_in_circle(lat: float, lng: float, *, center_lat: float, center_lng: float, radius_m: float) -> bool:
    """True if (lat, lng) is within radius_m of the center, boundary inclusive."""
    return haversine_m(lat, lng, center_lat, center_lng) <= radius_m


def point_in_polygon(lat: float, lng: float, points: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test. ``points`` are (lat, lng) pairs in
    order; the ring is implicitly closed (last point connects to the first).
    Fewer than 3 points can never enclose an area."""
    n = len(points)
    if n < 3:
        return False
    inside = False
    x, y = lng, lat
    x1, y1 = points[-1][1], points[-1][0]
    for py, px in points:
        x2, y2 = px, py
        if (y1 > y) != (y2 > y):
            x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersect:
                inside = not inside
        x1, y1 = x2, y2
    return inside
