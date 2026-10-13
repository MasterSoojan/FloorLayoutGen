"""Undo/redo for the editor's existing add, delete, and batch-edit actions."""


class History:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def record(self, action):
        self.undo_stack.append(action)
        self.redo_stack.clear()

    def undo(self, document):
        if not self.undo_stack:
            return False
        action = self.undo_stack.pop()
        self._apply(document, action, reverse=True)
        self.redo_stack.append(action)
        return True

    def redo(self, document):
        if not self.redo_stack:
            return False
        action = self.redo_stack.pop()
        self._apply(document, action, reverse=False)
        self.undo_stack.append(action)
        return True

    @staticmethod
    def _apply(document, action, reverse):
        command, *args = action
        if command == "batch_edit":
            for item, state in args[0 if reverse else 1].items():
                item.update_state(state)
            return
        if command not in ("add", "delete"):
            raise ValueError(f"Unknown history action: {command}")
        should_add = (command == "add") != reverse
        for item in args[0]:
            collection = document.collection_for(item)
            if should_add:
                if command == "delete":
                    item.update_state(args[0][item])
                if item not in collection:
                    collection.append(item)
            elif item in collection:
                collection.remove(item)
