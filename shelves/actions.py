# -*- coding: utf-8 -*-

"""
Context menu actions for the Shelves plugin.
"""

from __future__ import annotations

from typing import Any, List

from PyQt5 import QtWidgets
from picard import log
from picard.ui.itemviews import BaseAction

from .constants import ShelfConstants
from .utils import add_known_shelf, get_known_shelves
from .validators import validate_shelf_name


PLUGIN_NAME = "Shelves"


class SetShelfAction(BaseAction):
    """
    Context menu action: Set shelf name.
    """

    NAME = "Set shelf name..."

    # Type hint for tagger attribute from BaseAction
    tagger: Any

    def callback(self, objs: List[Any]) -> None:
        """
        Handle the action callback.

        Args:
        objs: Selected objects in Picard
        """
        log.debug("%s: SetShelfAction called with %d objects", PLUGIN_NAME, len(objs))

        known_shelves = get_known_shelves()

        dialog = QtWidgets.QInputDialog(self.tagger.window)
        dialog.setWindowTitle("Set Shelf Name")
        dialog.setLabelText("Select or enter shelf name:")
        dialog.setComboBoxItems(known_shelves)
        dialog.setComboBoxEditable(True)
        dialog.setOption(QtWidgets.QInputDialog.UseListViewForComboBoxItems, True)

        layout = dialog.layout()
        validation_label = QtWidgets.QLabel("")
        validation_label.setStyleSheet("QLabel { color: orange; }")
        if layout:
            layout.addWidget(validation_label)

        def on_text_changed(text: str) -> None:
            """Update validation label when text changes."""
            valid, msg = validate_shelf_name(text)
            if msg:
                validation_label.setText(msg)
                style = (
                    "QLabel { color: red; }"
                    if not valid
                    else "QLabel { color: orange; }"
                )
                validation_label.setStyleSheet(style)
            else:
                validation_label.setText("")

        combo = dialog.findChild(QtWidgets.QComboBox)
        if combo:
            combo.currentTextChanged.connect(on_text_changed)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            shelf_name = dialog.textValue().strip()

            if not shelf_name:
                return

            is_valid, message = validate_shelf_name(shelf_name)
            if not is_valid:
                QtWidgets.QMessageBox.warning(
                    self.tagger.window,
                    "Invalid Shelf Name",
                    f"Cannot use this shelf name: {message}",
                )
                return

            for obj in objs:
                self._set_shelf_recursive(obj, shelf_name)

            add_known_shelf(shelf_name)
            log.info(
                "%s: Set shelf to '%s' for %d object(s)",
                PLUGIN_NAME,
                shelf_name,
                len(objs),
            )

    @staticmethod
    def _set_shelf_recursive(obj: Any, shelf_name: str) -> None:
        """
        Set shelf name recursively on all files in an object.

        Args:
            obj: Picard object (album, track, etc.)
            shelf_name: Shelf name to set
        """
        if hasattr(obj, "metadata"):
            obj.metadata[ShelfConstants.TAG_KEY] = shelf_name
            log.debug(
                "%s: Set shelf '%s' on %s",
                PLUGIN_NAME,
                shelf_name,
                type(obj).__name__,
            )

        if hasattr(obj, "iterfiles"):
            for file in obj.iterfiles():
                file.metadata[ShelfConstants.TAG_KEY] = shelf_name
