import sys
import subprocess
from shapely.geometry import Polygon
from floorlayout.models import Room, BlueprintObject
from floorlayout.document import BlueprintDocument
from floorlayout.geometry import nearest_vertex, resize_rectangle


def test_models_do_not_import_tk():
    # Other tests may exercise UI adapters; verify the domain in a fresh process.
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import floorlayout.models, floorlayout.document, "
                "floorlayout.geometry, floorlayout.properties, floorlayout.layout; "
                "assert 'tkinter' not in sys.modules; "
                "assert 'matplotlib.pyplot' not in sys.modules"
            ),
        ],
        check=True,
    )


def test_room_move_and_state_restore():
    room = Room.from_box("Kitchen", 0, 0, 10, 12)
    original = room.get_state()
    room.translate(3, -2)
    assert room.bounds == (3, -2, 13, 10)
    assert room.area == 120
    room.update_state(original)
    assert room.contains(5, 6)
    assert not room.contains(0, 0)  # Existing strict interior-hit behavior.
    assert room.get_state() == original


def test_topmost_object_hit_and_resize_across_origin():
    doc = BlueprintDocument()
    room = Room.from_box("Room", 0, 0, 10, 10)
    obj = BlueprintObject("Desk", 2, 2, 2, 2)
    doc.rooms.append(room)
    doc.objects.append(obj)
    assert doc.find_item_at(3, 3) is obj
    assert doc.find_item_at(8, 8) is room
    assert resize_rectangle(room.polygon, "top-right", -2, -3).bounds == (-2, -3, 0, 0)
    assert nearest_vertex(room.polygon, 0, 0) is not None
    assert nearest_vertex(room.polygon, 5, 5) is None
    assert nearest_vertex(Polygon(), 0, 0) is None


def test_add_delete_edit_roundtrip_and_redo_invalidation():
    doc = BlueprintDocument()
    room = Room.from_box("Room", 0, 0, 10, 10)
    obj = BlueprintObject("Desk", 1, 1, 2, 2)
    doc.rooms.append(room)
    doc.objects.append(obj)
    doc.history.record(("add", [room, obj]))
    assert doc.history.undo(doc)
    assert not doc.rooms and not doc.objects
    assert doc.history.redo(doc)
    before = {item: item.get_state() for item in (room, obj)}
    room.translate(5, 0)
    obj.translate(5, 0)
    after = {item: item.get_state() for item in (room, obj)}
    doc.history.record(("batch_edit", before, after))
    doc.history.undo(doc)
    assert room.get_state() == before[room]
    assert obj.get_state() == before[obj]
    doc.history.redo(doc)
    assert room.get_state() == after[room]
    doc.rooms.remove(room)
    doc.history.record(("delete", {room: room.get_state()}))
    doc.history.undo(doc)
    assert room in doc.rooms
    doc.history.redo(doc)
    assert room not in doc.rooms
    doc.history.undo(doc)
    doc.history.record(("batch_edit", after, after))
    assert not doc.history.redo(doc)
