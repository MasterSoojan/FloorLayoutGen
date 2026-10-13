"""Characterize the real handlers with dialogs/rendering replaced, not a Tk window."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from shapely.geometry import box

from floorlayout.document import BlueprintDocument
from floorlayout.models import BlueprintObject, Room


@pytest.fixture
def editor(monkeypatch, tmp_path):
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    from floorlayout.ui.app import BlueprintApp

    # Bypass only window construction; invoke the actual bound event handlers.
    view = object.__new__(BlueprintApp)
    view.document = BlueprintDocument()
    view.house, view.furnishings = view.document.rooms, view.document.objects
    view.selected_items = view.document.selected_items
    view.history = view.document.history.undo_stack
    view.redo_stack = view.document.history.redo_stack
    view.draw_blueprint = Mock()
    view.update_buttons = Mock()
    view.reshape_mode_active = Mock()
    view.subtract_mode_active = Mock()
    view.draw_mode_active = Mock()
    view.mode_variables = {}
    view.current_action = None
    view.original_states = {}
    view.ghost_rect = view.selection_marquee = None
    view.ax = Mock(
        get_xlim=Mock(return_value=(-10, 30)), get_ylim=Mock(return_value=(-20, 60))
    )
    return view


def populate(editor):
    room = Room.from_box("Room", 0, 0, 10, 10)
    obj = BlueprintObject("Desk", 2, 2, 2, 4)
    editor.house.append(room)
    editor.furnishings.append(obj)
    return room, obj


def test_click_shift_toggle_and_selected_group_preservation(editor):
    room, obj = populate(editor)
    editor.handle_selection(room, False)
    editor.handle_selection(obj, True)
    assert editor.selected_items == [room, obj]
    editor.handle_selection(room, False)
    assert editor.selected_items == [room, obj]
    editor.handle_selection(room, True)
    assert editor.selected_items == [obj]
    editor.handle_selection(obj, True)
    assert editor.selected_items == []


def test_nudge_is_one_mixed_selection_history_entry(editor):
    room, obj = populate(editor)
    editor.select_items([room, obj])
    before = room.get_state(), obj.get_state()
    editor.move_selected(-2, 3)
    assert room.bounds == (-2, 3, 8, 13)
    assert (obj.x, obj.y) == (0, 5)
    assert len(editor.history) == 1
    editor.undo()
    assert (room.get_state(), obj.get_state()) == before
    editor.redo()
    assert (obj.x, obj.y) == (0, 5)


@pytest.mark.parametrize("kind", ["room", "object"])
def test_clipboard_is_a_snapshot_pasted_at_view_center(editor, kind):
    room, obj = populate(editor)
    room.polygon = box(0, 0, 20, 20).difference(box(5, 5, 10, 10))
    original = room if kind == "room" else obj
    editor.select_items([original])
    editor.copy_selection()
    original.translate(100, 100)
    editor.paste_selection()
    (copy,) = editor.selected_items
    assert copy is not original
    assert copy.name == original.name + "(copy)"
    if kind == "room":
        assert (copy.polygon.centroid.x, copy.polygon.centroid.y) == pytest.approx(
            (10, 20)
        )
        assert copy.area == 375
        assert len(copy.polygon.interiors) == 1
    else:
        assert (copy.x, copy.y, copy.width, copy.height) == (9, 18, 2, 4)
    editor.undo()
    assert editor.selected_items == []
    editor.redo()
    assert editor.selected_items == []  # Restoring an item does not select it.
    assert copy in editor.house + editor.furnishings


def test_multiselection_copy_keeps_previous_clipboard(editor):
    room, obj = populate(editor)
    editor.select_items([obj])
    editor.copy_selection()
    before = editor.clipboard
    editor.select_items([room, obj])
    editor.copy_selection()
    assert editor.clipboard == before


@pytest.mark.parametrize("accept", [False, True])
def test_delete_confirmation_and_restore_order(editor, monkeypatch, accept):
    from floorlayout.ui import app

    room, obj = populate(editor)
    later = Room.from_box("Later", 0, 0, 10, 10)
    editor.house.append(later)
    editor.select_items([room, obj])
    monkeypatch.setattr(app.messagebox, "askyesno", Mock(return_value=accept))
    editor.delete_selected_items()
    if not accept:
        assert editor.house == [room, later]
        assert editor.selected_items == [room, obj]
        assert not editor.history
        return
    assert editor.house == [later] and not editor.furnishings
    assert editor.selected_items == []
    editor.undo()
    assert editor.house == [
        later,
        room,
    ]  # Legacy restore appends, not original z-order.
    assert editor.furnishings == [obj]
    editor.redo()
    assert editor.house == [later] and not editor.furnishings


def test_clear_keeps_clipboard_but_discards_history(editor):
    room, _ = populate(editor)
    editor.select_items([room])
    editor.copy_selection()
    clipboard = editor.clipboard
    editor.move_selected(1, 0)
    editor.clear_blueprint(confirm=False)
    assert not editor.house and not editor.furnishings
    assert not editor.selected_items and not editor.history and not editor.redo_stack
    assert editor.clipboard == clipboard
    editor.paste_selection()
    assert len(editor.house) == 1


def test_drag_preview_uses_initial_state_and_escape_does_not_commit(editor):
    room, obj = populate(editor)
    editor.select_items([room, obj])
    before = {item: item.get_state() for item in editor.selected_items}
    editor.current_action = "moving"
    editor.action_start_xy = (2, 2)
    editor.original_states = before
    for x, y in ((4, 5), (6, 7)):
        editor.on_motion(SimpleNamespace(inaxes=editor.ax, xdata=x, ydata=y))
    assert room.bounds == (4, 5, 14, 15)
    assert (obj.x, obj.y) == (6, 7)
    editor.cancel_action()
    assert {item: item.get_state() for item in before} == before
    assert not editor.history


@pytest.mark.parametrize(
    "key,callback", [("delete", "delete_selected_items"), ("escape", "cancel_action")]
)
def test_canvas_does_not_repeat_toplevel_shortcuts(editor, monkeypatch, key, callback):
    action = Mock()
    monkeypatch.setattr(editor, callback, action)
    editor.on_key_press(SimpleNamespace(key=key))
    action.assert_not_called()
    assert editor.key_press_event.key == key
    editor.on_key_release(SimpleNamespace(key=key))
    assert editor.key_press_event is None


def test_generated_layout_preserves_templates_and_records_one_add(editor, monkeypatch):
    import random
    from floorlayout.ui import app

    room, _ = populate(editor)
    editor.select_items([room])
    editor.copy_selection()
    clipboard = editor.clipboard
    monkeypatch.setattr(app.messagebox, "askyesno", Mock(return_value=True))
    midpoint = Mock(side_effect=lambda low, high: (low + high) / 2)
    monkeypatch.setattr(random, "uniform", midpoint)
    editor.generate_random_layout()
    assert [(room.name, room.bounds) for room in editor.house] == [
        ("Living Room", (0, 0, 18.5, 15)),
        ("Kitchen", (18.5, 2, 29.5, 13)),
        ("Master Bedroom", (1.75, 15, 16.75, 27.5)),
        ("Bathroom", (18.5, 13, 26, 20.5)),
    ]
    assert midpoint.call_count == 10
    assert not editor.furnishings and not editor.selected_items
    assert editor.clipboard == clipboard
    assert len(editor.history) == 1
    editor.undo()
    assert not editor.house
    editor.redo()
    assert len(editor.house) == 4


def test_generation_cannot_discard_furniture_without_confirmation(editor, monkeypatch):
    from floorlayout.ui import app

    obj = BlueprintObject("Desk", 2, 2, 2, 4)
    editor.furnishings.append(obj)
    editor.select_items([obj])
    ask = Mock(return_value=False)
    monkeypatch.setattr(app.messagebox, "askyesno", ask)
    editor.generate_random_layout()
    ask.assert_called_once()
    assert editor.furnishings == [obj] and not editor.house
    assert editor.selected_items == [obj]
    assert not editor.history


def test_release_commits_one_drag_and_does_not_record_click_only(editor):
    room, obj = populate(editor)
    editor.select_items([room, obj])
    editor.on_motion = Mock()  # Ignore post-release cursor decoration only.
    editor.original_states = {item: item.get_state() for item in (room, obj)}
    editor.current_action = "moving"
    editor.on_release(SimpleNamespace(xdata=0, ydata=0))
    assert not editor.history
    editor.original_states = {item: item.get_state() for item in (room, obj)}
    editor.current_action = "moving"
    editor.document.preview_move(editor.original_states, -2, -2)
    editor.on_release(SimpleNamespace(xdata=0, ydata=0))
    assert len(editor.history) == 1
    assert (obj.x, obj.y) == (0, 0)
    editor.undo()
    assert (obj.x, obj.y) == (2, 2)
    assert editor.current_action is None and editor.original_states == {}


@pytest.mark.parametrize("kind", ["room", "object"])
def test_property_deletion_routes_through_document_and_refreshes_controls(
    editor, monkeypatch, kind
):
    from floorlayout.ui import app

    room, obj = populate(editor)
    editor.select_items([room, obj])
    monkeypatch.setattr(
        app,
        "RoomDialog" if kind == "room" else "ObjectDialog",
        Mock(return_value=SimpleNamespace(result="delete")),
    )
    if kind == "room":
        editor.prompt_edit_room_properties(room)
        assert editor.house == [] and editor.selected_items == []
    else:
        editor.prompt_edit_object_properties(obj)
        assert editor.furnishings == [] and editor.selected_items == [room]
    assert len(editor.history) == 1
    editor.undo()
    assert editor.house == [room] and editor.furnishings == [obj]


def test_marquee_and_subtraction_release_use_document_rules(editor):
    room, obj = populate(editor)
    editor.on_motion = Mock()
    editor.current_action = "selecting_area"
    editor.action_start_xy = (5, 5)
    editor.selection_marquee = Mock()
    editor.on_release(SimpleNamespace(xdata=0, ydata=0))
    assert set(editor.selected_items) == {room, obj}
    assert not editor.history
    editor.select_items([room])
    editor.current_action = "subtracting_from_room"
    editor.ghost_rect = Mock(
        get_width=Mock(return_value=2),
        get_height=Mock(return_value=2),
        get_xy=Mock(return_value=(5, 5)),
    )
    editor.on_release(SimpleNamespace(xdata=7, ydata=7))
    assert room.area == 96 and len(room.polygon.interiors) == 1
    editor.undo()
    assert room.area == 100


def test_cancel_clear_preserves_document_and_history(editor, monkeypatch):
    from floorlayout.ui import app

    room, obj = populate(editor)
    editor.select_items([room])
    editor.move_selected(2, 3)
    before = room.get_state()
    monkeypatch.setattr(app.messagebox, "askyesno", Mock(return_value=False))
    editor.clear_blueprint()
    assert editor.house == [room] and editor.furnishings == [obj]
    assert room.get_state() == before
    assert editor.selected_items == [room] and len(editor.history) == 1
