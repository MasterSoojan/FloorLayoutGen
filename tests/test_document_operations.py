"""Selection and edit journeys with no Tk, Matplotlib, dialogs or display."""

import pytest
from shapely.geometry import box

from floorlayout.document import BlueprintDocument
from floorlayout.models import Room, BlueprintObject


@pytest.fixture
def blueprint():
    doc = BlueprintDocument()
    room = Room.from_box("Room", 0, 0, 10, 10)
    obj = BlueprintObject("Desk", 2, 2, 2, 4)
    doc.add_items([room, obj])
    return doc, room, obj


def test_selection_preserves_group_and_redo(blueprint):
    doc, room, obj = blueprint
    doc.handle_selection(room, False)
    doc.handle_selection(obj, True)
    doc.handle_selection(room, False)
    assert doc.selected_items == [room, obj]
    doc.move_selected(1, 2)
    doc.undo()
    doc.handle_selection(room, True)
    assert doc.selected_items == [obj]
    doc.redo()
    assert (obj.x, obj.y) == (3, 4)
    assert room.bounds == (1, 2, 11, 12)


def test_area_selection_is_additive_inclusive_and_stable(blueprint):
    doc, room, obj = blueprint
    outside = BlueprintObject("Outside", 20, 20, 1, 1)
    doc.add_items([outside])
    doc.select_items([outside])
    # Reverse-direction drag; touching the object's right edge still selects it.
    assert doc.select_area(5, 3, 4, 2)
    assert doc.selected_items == [outside, room, obj]
    assert not doc.select_area(4, 2, 5, 3)


def test_delete_undo_prunes_selection_and_appends_restored_shape(blueprint):
    doc, room, obj = blueprint
    later = Room.from_box("Later", 0, 0, 10, 10)
    doc.add_items([later])
    doc.select_items([room, obj])
    doc.delete_items(doc.selected_items)
    assert not doc.selected_items
    assert doc.rooms == [later] and not doc.objects
    doc.undo()
    assert doc.rooms == [later, room] and doc.objects == [obj]
    assert not doc.selected_items
    doc.redo()
    assert doc.rooms == [later] and not doc.objects


@pytest.mark.parametrize("kind", ["room", "object"])
def test_copy_is_detached_and_clear_retains_clipboard(blueprint, kind):
    doc, room, obj = blueprint
    room.polygon = room.polygon.difference(box(2, 2, 4, 4))
    source = room if kind == "room" else obj
    doc.select_items([source])
    assert doc.copy_selection()
    snapshot = doc.clipboard
    source.translate(100, 100)
    doc.select_items([room, obj])
    assert not doc.copy_selection()
    assert doc.clipboard == snapshot
    aliases = doc.rooms, doc.objects, doc.selected_items
    doc.clear()
    assert all(
        alias is current
        for alias, current in zip(aliases, (doc.rooms, doc.objects, doc.selected_items))
    )
    assert not doc.undo() and not doc.redo()
    copy = doc.paste_at(-10, 0)
    assert copy.name == source.name + "(copy)" and copy is not source
    assert doc.selected_items == [copy]
    if kind == "room":
        assert len(copy.polygon.interiors) == 1
        assert copy.area == 96
        assert (copy.polygon.centroid.x, copy.polygon.centroid.y) == pytest.approx(
            (-10, 0)
        )
    else:
        assert (copy.x, copy.y, copy.width, copy.height) == (-11, -2, 2, 4)
    assert len(doc.history.undo_stack) == 1


def test_drag_commit_cancel_and_redo_invalidation(blueprint):
    doc, room, obj = blueprint
    before = {item: item.get_state() for item in (room, obj)}
    doc.preview_move(before, 2, 3)
    doc.preview_move(before, -2, -3)
    assert room.bounds == (-2, -3, 8, 7)
    assert (obj.x, obj.y) == (0, -1)
    assert len(doc.history.undo_stack) == 1  # Only the initial add so far.
    doc.restore_states(before)
    assert not doc.commit_edit(before)
    assert len(doc.history.undo_stack) == 1
    doc.preview_move(before, 4, 5)
    assert doc.commit_edit(before)
    assert len(doc.history.undo_stack) == 2
    doc.undo()
    assert {item: item.get_state() for item in before} == before
    doc.select_items([obj])
    doc.move_selected(1, 0)
    assert not doc.redo()


def test_resize_and_subtraction_history(blueprint):
    doc, room, _ = blueprint
    before = room.get_state()
    doc.preview_resize(room, before, "top-right", -10, -10)
    assert room.bounds == (-10, -10, 0, 0)
    doc.preview_resize(room, before, "top-right", 20, 20)
    assert room.bounds == (0, 0, 20, 20)
    doc.commit_edit({room: before})
    assert doc.subtract(room, 5, 5, 10, 10)
    assert room.area == 375 and len(room.polygon.interiors) == 1
    doc.undo()
    assert room.area == 400
    doc.undo()
    assert room.get_state() == before
    doc.redo()
    doc.redo()
    assert room.area == 375


def test_properties_use_center_conversion_and_skip_unchanged_edits(blueprint):
    doc, room, obj = blueprint
    assert not doc.edit_object(obj, ("Desk", 3, 4, 2, 4, obj.color))
    assert not doc.edit_room(room, ("Room", 0, 0, 10, 10, room.color))
    assert len(doc.history.undo_stack) == 1
    assert doc.edit_object(obj, ("Seat", -3, 0, 4, 2, obj.color))
    assert (obj.x, obj.y) == (-5, -1)
    assert doc.edit_room(room, ("Lounge", -10, -10, 20, 20, room.color))
    doc.undo()
    assert room.name == "Room" and room.bounds == (0, 0, 10, 10)
    doc.undo()
    assert obj.name == "Desk" and (obj.x, obj.y) == (2, 2)


def test_empty_operations_are_noops():
    doc = BlueprintDocument()
    assert not doc.copy_selection()
    assert doc.paste_at(0, 0) is None
    assert not doc.move_selected(1, 0)
    doc.add_items([])
    doc.delete_items([])
    assert not doc.commit_edit({})
    assert not doc.undo() and not doc.redo()


def test_layout_random_source_is_reproducible_without_global_state():
    import random
    from floorlayout.layout import generate_rooms

    before = random.getstate()
    first = generate_rooms(random.Random(42))
    second = generate_rooms(random.Random(42))
    assert [item.get_state() for item in first] == [item.get_state() for item in second]
    assert all(a is not b for a, b in zip(first, second))
    assert random.getstate() == before
