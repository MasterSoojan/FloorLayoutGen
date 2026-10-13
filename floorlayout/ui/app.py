import tkinter as tk
from tkinter import messagebox, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import OUTLINE, INFO, PRIMARY, SUCCESS, DANGER
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.patches as patches
from ..models import Room, BlueprintObject
from ..document import BlueprintDocument
from ..layout import generate_rooms
from ..geometry import nearest_vertex
from ..properties import object_state_from_center, object_state_to_center
from .dialogs import RoomDialog, ObjectDialog, ToolTip
from .canvas import render_blueprint


class BlueprintApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("FloorLayoutGen")
        self.geometry("1400x900")
        self.document = BlueprintDocument()
        self.house, self.furnishings = self.document.rooms, self.document.objects
        self.selected_items = self.document.selected_items
        self.current_action, self.action_start_xy = None, None
        self.ghost_rect, self.selection_marquee = None, None

        self.draw_mode_active = tk.BooleanVar(value=False)
        self.reshape_mode_active = tk.BooleanVar(value=False)
        self.subtract_mode_active = tk.BooleanVar(value=False)
        self.mode_variables = {
            "draw": self.draw_mode_active,
            "reshape": self.reshape_mode_active,
            "subtract": self.subtract_mode_active,
        }

        self.original_states = {}
        self.resize_handle = None
        self.reshape_vertex_index = None
        self.key_press_event = None
        self.setup_ui()
        self.setup_shortcuts()
        self.draw_blueprint()

    def setup_ui(self):
        self.controls_frame = ttk.Frame(self, padding="15", width=300)
        self.controls_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.controls_frame.pack_propagate(False)
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(
            self.controls_frame,
            text="FloorLayoutGen",
            font=("Helvetica", 18, "bold"),
            bootstyle=INFO,
        ).pack(pady=(0, 20))

        self._create_actions_ui()
        self._create_creative_tools_ui()
        self._create_objects_ui()
        self._create_options_ui()
        self.update_buttons()
        self.fig = plt.Figure()
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_frame)
        self.toolbar = NavigationToolbar2Tk(
            self.canvas, self.canvas_frame, pack_toolbar=False
        )
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.mpl_connect("key_press_event", self.on_key_press)
        self.canvas.mpl_connect("key_release_event", self.on_key_release)
        self.canvas.get_tk_widget().bind("<Button-3>", lambda e: self.select_items([]))

    def _create_actions_ui(self):
        frame = ttk.LabelFrame(self.controls_frame, text="Editing Actions")
        frame.pack(fill=tk.X, pady=(0, 10))
        self.copy_button = self._create_button(
            frame, "⎘ Copy Selection", self.copy_selection, "Ctrl+C", (OUTLINE, INFO)
        )
        self.paste_button = self._create_button(
            frame, "📋 Paste Selection", self.paste_selection, "Ctrl+V", (OUTLINE, INFO)
        )

    def _create_creative_tools_ui(self):
        frame = ttk.LabelFrame(self.controls_frame, text="Creative Tools")
        frame.pack(fill=tk.X, pady=10)
        self.draw_room_button = ttk.Checkbutton(
            frame,
            text="✏️ Draw Room",
            variable=self.draw_mode_active,
            command=lambda: self._on_mode_change("draw"),
            bootstyle="toolbutton-outline",
        )
        self.draw_room_button.pack(fill=tk.X, pady=5)
        ToolTip(self.draw_room_button, "Toggle mode to draw new rooms")
        self.reshape_room_button = ttk.Checkbutton(
            frame,
            text="✨ Reshape Room",
            variable=self.reshape_mode_active,
            command=lambda: self._on_mode_change("reshape"),
            bootstyle="toolbutton-outline",
        )
        self.reshape_room_button.pack(fill=tk.X, pady=5)
        ToolTip(self.reshape_room_button, "Toggle mode to reshape selected room")
        self.subtract_room_button = ttk.Checkbutton(
            frame,
            text="⛔ Subtract from Room",
            variable=self.subtract_mode_active,
            command=lambda: self._on_mode_change("subtract"),
            bootstyle="toolbutton-outline",
        )
        self.subtract_room_button.pack(fill=tk.X, pady=5)
        ToolTip(
            self.subtract_room_button,
            "Draw a rectangle to cut out from the selected room",
        )
        self._create_button(
            frame,
            "＋ Add Room...",
            self.prompt_add_room_precise,
            "Enter",
            (OUTLINE, PRIMARY),
        )
        self._create_button(
            frame, "🏠 Generate House", self.generate_random_layout, None, SUCCESS
        )

    def _create_objects_ui(self):
        frame = ttk.LabelFrame(self.controls_frame, text="Objects")
        frame.pack(fill=tk.X, pady=10)
        self._create_button(
            frame, "＋ Add Object...", self.prompt_add_object_precise, None, INFO
        )

    def _create_options_ui(self):
        frame = ttk.LabelFrame(self.controls_frame, text="Blueprint Info")
        frame.pack(fill=tk.X, pady=10)
        self.total_sqft_label = ttk.Label(
            frame, text="Total Area: 0.00 sqft", font=("Helvetica", 10, "bold")
        )
        self.total_sqft_label.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        self.clear_button = ttk.Button(
            frame,
            text="Clear All",
            command=self.clear_blueprint,
            bootstyle=(OUTLINE, DANGER),
        )
        self.clear_button.pack(side=tk.TOP, fill=tk.X)

    def _create_button(self, parent, text, command, shortcut, bootstyle):
        btn = ttk.Button(parent, text=text, command=command, bootstyle=bootstyle)
        btn.pack(fill=tk.X, pady=5)
        if shortcut:
            ToolTip(btn, text=f"Shortcut: {shortcut}")
        return btn

    def setup_shortcuts(self):
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-y>", self.redo)
        self.bind("<Control-c>", self.copy_selection)
        self.bind("<Control-v>", self.paste_selection)
        self.bind("<Delete>", self.delete_selected_items)
        self.bind("<Escape>", self.cancel_action)
        self.bind("<Return>", lambda e: self.prompt_add_room_precise())

    @property
    def clipboard(self):
        return self.document.clipboard

    def move_selected(self, dx, dy):
        if self.document.move_selected(dx, dy):
            self.update_buttons()
            self.draw_blueprint()

    def prompt_add_room_precise(self):
        dialog = RoomDialog(self)
        if isinstance(dialog.result, tuple):
            name, x, y, w, h, color = dialog.result
            new_room = Room.from_box(name, x, y, w, h, color)
            self.document.add_items([new_room])
            self.update_buttons()
            self.draw_blueprint()

    def prompt_add_object_precise(self):
        dialog = ObjectDialog(self)
        if isinstance(dialog.result, tuple):
            new_obj = BlueprintObject(*object_state_from_center(dialog.result))
            self.document.add_items([new_obj])
            self.select_items([new_obj])

    def copy_selection(self, event=None):
        if self.document.copy_selection():
            self.update_buttons()

    def paste_selection(self, event=None):
        if not self.clipboard:
            return
        x_lim = self.ax.get_xlim()
        y_lim = self.ax.get_ylim()
        view_center_x, view_center_y = (
            (x_lim[0] + x_lim[1]) / 2,
            (y_lim[0] + y_lim[1]) / 2,
        )

        self.document.paste_at(view_center_x, view_center_y)
        self.refresh_selection()

    def generate_random_layout(self):
        if (self.house or self.furnishings) and not messagebox.askyesno(
            "Confirm", "This will clear the current layout. Continue?", parent=self
        ):
            return
        self.clear_blueprint(confirm=False)
        self.document.add_items(generate_rooms())
        self.update_buttons()
        self.draw_blueprint()

    def on_key_press(self, event):
        self.key_press_event = event
        key = event.key

        # Canvas keys also reach the toplevel Tk bindings in setup_shortcuts.
        # Handle shared shortcuts there only: handling Delete here too reopens
        # its confirmation after the user cancels. Canvas-only arrows stay here,
        # so typing in a dialog cannot nudge the selected document shapes.
        if key in ["up", "down", "left", "right"]:
            nudge_amount = 0.06
            key_map = {
                "up": (0, nudge_amount),
                "down": (0, -nudge_amount),
                "left": (-nudge_amount, 0),
                "right": (nudge_amount, 0),
            }
            dx, dy = key_map[key]
            self.move_selected(dx, dy)

    def on_key_release(self, event):
        self.key_press_event = None

    def on_press(self, event):
        if event.inaxes != self.ax or self.toolbar.mode:
            return
        self.action_start_xy = (event.xdata, event.ydata)
        is_shift_pressed = self.key_press_event and self.key_press_event.key == "shift"

        if event.dblclick:
            item = self.find_item_at(event.xdata, event.ydata)
            if isinstance(item, Room):
                self.prompt_edit_room_properties(item)
            elif isinstance(item, BlueprintObject):
                self.prompt_edit_object_properties(item)
            return

        if self.reshape_mode_active.get():
            room, vertex_index = self.find_vertex_at(event.xdata, event.ydata)
            if room and vertex_index is not None:
                self.current_action = "reshaping_room"
                self.reshape_vertex_index = vertex_index
                self.original_states = {room: room.get_state()}
                self.select_items([room])
                return

        elif self.subtract_mode_active.get():
            self.current_action = "subtracting_from_room"
            self.ghost_rect = patches.Rectangle(
                self.action_start_xy,
                0,
                0,
                facecolor="#C0392B",
                alpha=0.5,
                edgecolor="white",
                linestyle="--",
            )
            self.ax.add_patch(self.ghost_rect)
            return

        elif self.draw_mode_active.get():
            self.select_items([])
            self.current_action = "drawing_room"
            self.ghost_rect = patches.Rectangle(
                self.action_start_xy, 0, 0, facecolor="#18BC9C", alpha=0.4
            )
            self.ax.add_patch(self.ghost_rect)
            return

        item_under_cursor = self.find_item_at(event.xdata, event.ydata)
        primary_selection = (
            self.selected_items[0] if len(self.selected_items) == 1 else None
        )

        resize_handle = None
        if not self.reshape_mode_active.get() and isinstance(primary_selection, Room):
            resize_handle = primary_selection.get_resize_handle(
                event.xdata, event.ydata
            )

        if resize_handle:
            self.current_action = "resizing_room"
            self.resize_handle = resize_handle
            self.original_states = {primary_selection: primary_selection.get_state()}
        elif item_under_cursor:
            self.handle_selection(item_under_cursor, is_shift_pressed)
            self.current_action = "moving"
            self.original_states = {
                item: item.get_state() for item in self.selected_items
            }
        elif is_shift_pressed:
            self.current_action = "selecting_area"
            self.selection_marquee = patches.Rectangle(
                self.action_start_xy,
                0,
                0,
                facecolor="cyan",
                alpha=0.2,
                edgecolor="cyan",
                linestyle="--",
            )
            self.ax.add_patch(self.selection_marquee)
        else:
            if not self.find_item_at(event.xdata, event.ydata):
                self.select_items([])
        self.draw_blueprint()

    def on_motion(self, event):
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            self.canvas.get_tk_widget().config(cursor="arrow")
            return

        if self.current_action and self.action_start_xy:
            x, y = event.xdata, event.ydata
            sx, sy = self.action_start_xy
            dx, dy = x - sx, y - sy

            if self.current_action == "selecting_area" and self.selection_marquee:
                self.selection_marquee.set_width(dx)
                self.selection_marquee.set_height(dy)
            elif (
                self.current_action in ("drawing_room", "subtracting_from_room")
                and self.ghost_rect
            ):
                self.ghost_rect.set_width(dx)
                self.ghost_rect.set_height(dy)
            elif self.current_action == "moving" and self.selected_items:
                self.document.preview_move(self.original_states, dx, dy)
            elif self.current_action == "reshaping_room":
                room = list(self.original_states.keys())[0]
                self.document.preview_reshape(room, self.reshape_vertex_index, x, y)
            elif self.current_action == "resizing_room":
                item = list(self.original_states.keys())[0]
                self.document.preview_resize(
                    item, self.original_states[item], self.resize_handle, x, y
                )

            self.draw_blueprint()
            return

        cursor = "arrow"
        if self.draw_mode_active.get() or self.subtract_mode_active.get():
            cursor = "crosshair"
        elif self.reshape_mode_active.get():
            room, _ = self.find_vertex_at(event.xdata, event.ydata)
            cursor = "hand2" if room else "arrow"
        else:
            primary_selection = (
                self.selected_items[0] if len(self.selected_items) == 1 else None
            )
            if isinstance(
                primary_selection, Room
            ) and primary_selection.get_resize_handle(event.xdata, event.ydata):
                cursor = "plus"
            elif self.find_item_at(event.xdata, event.ydata):
                cursor = "fleur"

        self.canvas.get_tk_widget().config(cursor=cursor)

    def on_release(self, event):
        if not self.current_action:
            return

        if self.current_action == "selecting_area" and self.selection_marquee:
            sx, sy = self.action_start_xy
            ex, ey = (
                (event.xdata if event.xdata is not None else sx),
                (event.ydata if event.ydata is not None else sy),
            )
            if self.document.select_area(sx, sy, ex, ey):
                self.refresh_selection()
            self.selection_marquee.remove()

        elif self.current_action == "drawing_room" and self.ghost_rect:
            w, h = self.ghost_rect.get_width(), self.ghost_rect.get_height()
            if abs(w) > 1 and abs(h) > 1:
                sx, sy = self.ghost_rect.get_xy()
                name = simpledialog.askstring(
                    "Room Name", "Enter name for the new room:", parent=self
                )
                if name:
                    new_room = Room.from_box(
                        name, min(sx, sx + w), min(sy, sy + h), abs(w), abs(h)
                    )
                    self.document.add_items([new_room])
            self.ghost_rect.remove()
            self.draw_mode_active.set(False)

        elif self.current_action == "subtracting_from_room" and self.ghost_rect:
            w, h = self.ghost_rect.get_width(), self.ghost_rect.get_height()
            if abs(w) > 0.1 and abs(h) > 0.1:
                sx, sy = self.ghost_rect.get_xy()
                room_to_modify = self.selected_items[0]
                self.document.subtract(room_to_modify, sx, sy, sx + w, sy + h)

            self.ghost_rect.remove()
            self.subtract_mode_active.set(False)

        elif self.current_action in ["moving", "resizing_room", "reshaping_room"]:
            self.document.commit_edit(self.original_states)

        (
            self.current_action,
            self.original_states,
            self.resize_handle,
            self.reshape_vertex_index,
        ) = None, {}, None, None
        self.ghost_rect, self.selection_marquee = None, None
        self.update_buttons()
        self.draw_blueprint()
        self.on_motion(event)

    def on_scroll(self, event):
        if event.inaxes != self.ax:
            return
        cur_xlim, cur_ylim = self.ax.get_xlim(), self.ax.get_ylim()
        scale_factor = 1 / 1.1 if event.button == "up" else 1.1
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        relx, rely = (
            (event.xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0]),
            (event.ydata - cur_ylim[0]) / (cur_ylim[1] - cur_ylim[0]),
        )
        self.ax.set_xlim(
            [event.xdata - new_width * relx, event.xdata + new_width * (1 - relx)]
        )
        self.ax.set_ylim(
            [event.ydata - new_height * rely, event.ydata + new_height * (1 - rely)]
        )
        self.canvas.draw_idle()

    def find_item_at(self, x, y):
        return self.document.find_item_at(x, y)

    def find_vertex_at(self, x, y, tolerance=0.5):
        if len(self.selected_items) == 1 and isinstance(self.selected_items[0], Room):
            room = self.selected_items[0]
            index = nearest_vertex(room.polygon, x, y, tolerance)
            if index is not None:
                return room, index
        return None, None

    def prompt_edit_room_properties(self, room):
        if not room.is_rectangular:
            messagebox.showinfo(
                "Complex Shape",
                "This room has a complex shape. Use Reshape Mode to move corners or Subtract Mode to cut portions.",
                parent=self,
            )
            return

        minx, miny, maxx, maxy = room.bounds
        old_state_tuple = (room.name, minx, miny, maxx - minx, maxy - miny, room.color)
        dialog = RoomDialog(self, old_state_tuple)
        res = dialog.result
        if res == "delete":
            self.document.delete_items([room])
            self.document.select_items([])
            self.refresh_selection()
        elif isinstance(res, tuple) and res != old_state_tuple:
            self.document.edit_room(room, res)
            self.update_buttons()
        self.draw_blueprint()

    def prompt_edit_object_properties(self, obj):
        old_state = obj.get_state()
        old_properties = object_state_to_center(old_state)
        dialog = ObjectDialog(self, old_properties)
        res = dialog.result
        if res == "delete":
            self.document.delete_items([obj])
            self.refresh_selection()
        elif isinstance(res, tuple) and res != old_properties:
            self.document.edit_object(obj, res)
            self.update_buttons()
        self.draw_blueprint()

    def _on_mode_change(self, changed_mode):
        if self.mode_variables[changed_mode].get():
            for mode, var in self.mode_variables.items():
                if mode != changed_mode:
                    var.set(False)
        self.cancel_action(clear_all_modes=False)

    def cancel_action(self, event=None, clear_all_modes=True):
        if self.current_action and self.original_states:
            self.document.restore_states(self.original_states)
            self.original_states = {}

        for patch in [self.ghost_rect, self.selection_marquee]:
            if patch and patch in self.ax.patches:
                patch.remove()

        self.ghost_rect, self.selection_marquee, self.current_action = None, None, None

        if clear_all_modes:
            for var in self.mode_variables.values():
                var.set(False)

        self.update_buttons()
        self.draw_blueprint()

    def undo(self, event=None):
        self.document.undo()
        self.refresh_selection()

    def redo(self, event=None):
        self.document.redo()
        self.refresh_selection()

    def clear_blueprint(self, confirm=True):
        if confirm and not messagebox.askyesno(
            "Confirm",
            "This will clear the layout and all history. Continue?",
            parent=self,
        ):
            return
        self.document.clear()
        self.refresh_selection()

    def delete_selected_items(self, event=None):
        if not self.selected_items:
            return
        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete {len(self.selected_items)} selected item(s)?",
            parent=self,
        ):
            return
        self.document.delete_items(self.selected_items)
        self.refresh_selection()

    def handle_selection(self, item, is_shift_click):
        if self.document.handle_selection(item, is_shift_click):
            self.refresh_selection()

    def select_items(self, items):
        if self.document.select_items(items):
            self.refresh_selection()

    def refresh_selection(self):
        if not (
            len(self.selected_items) == 1 and isinstance(self.selected_items[0], Room)
        ):
            self.reshape_mode_active.set(False)
            self.subtract_mode_active.set(False)
        self.update_buttons()
        self.draw_blueprint()

    def update_buttons(self):
        is_mouse_action_active = self.current_action is not None
        is_drawing = self.draw_mode_active.get()
        is_reshaping = self.reshape_mode_active.get()
        is_subtracting = self.subtract_mode_active.get()

        can_reshape_or_subtract = len(self.selected_items) == 1 and isinstance(
            self.selected_items[0], Room
        )
        can_copy = len(self.selected_items) == 1
        can_paste = self.clipboard is not None

        self.draw_room_button.config(
            state="disabled"
            if is_reshaping or is_subtracting or is_mouse_action_active
            else "normal"
        )
        self.reshape_room_button.config(
            state="disabled"
            if not can_reshape_or_subtract
            or is_drawing
            or is_subtracting
            or is_mouse_action_active
            else "normal"
        )
        self.subtract_room_button.config(
            state="disabled"
            if not can_reshape_or_subtract
            or is_drawing
            or is_reshaping
            or is_mouse_action_active
            else "normal"
        )

        is_any_mode_active = (
            is_drawing or is_reshaping or is_subtracting or is_mouse_action_active
        )
        self.copy_button.config(
            state="disabled" if not can_copy or is_any_mode_active else "normal"
        )
        self.paste_button.config(
            state="disabled" if not can_paste or is_any_mode_active else "normal"
        )

    def draw_blueprint(self):
        render_blueprint(self)
