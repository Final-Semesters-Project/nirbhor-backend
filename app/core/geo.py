from typing import cast
from geoalchemy2.shape import to_shape
from shapely.geometry import Point


def to_lat_lng(location) -> tuple[float, float] | None:
    """Geometry column value -> (latitude, longitude)."""
    if location is None:
        return None
    point = cast(Point, to_shape(location))
    return point.y, point.x
