"""Matplotlib rendering; consumes the view state without mutating domain objects."""

import textwrap
import matplotlib.patches as patches
from matplotlib.path import Path
from shapely.geometry import Polygon, MultiPolygon


def render_blueprint(self):
    xlim_before, ylim_before = self.ax.get_xlim(), self.ax.get_ylim()
    self.ax.clear()
    palette = {
        "bg": "#002b36",
        "text": "#EAEAEA",
        "grid": "#4E6A85",
        "room_edge": "#9CC2E5",
        "selected_edge": "#18BC9C",
        "selected_obj_edge": "#F39C12",
        "vertex_handle": "#FFD700",
    }
    self.fig.patch.set_facecolor(palette["bg"])
    self.ax.set_facecolor(palette["bg"])
    self.ax.tick_params(colors=palette["text"], which="both")
    for spine in self.ax.spines.values():
        spine.set_edgecolor(palette["grid"])
    self.ax.set_title(
        "Blueprint View", color=palette["text"], weight="bold", fontsize=16
    )
    self.ax.set_xlabel("Width (feet)", color=palette["text"])
    self.ax.set_ylabel("Height (feet)", color=palette["text"])

    for r in self.house:
        is_selected = r in self.selected_items

        def create_patch_for_polygon(poly):
            path = Path.make_compound_path(
                Path(poly.exterior.coords), *[Path(i.coords) for i in poly.interiors]
            )
            return patches.PathPatch(
                path,
                edgecolor=palette["selected_edge"]
                if is_selected
                else palette["room_edge"],
                facecolor=r.color,
                linewidth=2.5 if is_selected else 1.5,
                alpha=0.9 if is_selected else 0.7,
                zorder=2,
            )

        if isinstance(r.polygon, Polygon):
            self.ax.add_patch(create_patch_for_polygon(r.polygon))
        elif isinstance(r.polygon, MultiPolygon):
            for sub_poly in r.polygon.geoms:
                self.ax.add_patch(create_patch_for_polygon(sub_poly))

        if not r.polygon.is_empty:
            self.ax.text(
                r.polygon.centroid.x,
                r.polygon.centroid.y,
                f"{r.name}\n({r.area:.2f} sqft)",
                ha="center",
                va="center",
                fontsize=8,
                color=palette["text"],
                zorder=5,
                wrap=True,
            )

        if (
            self.reshape_mode_active.get()
            and is_selected
            and isinstance(r.polygon, Polygon)
        ):
            x, y = r.polygon.exterior.xy
            self.ax.plot(
                x, y, "o", color=palette["vertex_handle"], markersize=7, zorder=10
            )

    for obj in self.furnishings:
        is_selected = obj in self.selected_items
        patch = patches.Rectangle(
            (obj.x, obj.y),
            obj.width,
            obj.height,
            edgecolor=palette["selected_obj_edge"] if is_selected else obj.color,
            facecolor=obj.color,
            linewidth=2.2 if is_selected else 1.0,
            zorder=4,
            alpha=0.9 if is_selected else 0.75,
        )
        self.ax.add_patch(patch)
        wrapped_name = "\n".join(textwrap.wrap(obj.name, width=10))
        self.ax.text(
            obj.x + obj.width / 2,
            obj.y + obj.height / 2,
            wrapped_name,
            ha="center",
            va="center",
            fontsize=6,
            color=palette["text"],
            zorder=5,
        )

    # This calculation correctly sums the area of all Room objects from self.house
    # It does NOT include any BlueprintObjects from self.furnishings.
    self.total_sqft_label.config(
        text=f"Total Area: {sum(r.area for r in self.house):.2f} sqft"
    )

    for patch in [self.ghost_rect, self.selection_marquee]:
        if patch and patch not in self.ax.patches:
            self.ax.add_patch(patch)

    all_bounds = [
        i.bounds for i in self.house if i.bounds and not i.polygon.is_empty
    ] + [(o.x, o.y, o.x + o.width, o.y + o.height) for o in self.furnishings]
    is_first = xlim_before == (0.0, 1.0) and ylim_before == (0.0, 1.0)
    if all_bounds:
        min_x = min((b[0] for b in all_bounds), default=0)
        min_y = min((b[1] for b in all_bounds), default=0)
        max_x = max((b[2] for b in all_bounds), default=50)
        max_y = max((b[3] for b in all_bounds), default=50)
        if is_first:
            x_margin = max(5, (max_x - min_x) * 0.1 if max_x > min_x else 0)
            y_margin = max(5, (max_y - min_y) * 0.1 if max_y > min_y else 0)
            self.ax.set_xlim(min_x - x_margin, max_x + x_margin)
            self.ax.set_ylim(min_y - y_margin, max_y + y_margin)
        else:
            self.ax.set_xlim(xlim_before)
            self.ax.set_ylim(ylim_before)
    elif is_first:
        self.ax.set_xlim(0, 50)
        self.ax.set_ylim(0, 50)
    else:
        self.ax.set_xlim(xlim_before)
        self.ax.set_ylim(ylim_before)
    self.ax.set_aspect("equal", adjustable="box")
    self.ax.grid(True, linestyle="--", color=palette["grid"], alpha=0.6, zorder=0)
    self.canvas.draw_idle()
