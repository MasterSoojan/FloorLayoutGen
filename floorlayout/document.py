"""Blueprint selection and edits, independent of widgets and pointer events."""

from shapely.affinity import translate
from shapely.geometry import box
from shapely.wkt import loads as wkt_loads

from .models import Room, BlueprintObject
from .history import History
from .geometry import resize_rectangle, reshape_vertex
from .properties import object_state_from_center, object_state_to_center


class BlueprintDocument:
    def __init__(self):
        self.rooms = []
        self.objects = []
        self.history = History()
        self.selected_items = []
        self.clipboard = None

    def collection_for(self, item):
        return self.rooms if isinstance(item, Room) else self.objects

    def select_items(self, items):
        # Keep list identities stable: the view reads these collections directly.
        # Selection is not an undoable edit and must not invalidate redo history.
        if set(self.selected_items) == set(items):
            return False
        self.selected_items[:] = items
        return True

    def handle_selection(self, item, is_shift_click):
        selection = self.selected_items[:]
        if is_shift_click:
            if item in selection:
                selection.remove(item)
            else:
                selection.append(item)
        elif item not in selection:
            selection = [item]
        return self.select_items(selection)

    def select_area(self, x1, y1, x2, y2):
        region = box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        hits = [item for item in self.rooms if item.polygon.intersects(region)]
        hits.extend(
            item
            for item in self.objects
            if region.intersects(
                box(item.x, item.y, item.x + item.width, item.y + item.height)
            )
        )
        # Area selection adds to the existing group. Use draw order for new hits
        # rather than set iteration, so later group edits have a stable order.
        return self.select_items(
            self.selected_items
            + [item for item in hits if item not in self.selected_items]
        )

    def add_items(self, items):
        items = list(items)
        if not items:
            return
        for item in items:
            self.collection_for(item).append(item)
        self.history.record(("add", items))

    def delete_items(self, items):
        removed = {item: item.get_state() for item in items}
        if not removed:
            return
        for item in removed:
            self.collection_for(item).remove(item)
        self.history.record(("delete", removed))
        self._prune_selection()

    def move_selected(self, dx, dy):
        if not self.selected_items:
            return False
        before = {item: item.get_state() for item in self.selected_items}
        for item in self.selected_items:
            item.translate(dx, dy)
        self.history.record(
            ("batch_edit", before, {item: item.get_state() for item in before})
        )
        return True

    def copy_selection(self):
        if len(self.selected_items) != 1:
            return False
        item = self.selected_items[0]
        # Snapshot values, not a live reference: moving/deleting the source must
        # not change subsequent pastes. WKT preserves polygon holes and islands.
        self.clipboard = (
            "room" if isinstance(item, Room) else "object",
            item.get_state(),
        )
        return True

    def paste_at(self, x, y):
        if self.clipboard is None:
            return None
        kind, state = self.clipboard
        if kind == "room":
            name, wkt, color = state
            polygon = wkt_loads(wkt)
            item = Room(
                f"{name}(copy)",
                translate(
                    polygon, xoff=x - polygon.centroid.x, yoff=y - polygon.centroid.y
                ),
                color,
            )
        else:
            name, _, _, width, height, color = state
            item = BlueprintObject(
                f"{name}(copy)", x - width / 2, y - height / 2, width, height, color
            )
        self.add_items([item])
        self.select_items([item])
        return item

    @staticmethod
    def restore_states(states):
        for item, state in states.items():
            item.update_state(state)

    def preview_move(self, states, dx, dy):
        # Every pointer event is relative to the gesture's starting position,
        # not the previous preview; accumulating deltas would accelerate a drag.
        self.restore_states(states)
        for item in states:
            item.translate(dx, dy)

    @staticmethod
    def preview_resize(room, initial_state, handle, x, y):
        room.polygon = resize_rectangle(wkt_loads(initial_state[1]), handle, x, y)

    @staticmethod
    def preview_reshape(room, index, x, y):
        room.polygon = reshape_vertex(room.polygon, index, x, y)

    def commit_edit(self, before):
        after = {item: item.get_state() for item in before}
        if before == after:
            return False
        # Many previews produce one undo entry on release. Escape restores the
        # captured states instead, leaving both history stacks untouched.
        self.history.record(("batch_edit", before, after))
        return True

    def subtract(self, room, x1, y1, x2, y2):
        before = room.get_state()
        polygon = room.polygon.difference(box(x1, y1, x2, y2))
        if not polygon.is_valid:
            return False
        room.polygon = polygon
        # Preserve the existing valid-cut history behavior, including a cut that
        # misses the room. Empty/multipolygon results remain supported as before.
        self.history.record(("batch_edit", {room: before}, {room: room.get_state()}))
        return True

    def edit_room(self, room, properties):
        if not room.is_rectangular:
            return False
        minx, miny, maxx, maxy = room.bounds
        if properties == (room.name, minx, miny, maxx - minx, maxy - miny, room.color):
            return False
        before = {room: room.get_state()}
        name, x, y, width, height, color = properties
        room.name, room.color = name, color
        room.polygon = box(x, y, x + width, y + height)
        return self.commit_edit(before)

    def edit_object(self, item, properties):
        if properties == object_state_to_center(item.get_state()):
            return False
        before = {item: item.get_state()}
        item.update_state(object_state_from_center(properties))
        return self.commit_edit(before)

    def _prune_selection(self):
        self.select_items(
            [
                item
                for item in self.selected_items
                if item in self.rooms or item in self.objects
            ]
        )

    def undo(self):
        changed = self.history.undo(self)
        self._prune_selection()
        return changed

    def redo(self):
        changed = self.history.redo(self)
        self._prune_selection()
        return changed

    def clear(self):
        self.rooms.clear()
        self.objects.clear()
        self.selected_items.clear()
        self.history.undo_stack.clear()
        self.history.redo_stack.clear()
        # Keep the clipboard so a copied shape can be pasted into a new layout.

    def find_item_at(self, x, y):
        # Objects render above rooms; within each collection the last item wins.
        return next(
            (
                item
                for item in [*reversed(self.objects), *reversed(self.rooms)]
                if item.contains(x, y)
            ),
            None,
        )
