# FloorLayoutGen

A Tk/ttkbootstrap desktop floor-plan editor with Matplotlib rendering and Shapely geometry. It supports rectangular and polygon rooms, furniture, move/resize, vertex editing, subtraction, copy/paste, and undo/redo. Coordinates are feet; displayed room area is square feet.

## Setup and run

Python 3.11+ and the system Tk package are required (on Debian/Ubuntu: `python3-tk`). A desktop display is needed to run the editor.

The local suite has passed on Python 3.11 and 3.14. The constraints select NumPy 2.4.6 on Python 3.11 and 2.5.3 on newer supported Python versions, because NumPy 2.5 requires Python 3.12. Keep the environment markers when updating pins; an unconditional newer pin would break the documented minimum runtime.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -c constraints.txt -e '.[dev]'
python -m floorlayout
# Compatibility entry point: python FloorLayoutGen.py
pytest
ruff check .
```

No credentials or environment file are needed. Pure geometry/history/property tests run without Tk or a display:

```sh
pytest tests/test_domain.py tests/test_geometry_properties.py tests/test_document_operations.py
```

The default `pytest` suite also exercises UI handlers with stand-in widgets/dialogs and exports a PNG through Matplotlib's headless Agg renderer. It needs the installed UI libraries, but does not open a window. The separate desktop cases are explicitly skipped unless opted in; headless checks do not verify real Tk event delivery or desktop appearance.

With a working desktop display, run the real-window checks separately (Bash/POSIX syntax):

```sh
FLOORLAYOUT_RUN_DESKTOP=1 pytest tests/test_desktop.py
```

These tests open and focus a temporary app window with synthetic layouts, exercise Tk/Matplotlib keyboard and pointer dispatch, room/object modal forms and toolbar PNG export, then close the window. Do not interact with that window while the suite runs. An unavailable display fails an explicitly opted-in run rather than silently skipping it. Confirmation responses and the export filename are supplied by tests; they do not validate native confirmation/file-chooser appearance, broad desktop ergonomics, every window manager or human visual acceptance. Images are written only to pytest's temporary directory. Other desktop applications are not manipulated.

Real-event coverage also includes Shift-click mixed selection, marquee selection, group drag/undo, courtyard subtraction, cancelled/committed vertex reshaping with hole preservation, and cancelled/unchanged object-property forms. The existing room resize handles take priority within a five-coordinate-unit tolerance; group-selection tests deliberately use separate hit regions. That interaction policy has not been redesigned.

For desktop acceptance, add a room and object, move each, undo/redo, resize through the zero axes, try reshape/subtract, and clear the layout. In particular, subtract an interior courtyard and reshape an outer corner: the cutout must remain. Edit furniture's center and dimensions, then cancel, apply and undo/redo; unchanged properties must not move it or add history. Try blank names, `nan`, infinity and nonpositive dimensions; invalid drafts must remain open with an error. Use the Matplotlib toolbar to save an image; document save/load is not implemented.

To verify wheel packaging separately (build dependencies may need network access):

```sh
python -m pip wheel --no-deps --wheel-dir dist .
```

This creates a Python wheel, not a standalone desktop executable; the destination still needs Python, Tk and the runtime dependencies.

## Structure and maintenance

- `FloorLayoutGen.py`: compatibility launcher; `floorlayout/__main__.py`: dependency errors and GUI startup.
- `models.py`, `geometry.py`: shape state and pure interaction calculations.
- `properties.py`: shared room/object form validation and explicit center-to-corner furniture conversion.
- `document.py`: room/object and selection ownership, clipboard snapshots, edits/previews, and undo/redo coordination; no widget or display dependencies.
- `layout.py`: the existing four-room sample generator, with a supplied random source for reproducible tests.
- `history.py`: existing add/delete/batch-edit actions, without UI dependencies.
- `ui/app.py`: Tk controls, pointer/keyboard gesture state, confirmation dialogs, viewport coordinates and refreshes; `ui/dialogs.py`: form dialogs/tooltips.
- `ui/canvas.py`: Matplotlib presentation; `colors.py`: shared room/furniture colors.

Add business behavior in domain modules and cover it before connecting the GUI. UI gesture state stays in the app. The action tuple protocol is intentionally small; there is no command-plugin framework. Clear and random generation discard previous history after confirmation. Undoing a deletion appends the restored shape, matching the legacy draw-order behavior.

Selection changes do not consume undo entries or clear redo. Clicking an already selected shape keeps its group; Shift toggles membership and a marquee adds intersecting shapes. Newly selected marquee hits now use stable draw order instead of unordered set iteration. Undo/redo remove selection references to absent shapes without automatically selecting restored shapes. The UI reads the document's collection/selection lists; document operations retain those list identities.

Copy captures one shape's state, not a live reference, and paste centers that snapshot in the current viewport. Clear retains the clipboard. Drag previews use the original gesture state; release records one changed edit and Escape restores the original without adding history. Domain tests cover these rules without GUI libraries; handler tests exercise their UI wiring with stand-in dialogs/rendering, including confirmations and release/cancel behavior. The renderer, widget layout and shortcuts were not redesigned.

Generate House now also asks for confirmation when only furniture exists: previously it could silently discard that layout because the guard checked rooms alone. The sample generator's four templates, ranges and random draw order are unchanged; this is not an architectural-validity or non-overlap solver. No document save/load capability was added.

Room forms use the lower-left start position. Object forms use the center consistently for both creation and editing; internal furniture/history tuples still use the lower-left corner. Form names are trimmed and required; coordinates/dimensions must be finite numbers, dimensions positive and colors from the existing palette. Vertex reshaping edits only a single polygon's exterior, preserves existing holes and keeps the last valid shape when a proposed move would self-intersect or exclude a hole. Multipolygon vertex editing is not supported. These intentionally fix the previous inconsistent object editor and hole-losing reshape behavior without changing the history format.

Shortcuts: Ctrl+C/V copy/paste, Ctrl+Z/Y undo/redo, arrows nudge, Delete removes selection, Escape cancels, Enter opens Add Room. Shift supports multiple selection. Double-click opens properties; the scroll wheel zooms.

Shared shortcuts are handled once by the root Tk bindings. Matplotlib's canvas key callback tracks modifiers and handles canvas-only arrow nudges; it must not repeat Delete/Escape, because canvas events also reach the root. This fixes the repeated deletion confirmation that previously appeared after cancelling a canvas Delete action. Dialog text-entry arrows do not nudge the drawing.
