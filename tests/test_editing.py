"""Headless adapter regressions, not a substitute for real Tk interaction tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from shapely.geometry import Polygon, box

from floorlayout.colors import COLOR_MAP
from floorlayout.document import BlueprintDocument
from floorlayout.models import BlueprintObject, Room


@pytest.fixture
def ui(monkeypatch, tmp_path):
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    from floorlayout.ui import app, dialogs

    return app, dialogs


def test_object_properties_use_center_on_read_and_write(ui, monkeypatch):
    app, _ = ui
    obj = BlueprintObject("Desk", 2, 4, 6, 8)
    before = obj.get_state()
    doc = BlueprintDocument()
    doc.objects.append(obj)
    editor = SimpleNamespace(
        document=doc,
        furnishings=doc.objects,
        selected_items=[obj],
        draw_blueprint=Mock(),
        update_buttons=Mock(),
    )
    dialog = Mock(
        return_value=SimpleNamespace(result=("Desk", 10, -3, 4, 2, obj.color))
    )
    monkeypatch.setattr(app, "ObjectDialog", dialog)
    app.BlueprintApp.prompt_edit_object_properties(editor, obj)
    assert dialog.call_args.args[1] == ("Desk", 5, 8, 6, 8, obj.color)
    assert obj.get_state() == ("Desk", 8, -4, 4, 2, obj.color)
    assert doc.history.undo(doc)
    assert obj.get_state() == before
    assert doc.history.redo(doc)
    assert (obj.x, obj.y) == (8, -4)


def test_reshape_preserves_subtracted_hole(ui):
    app, _ = ui
    polygon = box(0, 0, 20, 20).difference(box(5, 5, 10, 10))
    room = Room("Courtyard", polygon)
    editor = SimpleNamespace(
        document=BlueprintDocument(),
        ax=object(),
        current_action="reshaping_room",
        action_start_xy=(0, 0),
        original_states={room: room.get_state()},
        reshape_vertex_index=0,
        draw_blueprint=Mock(),
    )
    x, y = room.polygon.exterior.coords[0]
    app.BlueprintApp.on_motion(
        editor, SimpleNamespace(inaxes=editor.ax, xdata=x + 1, ydata=y + 1)
    )
    assert room.polygon.is_valid
    assert len(room.polygon.interiors) == 1
    assert Polygon(room.polygon.interiors[0]).equals(box(5, 5, 10, 10))


@pytest.mark.parametrize(
    "field,value",
    [
        ("Room Name", "   "),
        ("Start X", "nan"),
        ("Start Y", "inf"),
        ("Width", "nan"),
        ("Height", "-inf"),
        ("Width", "0"),
        ("Height", "-2"),
        ("Color", "not a palette color"),
    ],
)
def test_dialog_rejects_invalid_properties_without_closing(
    ui, monkeypatch, field, value
):
    _, dialogs = ui
    fields = {
        "Room Name": "Room",
        "Start X": "1",
        "Start Y": "2",
        "Width": "3",
        "Height": "4",
        "Color": next(iter(COLOR_MAP)),
    }
    fields[field] = value
    dialog = SimpleNamespace(
        entries={
            key: Mock(get=Mock(return_value=value)) for key, value in fields.items()
        },
        result=None,
        destroy=Mock(),
    )
    error = Mock()
    monkeypatch.setattr(dialogs.messagebox, "showerror", error)
    dialogs.BaseDialog.on_ok(dialog)
    assert dialog.result is None
    dialog.destroy.assert_not_called()
    error.assert_called_once()


@pytest.mark.parametrize("result", [None, "unchanged"])
def test_cancel_or_unchanged_object_dialog_does_not_record_history(
    ui, monkeypatch, result
):
    app, _ = ui
    obj = BlueprintObject("Desk", -2, -4, 6, 8)
    before = obj.get_state()
    doc = BlueprintDocument()
    editor = SimpleNamespace(document=doc, draw_blueprint=Mock())

    def dialog(parent, properties):
        return SimpleNamespace(result=properties if result == "unchanged" else None)

    monkeypatch.setattr(app, "ObjectDialog", dialog)
    app.BlueprintApp.prompt_edit_object_properties(editor, obj)
    assert obj.get_state() == before
    assert not doc.history.undo_stack


def test_add_object_uses_same_center_contract(ui, monkeypatch):
    app, _ = ui
    doc = BlueprintDocument()
    editor = SimpleNamespace(document=doc, furnishings=doc.objects, select_items=Mock())
    color = next(iter(COLOR_MAP.values()))
    monkeypatch.setattr(
        app,
        "ObjectDialog",
        Mock(return_value=SimpleNamespace(result=("Desk", -2, 0, 4, 6, color))),
    )
    app.BlueprintApp.prompt_add_object_precise(editor)
    (obj,) = editor.furnishings
    assert obj.get_state() == ("Desk", -4, -3, 4, 6, color)
    assert doc.history.undo_stack == [("add", [obj])]
    editor.select_items.assert_called_once_with([obj])


@pytest.mark.parametrize("cancel", [False, True])
def test_reshape_history_and_escape_restore_holes(ui, cancel):
    app, _ = ui
    room = Room("Courtyard", box(0, 0, 20, 20).difference(box(5, 5, 10, 10)))
    doc = BlueprintDocument()
    doc.rooms.append(room)
    before = room.get_state()
    editor = SimpleNamespace(
        document=doc,
        ax=object(),
        current_action="reshaping_room",
        action_start_xy=(0, 0),
        original_states={room: before},
        reshape_vertex_index=0,
        draw_blueprint=Mock(),
        update_buttons=Mock(),
        mode_variables={},
        ghost_rect=None,
        selection_marquee=None,
        resize_handle=None,
        on_motion=Mock(),
    )
    x, y = room.polygon.exterior.coords[0]
    event = SimpleNamespace(inaxes=editor.ax, xdata=x + 1, ydata=y + 1)
    app.BlueprintApp.on_motion(editor, event)
    after = room.get_state()
    assert after != before
    if cancel:
        app.BlueprintApp.cancel_action(editor)
        assert room.get_state() == before
        assert not doc.history.undo_stack
    else:
        app.BlueprintApp.on_release(editor, event)
        assert len(doc.history.undo_stack) == 1
        doc.history.undo(doc)
        assert room.get_state() == before
        doc.history.redo(doc)
        assert room.get_state() == after
        assert len(room.polygon.interiors) == 1
    assert editor.current_action is None


def test_dialog_accepts_negative_coordinates_and_positive_dimensions(ui):
    _, dialogs = ui
    fields = {
        "Object Name": " Desk ",
        "Center X": "-1.5",
        "Center Y": "0",
        "Width": "3",
        "Height": "4",
        "Color": next(iter(COLOR_MAP)),
    }
    dialog = SimpleNamespace(
        entries={
            key: Mock(get=Mock(return_value=value)) for key, value in fields.items()
        },
        result=None,
        destroy=Mock(),
    )
    dialogs.BaseDialog.on_ok(dialog)
    assert dialog.result == ("Desk", -1.5, 0, 3, 4, next(iter(COLOR_MAP.values())))
    dialog.destroy.assert_called_once()


def test_agg_canvas_exports_room_hole_and_furniture_without_mutating_document(
    ui, tmp_path
):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from floorlayout.ui.canvas import render_blueprint

    fig = Figure(figsize=(6, 6))
    canvas = FigureCanvasAgg(fig)
    room = Room("Courtyard", box(0, 0, 20, 20).difference(box(5, 5, 10, 10)))
    obj = BlueprintObject("Desk", 12, 12, 2, 4)
    states = room.get_state(), obj.get_state()
    editor = SimpleNamespace(
        fig=fig,
        ax=fig.add_subplot(),
        canvas=canvas,
        house=[room],
        furnishings=[obj],
        selected_items=[room],
        reshape_mode_active=Mock(get=Mock(return_value=True)),
        total_sqft_label=Mock(),
        ghost_rect=None,
        selection_marquee=None,
    )
    render_blueprint(editor)
    canvas.draw()
    assert len(editor.ax.patches) == 2
    editor.total_sqft_label.config.assert_called_once_with(
        text="Total Area: 375.00 sqft"
    )
    assert (room.get_state(), obj.get_state()) == states
    # Check the actual raster: the cutout must show the canvas background, not fill.
    pixels = canvas.buffer_rgba()
    x, y = editor.ax.transData.transform((7.3, 7.3))
    assert tuple(pixels[pixels.shape[0] - 1 - int(y), int(x), c] for c in range(3)) == (
        0,
        43,
        54,
    )
    output = tmp_path / "blueprint.png"
    fig.savefig(output)
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 1000
