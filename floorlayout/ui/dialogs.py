import tkinter as tk
from tkinter import messagebox, TclError
import ttkbootstrap as ttk
from ttkbootstrap.constants import SUCCESS, DANGER, INVERSE
from ..colors import COLOR_MAP
from ..properties import parse_shape_properties


class BaseDialog(tk.Toplevel):
    def __init__(self, parent, title, fields, existing_state=None, name_readonly=False):
        super().__init__(parent)
        self.transient(parent)
        self.result = None
        self.title(title)
        self.geometry("350x450")
        body = ttk.Frame(self, padding="15")
        body.pack(expand=True, fill=tk.BOTH)
        self.entries = {}

        self.color_names = list(COLOR_MAP.keys())
        self.hex_to_name = {v: k for k, v in COLOR_MAP.items()}

        for i, field in enumerate(fields):
            ttk.Label(body, text=f"{field}:").grid(
                row=i, column=0, sticky=tk.W, padx=5, pady=8
            )
            if field == "Color":
                entry = ttk.Combobox(
                    body, width=18, values=self.color_names, state="readonly"
                )
            else:
                entry = ttk.Entry(body, width=20)
            entry.grid(row=i, column=1, padx=5, pady=8)
            self.entries[field] = entry

        if existing_state:
            for i, field in enumerate(fields):
                value = existing_state[i]
                if field == "Color":
                    color_name = self.hex_to_name.get(value, "")
                    self.entries[field].set(color_name)
                else:
                    self.entries[field].insert(0, value)

        if name_readonly and "Room Name" in self.entries:
            self.entries["Room Name"].config(state="readonly")

        self.entries[fields[0]].focus_set()
        button_box = ttk.Frame(body)
        button_box.grid(row=len(fields), columnspan=2, pady=20)
        ok_text = "Apply Changes" if existing_state else "Add"
        ttk.Button(
            button_box, text=ok_text, command=self.on_ok, bootstyle=SUCCESS
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_box, text="Cancel", command=self.on_cancel).pack(
            side=tk.LEFT, padx=5
        )
        if existing_state:
            ttk.Button(
                button_box, text="Delete", command=self.on_delete, bootstyle=DANGER
            ).pack(side=tk.LEFT, padx=15)
        self.bind("<Return>", self.on_ok)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def on_ok(self, event=None):
        try:
            self.result = parse_shape_properties(
                *(entry.get() for entry in self.entries.values())
            )
            self.destroy()
        except (ValueError, TclError) as e:
            messagebox.showerror("Input Error", str(e), parent=self)

    def on_delete(self):
        if messagebox.askyesno(
            "Confirm Deletion",
            "Are you sure you want to delete this item?",
            parent=self,
        ):
            self.result = "delete"
            self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()


# --- Specialized Dialogs ---
class RoomDialog(BaseDialog):
    def __init__(self, parent, existing_room_state=None):
        fields = ["Room Name", "Start X", "Start Y", "Width", "Height", "Color"]
        super().__init__(
            parent,
            "Edit Room Properties" if existing_room_state else "Add New Room",
            fields,
            existing_room_state,
        )


class ObjectDialog(BaseDialog):
    def __init__(self, parent, existing_object_state=None):
        title = "Edit Object Properties" if existing_object_state else "Add New Object"
        fields = ["Object Name", "Center X", "Center Y", "Width", "Height", "Color"]
        super().__init__(parent, title, fields, existing_object_state)


class ToolTip:
    def __init__(self, widget, text):
        self.widget, self.text, self.toplevel = widget, text, None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        if self.toplevel:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.toplevel = tk.Toplevel(self.widget)
        self.toplevel.wm_overrideredirect(True)
        self.toplevel.wm_geometry(f"+{x}+{y}")
        ttk.Label(self.toplevel, text=self.text, bootstyle=INVERSE).pack(
            ipadx=5, ipady=5
        )

    def leave(self, event=None):
        if self.toplevel:
            self.toplevel.destroy()
            self.toplevel = None
