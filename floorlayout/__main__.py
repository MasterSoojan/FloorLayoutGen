"""Desktop entry point; domain modules remain safe to import in headless tests."""

import sys


def main():
    try:
        from .ui.app import BlueprintApp
    except ImportError as error:
        print(
            f"Cannot start FloorLayoutGen: {error}. Install this project's dependencies and Tk.",
            file=sys.stderr,
        )
        return 1
    app = BlueprintApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
