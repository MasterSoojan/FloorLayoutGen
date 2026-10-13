"""Opt-in real Tk wiring checks; ordinary pytest remains display-independent."""

import os
import time

import pytest
from shapely.geometry import Polygon

from floorlayout.models import BlueprintObject, Room


pytestmark = pytest.mark.skipif(
    os.environ.get("FLOORLAYOUT_RUN_DESKTOP") != "1",
    reason="Set FLOORLAYOUT_RUN_DESKTOP=1 with an available desktop display",
)


@pytest.fixture(scope="module")
def window():
    from floorlayout.ui.app import BlueprintApp

    # Do not skip a failed connection after explicit opt-in: it is a failed gate.
    app = BlueprintApp()
    errors = []
    app.report_callback_exception = lambda kind, value, trace: errors.append(value)
    app.geometry("1000x750+30+30")
    app.update()
    try:
        yield app
    finally:
        app.update_idletasks()
        app.destroy()
        assert not errors, f"Tk callback failures: {errors}"


@pytest.fixture
def desktop(window):
    # One interpreter mirrors an app session and avoids ttk's queued theme events
    # targeting a destroyed interpreter between cases. Each layout is disposable.
    app = window
    app.cancel_action()
    app.clear_blueprint(confirm=False)
    app.key_press_event = None
    app.canvas.get_tk_widget().focus_force()
    app.ax.set_xlim(-5, 25)
    app.ax.set_ylim(-5, 25)
    app.canvas.draw()
    app.update()
    return app


def key(app, name, state=0):
    widget = app.canvas.get_tk_widget()
    widget.focus_force()
    # Focus restoration after a real modal is asynchronous at the window manager.
    # Wait for it instead of injecting a key into the just-destroyed dialog.
    deadline = time.monotonic() + 2
    while app.focus_get() is not widget and time.monotonic() < deadline:
        app.update()
        time.sleep(0.01)
    assert app.focus_get() is widget
    widget.event_generate("<KeyPress>", keysym=name, state=state)
    widget.event_generate("<KeyRelease>", keysym=name, state=state)
    app.update()


def pointer(app, event, x, y):
    widget = app.canvas.get_tk_widget()
    px, py = app.ax.transData.transform((x, y))
    widget.event_generate(event, x=round(px), y=round(widget.winfo_height() - py))
    app.update()


def test_canvas_keys_copy_paste_and_history_once(desktop):
    app = desktop
    obj = BlueprintObject("Synthetic desk", 0, 0, 2, 2)
    app.document.add_items([obj])
    app.select_items([obj])
    app.update()
    key(app, "Right")
    assert obj.x == pytest.approx(0.06)
    key(app, "c", state=4)
    assert app.clipboard is not None
    key(app, "v", state=4)
    assert len(app.furnishings) == 2
    key(app, "z", state=4)
    assert app.furnishings == [obj]
    key(app, "y", state=4)
    assert len(app.furnishings) == 2


def test_cancelled_delete_prompts_only_once(desktop, monkeypatch):
    from floorlayout.ui import app as ui

    obj = BlueprintObject("Synthetic desk", 0, 0, 2, 2)
    desktop.document.add_items([obj])
    desktop.select_items([obj])
    prompts = []
    # Keep the real Tk and Matplotlib dispatch; only the user's answer is fake.
    monkeypatch.setattr(
        ui.messagebox, "askyesno", lambda *a, **kw: prompts.append(a) or False
    )
    key(desktop, "Delete")
    assert len(prompts) == 1
    assert desktop.furnishings == [obj]


def test_real_pointer_drag_escape_and_commit(desktop):
    app = desktop
    room = Room.from_box("Synthetic room", 0, 0, 20, 20)
    app.document.add_items([room])
    app.draw_blueprint()
    app.update()
    before = room.get_state()
    pointer(app, "<ButtonPress-1>", 8, 8)
    pointer(app, "<B1-Motion>", 10, 11)
    assert room.bounds[:2] == pytest.approx((2, 3), abs=0.1)
    key(app, "Escape")
    pointer(app, "<ButtonRelease-1>", 10, 11)
    assert room.get_state() == before
    assert len(app.document.history.undo_stack) == 1
    # Stay outside the existing five-unit resize handles on the selected room.
    # A different start pixel also avoids Tk classifying rapid clicks as double.
    pointer(app, "<ButtonPress-1>", 10, 10)
    pointer(app, "<B1-Motion>", 12, 13)
    pointer(app, "<ButtonRelease-1>", 12, 13)
    assert room.bounds[:2] == pytest.approx((2, 3), abs=0.1)
    assert len(app.document.history.undo_stack) == 2
    key(app, "z", state=4)
    assert room.get_state() == before


def test_real_pointer_resize_across_zero(desktop):
    app = desktop
    room = Room.from_box("Synthetic room", 0, 0, 20, 20)
    app.document.add_items([room])
    app.select_items([room])
    app.update()
    before = room.get_state()
    pointer(app, "<ButtonPress-1>", 0, 10)
    assert app.current_action == "resizing_room"
    pointer(app, "<B1-Motion>", -2, 10)
    pointer(app, "<ButtonRelease-1>", -2, 10)
    assert room.bounds == pytest.approx((-2, 0, 20, 20), abs=0.1)
    key(app, "z", state=4)
    assert room.get_state() == before


def test_real_shift_selection_and_mixed_group_drag(desktop):
    app = desktop
    room = Room.from_box("Synthetic room", 0, 0, 10, 10)
    # Keep the object outside the selected room's existing resize-handle region;
    # this case characterizes group selection, not the handle-priority policy.
    obj = BlueprintObject("Synthetic desk", 20, 20, 2, 2)
    app.document.add_items([room, obj])
    app.draw_blueprint()
    app.update()
    pointer(app, "<ButtonPress-1>", 5, 5)
    pointer(app, "<ButtonRelease-1>", 5, 5)
    assert app.selected_items == [room]

    widget = app.canvas.get_tk_widget()
    widget.event_generate("<KeyPress>", keysym="Shift_L")
    app.update()
    pointer(app, "<ButtonPress-1>", 21, 21)
    pointer(app, "<ButtonRelease-1>", 21, 21)
    widget.event_generate("<KeyRelease>", keysym="Shift_L")
    app.update()
    assert app.selected_items == [room, obj]
    before = room.get_state(), obj.get_state()
    pointer(app, "<ButtonPress-1>", 6, 6)
    pointer(app, "<B1-Motion>", 8, 7)
    pointer(app, "<ButtonRelease-1>", 8, 7)
    assert room.bounds[:2] == pytest.approx((2, 1), abs=0.1)
    assert (obj.x, obj.y) == pytest.approx((22, 21), abs=0.1)
    assert app.selected_items == [room, obj]
    assert len(app.document.history.undo_stack) == 2
    key(app, "z", state=4)
    assert (room.get_state(), obj.get_state()) == before


def test_real_shift_marquee_adds_shapes_without_history(desktop):
    app = desktop
    room = Room.from_box("Synthetic room", 0, 0, 10, 10)
    obj = BlueprintObject("Synthetic desk", 15, 15, 2, 2)
    app.document.add_items([room, obj])
    app.draw_blueprint()
    app.update()
    widget = app.canvas.get_tk_widget()
    widget.event_generate("<KeyPress>", keysym="Shift_L")
    app.update()
    pointer(app, "<ButtonPress-1>", -2, -2)
    assert app.current_action == "selecting_area"
    pointer(app, "<B1-Motion>", 20, 20)
    pointer(app, "<ButtonRelease-1>", 20, 20)
    widget.event_generate("<KeyRelease>", keysym="Shift_L")
    app.update()
    assert app.selected_items == [room, obj]
    assert app.selection_marquee is None
    assert len(app.document.history.undo_stack) == 1


def test_real_subtract_reshape_cancel_and_history_preserve_courtyard(desktop):
    app = desktop
    room = Room.from_box("Synthetic courtyard", 0, 0, 20, 20)
    app.document.add_items([room])
    app.select_items([room])
    app.update()
    original = room.get_state()
    app.subtract_room_button.invoke()
    pointer(app, "<ButtonPress-1>", 4, 4)
    pointer(app, "<B1-Motion>", 8, 8)
    pointer(app, "<ButtonRelease-1>", 8, 8)
    assert len(room.polygon.interiors) == 1
    courtyard = Polygon(room.polygon.interiors[0])
    # Tk events round to pixels, so compare the drawn area within pixel error;
    # subsequent shape edits must preserve that actual cutout exactly.
    assert courtyard.area == pytest.approx(16, abs=0.8)
    cut_state = room.get_state()
    app.reshape_room_button.invoke()
    pointer(app, "<ButtonPress-1>", 0, 0)
    assert app.current_action == "reshaping_room"
    pointer(app, "<B1-Motion>", -1, -1)
    key(app, "Escape")
    pointer(app, "<ButtonRelease-1>", -1, -1)
    assert room.get_state() == cut_state
    assert len(app.document.history.undo_stack) == 2

    app.reshape_room_button.invoke()
    pointer(app, "<ButtonPress-1>", 20, 20)
    pointer(app, "<B1-Motion>", 22, 21)
    pointer(app, "<ButtonRelease-1>", 22, 21)
    assert room.polygon.is_valid and room.get_state() != cut_state
    assert Polygon(room.polygon.interiors[0]).equals(courtyard)
    key(app, "z", state=4)
    assert room.get_state() == cut_state
    key(app, "z", state=4)
    assert room.get_state() == original
    key(app, "y", state=4)
    assert room.get_state() == cut_state


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def button(app, label):
    return next(
        widget
        for widget in descendants(app)
        if widget.winfo_class() == "TButton" and widget.cget("text") == label
    )


def complete_dialog(app, launch, values, submit="Add"):
    """Operate real modal widgets without a human or an unbounded failed wait."""
    failures = []
    completed = []

    def interact():
        from floorlayout.ui.dialogs import BaseDialog

        dialog = None
        try:
            dialog = next(
                child for child in app.winfo_children() if isinstance(child, BaseDialog)
            )
            for field, value in values.items():
                entry = dialog.entries[field]
                if field == "Color":
                    entry.set(value)
                else:
                    entry.delete(0, "end")
                    entry.insert(0, str(value))
            entry = next(iter(dialog.entries.values()))
            entry.focus_force()
            app.update()
            assert app.focus_get() is entry
            button(dialog, submit).invoke()
            completed.append(True)
        except Exception as error:
            failures.append(error)
        finally:
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()

    app.after(50, interact)
    launch()
    app.update()
    assert completed and not failures, f"Dialog interaction failed: {failures}"


def test_real_room_and_object_dialogs(desktop):
    app = desktop
    complete_dialog(
        app,
        lambda: button(app, "＋ Add Room...").invoke(),
        {
            "Room Name": "Synthetic room",
            "Start X": 0,
            "Start Y": 0,
            "Width": 20,
            "Height": 15,
            "Color": "Ocean Blue",
        },
    )
    assert app.house[0].bounds == (0, 0, 20, 15)
    complete_dialog(
        app,
        lambda: button(app, "＋ Add Object...").invoke(),
        {
            "Object Name": "Synthetic desk",
            "Center X": 10,
            "Center Y": 8,
            "Width": 4,
            "Height": 2,
            "Color": "Royal Purple",
        },
    )
    obj = app.furnishings[0]
    assert (obj.x, obj.y, obj.width, obj.height) == (8, 7, 4, 2)
    before = obj.get_state()
    complete_dialog(
        app,
        lambda: app.prompt_edit_object_properties(obj),
        {"Center X": 6, "Center Y": 5, "Width": 2},
        "Apply Changes",
    )
    assert (obj.x, obj.y, obj.width, obj.height) == (5, 4, 2, 2)
    key(app, "z", state=4)
    assert obj.get_state() == before


def test_toolbar_exports_actual_canvas(desktop, monkeypatch, tmp_path):
    from tkinter import filedialog

    target = tmp_path / "synthetic-blueprint.png"
    desktop.document.add_items([Room.from_box("Synthetic", 0, 0, 10, 10)])
    desktop.draw_blueprint()
    desktop.update()
    # File chooser appearance still needs human review; never write user files.
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(target))
    desktop.toolbar._buttons["Save"].invoke()
    desktop.update()
    assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert target.stat().st_size > 1000


def test_real_dialog_cancel_and_unchanged_apply_preserve_history(desktop):
    app = desktop
    obj = BlueprintObject("Synthetic desk", 2, 4, 6, 8)
    app.document.add_items([obj])
    app.select_items([obj])
    before = obj.get_state()
    complete_dialog(
        app,
        lambda: app.prompt_edit_object_properties(obj),
        {"Center X": 100, "Width": 12},
        "Cancel",
    )
    assert obj.get_state() == before
    assert len(app.document.history.undo_stack) == 1
    complete_dialog(
        app, lambda: app.prompt_edit_object_properties(obj), {}, "Apply Changes"
    )
    assert obj.get_state() == before
    assert len(app.document.history.undo_stack) == 1
