"""Pure editing rules; this file does not import Tk or Matplotlib."""

import pytest
from shapely.geometry import Polygon, MultiPolygon, box

from floorlayout.colors import COLOR_MAP
from floorlayout.geometry import reshape_vertex
from floorlayout.properties import (
    parse_shape_properties,
    object_state_from_center,
    object_state_to_center,
)


@pytest.mark.parametrize("index", [0, 1, 2, 3, 4])
def test_move_exterior_vertex_keeps_holes_and_closed_ring(index):
    polygon = Polygon(
        [(0, 0), (20, 0), (20, 20), (0, 20)],
        holes=[[(5, 5), (10, 5), (10, 10), (5, 10)]],
    )
    before = polygon.wkt
    x, y = polygon.exterior.coords[index]
    result = reshape_vertex(polygon, index, x + 1, y + 1)
    assert result is not polygon
    assert result.is_valid
    assert result.exterior.coords[0] == result.exterior.coords[-1]
    assert Polygon(result.interiors[0]).equals(box(5, 5, 10, 10))
    assert polygon.wkt == before


@pytest.mark.parametrize(
    "index,x,y",
    [
        (0, 25, 25),  # Self-intersection or excluded hole.
        (0, 15, 15),  # The unchanged hole no longer fits inside the exterior.
        (0, float("nan"), 1),
        (0, 1, float("inf")),
        (-1, 0, 0),
        (99, 0, 0),
    ],
)
def test_invalid_vertex_preview_leaves_last_valid_polygon(index, x, y):
    polygon = Polygon(
        [(0, 0), (20, 0), (20, 20), (0, 20)],
        holes=[[(5, 5), (10, 5), (10, 10), (5, 10)]],
    )
    assert reshape_vertex(polygon, index, x, y) is polygon


@pytest.mark.parametrize("polygon", [Polygon(), MultiPolygon([box(0, 0, 2, 2)])])
def test_unsupported_reshape_is_unchanged(polygon):
    assert reshape_vertex(polygon, 0, 1, 1) is polygon


@pytest.mark.parametrize("x,y,w,h", [(0, 0, 4, 8), (-8, 2, 1, 0.5), (10, -10, 3, 5)])
def test_object_center_conversion_roundtrip(x, y, w, h):
    state = ("Desk", x, y, w, h, "#123456")
    center = object_state_to_center(state)
    assert center[1:3] == (x + w / 2, y + h / 2)
    assert object_state_from_center(center) == state


@pytest.mark.parametrize(
    "values,message",
    [
        (("", "1", "2", "3", "4", "Ocean Blue"), "Name"),
        (("R", "oops", "2", "3", "4", "Ocean Blue"), "numbers"),
        (("R", "1", "2", "3", "4", ""), "color"),
        (("R", "1", "2", "-1", "4", "Ocean Blue"), "positive"),
        (("R", "1e999", "2", "3", "4", "Ocean Blue"), "finite"),
    ],
)
def test_properties_errors_are_domain_rules(values, message):
    with pytest.raises(ValueError, match=message):
        parse_shape_properties(*values)


def test_properties_return_existing_state_shape():
    assert parse_shape_properties(" Kitchen ", "-2", "0", "3.5", "4", "Ocean Blue") == (
        "Kitchen",
        -2.0,
        0.0,
        3.5,
        4.0,
        COLOR_MAP["Ocean Blue"],
    )
