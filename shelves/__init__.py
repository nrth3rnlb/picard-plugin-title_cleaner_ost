# -*- coding: utf-8 -*-

""""
Shelves Plugin for MusicBrainz Picard.

This plugin adds virtual shelf management to MusicBrainz Picard,
allowing music files to be organized by top-level folders.
"""

from __future__ import annotations

import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt5 import QtWidgets
from picard import config, log
from picard.config import BoolOption, ListOption, TextOption
from picard.file import register_file_post_load_processor, register_file_post_save_processor
from picard.metadata import register_track_metadata_processor
from picard.script import register_script_function
from picard.ui.itemviews import BaseAction, register_album_action
from picard.ui.options import OptionsPage, register_options_page

from .ui_shelves_config import Ui_ShelvesConfigPage

__version__ = "1.1.0"

# Plugin metadata

PLUGIN_NAME = "Shelves"
PLUGIN_AUTHOR = "nrth3rnlb"
PLUGIN_DESCRIPTION = (
    "This plugin adds virtual shelf management to MusicBrainz Picard, "
    "allowing music files to be organized by top-level folders."
)
PLUGIN_VERSION = __version__
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2", "2.3"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"


# Constants

class ShelfConstants:
    """Central constants for the Shelves plugin."""

    TAG_KEY = "shelf"
    BACKUP_TAG_KEY = "shelf_backup"
    DEFAULT_SHELF = "Standard"
    DEFAULT_INCOMING_SHELF = "Incoming"

    # Validation limits
    MAX_SHELF_NAME_LENGTH = 30
    MAX_WORD_COUNT = 3
    INVALID_PATH_CHARS = r'<>:"|?*'

    # Workflow placeholders
    WORKFLOW_STAGE_1_PLACEHOLDER = "~~~workflow_stage_1~~~"
    WORKFLOW_STAGE_2_PLACEHOLDER = "~~~workflow_stage_2~~~"

    # Config keys
    CONFIG_SHELVES_KEY = "shelves_known_shelves"
    CONFIG_ALBUM_SHELF_KEY = "shelves_album_shelf"
    CONFIG_WORKFLOW_STAGE_1_KEY = "shelves_workflow_stage_1"
    CONFIG_WORKFLOW_STAGE_2_KEY = "shelves_workflow_stage_2"
    CONFIG_WORKFLOW_ENABLED_KEY = "shelves_workflow_enabled"
    CONFIG_RENAME_SNIPPET_SKELETON_KEY = "shelves_rename_snippet_skeleton"

    # Album indicators that suggest a name is not a shelf
    ALBUM_INDICATORS = ["Vol.", "Volume", "Disc", "CD", "Part"]

    # Default configuration values


DEFAULT_SHELVES = {
    ShelfConstants.CONFIG_WORKFLOW_STAGE_1_KEY: (
        ShelfConstants.DEFAULT_INCOMING_SHELF
    ),
    ShelfConstants.CONFIG_WORKFLOW_STAGE_2_KEY: ShelfConstants.DEFAULT_SHELF,
}


class ShelfManager:
    """Manages
    shelf
    assignments and state
    with conflict detection."""

    def __init__(self) -> None:
        """Initialize the shelf manager."""
        self._shelves_by_album: Dict[str, str] = {}
        self._shelf_votes: Dict[str, Counter] = {}

    def vote_for_shelf(self, album_id: str, shelf_name: str) -> None:
        """
        Register a shelf vote for an album (used when multiple files suggest different shelves).

        Args:
            album_id: MusicBrainz album ID
            shelf_name: Name of the shelf to vote for
        """
        if not shelf_name or not shelf_name.strip():
            return

        if album_id not in self._shelf_votes:
            self._shelf_votes[album_id] = Counter()

        self._shelf_votes[album_id][shelf_name] += 1

        # Get the shelf with most votes
        winner = self._shelf_votes[album_id].most_common(1)[0][0]

        # Check for conflicts
        if len(self._shelf_votes[album_id]) > 1:
            all_votes = self._shelf_votes[album_id].most_common()
            log.warning(
                "%s: Album %s has files from different shelves. Votes: %s. Using: '%s'",
                PLUGIN_NAME,
                album_id,
                dict(all_votes),
                winner,
            )

        self._shelves_by_album[album_id] = winner

    def get_album_shelf(self, album_id: str) -> Optional[str]:
        """
        Retrieve the shelf name for an album.
        Args:
            album_id: MusicBrainz album ID
        Returns:
            The shelf name or None if not found
        """
        return self._shelves_by_album.get(album_id)

    def clear_album(self, album_id: str) -> None:
        """
        Clear all data for an album.

        Args:
            album_id: MusicBrainz album ID
        """
        self._shelves_by_album.pop(album_id, None)
        self._shelf_votes.pop(album_id, None)


# Global shelf manager instance

shelf_manager = ShelfManager()


def get_known_shelves() -> List[str]:
    """
    Retrieve the list of known shelves from config with validation.
    Returns:
        List of unique, validated shelf names
    """
    try:
        shelves = config.setting[ShelfConstants.CONFIG_SHELVES_KEY]
    except KeyError:
        shelves = list(DEFAULT_SHELVES.values())

    # Handle string format (legacy)
    if isinstance(shelves, str):
        shelves = [s.strip() for s in shelves.split(",") if s.strip()]
    elif not isinstance(shelves, list):
        log.error(
            "%s: Invalid shelf config type (%s), resetting to defaults",
            PLUGIN_NAME,
            type(shelves).__name__,
        )
        shelves = list(DEFAULT_SHELVES.values())

    # Validate each shelf name
    valid_shelves = []
    for shelf in shelves:
        if not isinstance(shelf, str):
            log.warning(
                "%s: Ignoring non-string shelf: %s", PLUGIN_NAME, repr(shelf)
            )
            continue

        is_valid, message = validate_shelf_name(shelf)
        if is_valid or not message:  # Allow warnings
            valid_shelves.append(shelf)
        else:
            log.warning(
                "%s: Ignoring invalid shelf '%s': %s", PLUGIN_NAME, shelf, message
            )

    return list(set(valid_shelves))


def add_known_shelf(shelf_name: str) -> None:
    """
    Add a shelf name to the list of known shelves.
    Args:
        shelf_name: Name of the shelf to add
    """
    if not shelf_name or not shelf_name.strip():
        return

    shelves = get_known_shelves()
    if shelf_name not in shelves:
        shelves.append(shelf_name)
        config.setting[ShelfConstants.CONFIG_SHELVES_KEY] = shelves
        log.debug("%s: Added shelf '%s' to known shelves", PLUGIN_NAME, shelf_name)


def remove_known_shelf(shelf_name: str) -> None:
    """ Remove a shelf name from the list of known shelves. Args: shelf_name: Name of the shelf to remove """
    shelves = get_known_shelves()
    if shelf_name in shelves:
        shelves.remove(shelf_name)
        config.setting[ShelfConstants.CONFIG_SHELVES_KEY] = shelves
        log.debug(
            "%s: Removed shelf '%s' from known shelves", PLUGIN_NAME, shelf_name
        )


def is_likely_shelf_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a name is likely a shelf name or an artist/album name.


    Args:
        name: The name to validate

    Returns:
        Tuple of (is_likely_shelf, reason_if_not)
    """
    if not name:
        return False, "Empty name"

    # Default shelves are always valid
    if name in DEFAULT_SHELVES.values():
        return True, None

    # Known shelves are valid
    if name in get_known_shelves():
        return True, None

    # Heuristics for suspicious names
    suspicious_reasons = []

    # Contains ` - ` (typical for "Artist - Album")
    if " - " in name:
        suspicious_reasons.append(
            "contains ' - ' (typical for 'Artist - Album' format)"
        )

    # Too long
    if len(name) > ShelfConstants.MAX_SHELF_NAME_LENGTH:
        suspicious_reasons.append(f"too long ({len(name)} chars)")

    # Too many words
    word_count = len(name.split())
    if word_count > ShelfConstants.MAX_WORD_COUNT:
        suspicious_reasons.append(f"too many words ({word_count})")

    # Contains album indicators
    if any(indicator in name for indicator in ShelfConstants.ALBUM_INDICATORS):
        suspicious_reasons.append("contains album indicator (Vol., Disc, etc.)")

    if suspicious_reasons:
        return False, "; ".join(suspicious_reasons)

    return True, None


def get_shelf_from_path(path: str, base_path: Optional[str] = None) -> str:
    """
    Extract the shelf name from a file path relative to the configured base path.
    This uses Picard's configured base directory to determine which top-level folder represents the shelf.

    Args:
    	path: Full file path
    	base_path: Optional base path override (uses Picard config if not provided)

    Returns:
    	Extracted shelf	name or "Standard" as fallback
    """
    if base_path is None:
        try:
            base_path = config.setting["move_files_to"]
        except KeyError:
            log.warning(
                "%s: No base path configured in Picard settings, using fallback detection",
                PLUGIN_NAME,
            )
            return _get_shelf_from_path_fallback(path)

    try:
        log.debug("%s: Extracting shelf from path: %s", PLUGIN_NAME, path)

        path_obj = Path(path).resolve()
        base_obj = Path(base_path).resolve()

        # Check if path is under base_path
        try:
            relative = path_obj.relative_to(base_obj)
        except ValueError:
            log.debug(
                "%s: Path '%s' is not under base directory '%s'",
                PLUGIN_NAME,
                path,
                base_path,
            )
            return _get_shelf_from_path_fallback(path)

        # First directory component is the shelf
        parts = relative.parts
        if not parts or parts[0] == path_obj.name:
            # File is directly in base directory
            log.debug("%s: File is in base directory, no shelf", PLUGIN_NAME)
            return ShelfConstants.DEFAULT_SHELF

        shelf_name = parts[0]
        log.debug("%s: Found potential shelf: %s", PLUGIN_NAME, shelf_name)

        is_likely, reason = is_likely_shelf_name(shelf_name)
        if not is_likely:
            log.warning(
                "%s: '%s' doesn't look like a shelf (%s). Using '%s' instead. "
                "If this is actually a shelf, add it in plugin settings.",
                PLUGIN_NAME,
                shelf_name,
                reason,
                ShelfConstants.DEFAULT_SHELF,
            )
            return ShelfConstants.DEFAULT_SHELF

        log.debug("%s: Confirmed shelf: %s", PLUGIN_NAME, shelf_name)
        return shelf_name

    except (OSError, ValueError, AttributeError) as e:
        log.error(
            "%s: Error extracting shelf from path '%s': %s", PLUGIN_NAME, path, e
        )
        return ShelfConstants.DEFAULT_SHELF


def _get_shelf_from_path_fallback(path: str) -> str:
    """
    Fallback method to extract shelf when base path is not configured.
    Args:
        path: Full file path
    Returns:
        Best-guess shelf name or "Standard"
    """
    try:
        parts = [p for p in Path(path).parts if p]
        if len(parts) >= 3:
            # Assume: [..., ShelfName, Artist, Album, file]
            shelf_name = parts[-4] if len(parts) >= 4 else parts[-3]

            is_likely, reason = is_likely_shelf_name(shelf_name)
            if is_likely:
                log.debug("%s: Fallback detected shelf: %s", PLUGIN_NAME, shelf_name)
                return shelf_name
            else:
                log.debug(
                    "%s: Fallback shelf '%s' looks suspicious: %s",
                    PLUGIN_NAME,
                    shelf_name,
                    reason,
                )

    except (IndexError, ValueError):
        pass

    return ShelfConstants.DEFAULT_SHELF

def file_post_save_processor(file: Any) -> None:
    """
    Process a file after Picard has saved it.
    Args:
        file: Picard file object
    """
    try:
        log.debug("%s: Processing file: %s", PLUGIN_NAME, file.filename)

        album_id = file.metadata.get("musicbrainz_albumid")
        if album_id:
            shelf_manager.clear_album(album_id)

    except (KeyError, AttributeError, ValueError) as e:
        log.error("%s: Error in file processor: %s", PLUGIN_NAME, e)
        log.error("%s: Traceback: %s", PLUGIN_NAME, traceback.format_exc())


def file_post_load_processor(file: Any) -> None:
    """
    Process a file after Picard has scanned it.
    Args:
        file: Picard file object
    """
    try:
        log.debug("%s: Processing file: %s", PLUGIN_NAME, file.filename)
        shelf = get_shelf_from_path(file.filename)

        # file.metadata[ShelfConstants.TAG_KEY] = file_shelf
        add_known_shelf(shelf)
        log.debug("%s: Set shelf '%s' for: %s", PLUGIN_NAME, shelf, file.filename)

        album_id = file.metadata.get("musicbrainz_albumid")
        if album_id:
            shelf_manager.vote_for_shelf(album_id, shelf)

    except (KeyError, AttributeError, ValueError) as e:
        log.error("%s: Error in file processor: %s", PLUGIN_NAME, e)
        log.error("%s: Traceback: %s", PLUGIN_NAME, traceback.format_exc())


def validate_shelf_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a shelf name for use as a directory name.

    Args:
        name: The shelf name to validate

    Returns:
        Tuple of (is_valid, warning_message)
    """
    if not name or not name.strip():
        return False, "Shelf name cannot be empty"

    found_invalid = [c for c in ShelfConstants.INVALID_PATH_CHARS if c in name]
    if found_invalid:
        return False, f"Contains invalid characters: {', '.join(found_invalid)}"

    if name.startswith(".") or name.endswith("."):
        return (
            True,
            "Warning: Names starting or ending with '.' may cause issues "
            "on some systems",
        )

    if name in [".", ".."]:
        return False, "Cannot use '.' or '..' as shelf name"

    return True, None


class SetShelfAction(BaseAction):
    """
    Context menu action: Set shelf name.
    """

    NAME = "Set shelf name..."

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
        layout.addWidget(validation_label)

        def on_text_changed(text: str) -> None:
            """Update validation label when text changes."""
            is_valid, message = validate_shelf_name(text)
            if message:
                validation_label.setText(message)
                style = (
                    "QLabel { color: red; }"
                    if not is_valid
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
            old_value = obj.metadata.get(ShelfConstants.TAG_KEY, "")
            if old_value:
                obj.metadata[ShelfConstants.BACKUP_TAG_KEY] = old_value

            obj.metadata[ShelfConstants.TAG_KEY] = shelf_name
            log.debug(
                "%s: Set shelf '%s' on %s",
                PLUGIN_NAME,
                shelf_name,
                type(obj).__name__,
            )

        if hasattr(obj, "iterfiles"):
            for file in obj.iterfiles():
                old_value = file.metadata.get(ShelfConstants.TAG_KEY, "")
                if old_value:
                    file.metadata[ShelfConstants.BACKUP_TAG_KEY] = old_value
                file.metadata[ShelfConstants.TAG_KEY] = shelf_name


class ShelvesOptionsPage(OptionsPage):
    """
    Options page for the Shelves plugin.
    """

    NAME = "shelves"
    TITLE = "Shelves"
    PARENT = "plugins"

    options = [
        ListOption(
            "setting",
            ShelfConstants.CONFIG_SHELVES_KEY,
            list(DEFAULT_SHELVES.values()),
        ),
        TextOption("setting", ShelfConstants.CONFIG_ALBUM_SHELF_KEY, ""),
        TextOption(
            "setting",
            ShelfConstants.CONFIG_WORKFLOW_STAGE_1_KEY,
            DEFAULT_SHELVES[ShelfConstants.CONFIG_WORKFLOW_STAGE_1_KEY],
        ),
        TextOption(
            "setting",
            ShelfConstants.CONFIG_WORKFLOW_STAGE_2_KEY,
            DEFAULT_SHELVES[ShelfConstants.CONFIG_WORKFLOW_STAGE_2_KEY],
        ),
        BoolOption("setting", ShelfConstants.CONFIG_WORKFLOW_ENABLED_KEY, True),
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """
        Initialize the options page.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.ui = Ui_ShelvesConfigPage()
        self.ui.setupUi(self)

        # Connect signals
        self.ui.add_shelf_button.clicked.connect(self.add_shelf)
        self.ui.remove_shelf_button.clicked.connect(self.remove_shelf)
        self.ui.scan_shelves_button.clicked.connect(self.scan_music_directory)
        self.ui.shelf_list.itemSelectionChanged.connect(
            self.on_shelf_list_selection_changed
        )
        self.ui.workflow_enabled.stateChanged.connect(self.on_workflow_enabled_changed)
        self.ui.workflow_stage_1.currentTextChanged.connect(
            self.on_workflow_stage_changed
        )
        self.ui.workflow_stage_2.currentTextChanged.connect(
            self.on_workflow_stage_changed
        )

    def load(self) -> None:
        """Load known shelves from config."""
        shelves = sorted(get_known_shelves())
        self.ui.shelf_list.clear()
        self.ui.shelf_list.addItems(shelves)

        self.ui.workflow_transitions.setEnabled(self.ui.workflow_enabled.isChecked())

        self.ui.workflow_stage_1.clear()
        self.ui.workflow_stage_1.addItems(shelves)
        try:
            self.ui.workflow_stage_1.setCurrentText(
                config.setting[ShelfConstants.CONFIG_WORKFLOW_STAGE_1_KEY])
        except KeyError:
            self.ui.workflow_stage_1.setCurrentText(ShelfConstants.DEFAULT_INCOMING_SHELF)

        self.ui.workflow_stage_2.clear()
        self.ui.workflow_stage_2.addItems(shelves)
        try:
            self.ui.workflow_stage_2.setCurrentText(
                config.setting[ShelfConstants.CONFIG_WORKFLOW_STAGE_2_KEY])
        except KeyError:
            self.ui.workflow_stage_2.setCurrentText(ShelfConstants.DEFAULT_SHELF)

        try:
            self.ui.workflow_enabled.setChecked(
                config.setting[ShelfConstants.CONFIG_WORKFLOW_ENABLED_KEY])
        except KeyError:
            self.ui.workflow_enabled.setChecked(False)

        # Update preview with current values
        snippet = self.rebuild_rename_snippet()
        self.ui.script_preview.setPlainText(snippet)

    def save(self) -> None:
        """Save shelves list to config."""
        shelves = []
        for i in range(self.ui.shelf_list.count()):
            item_text = self.ui.shelf_list.item(i).text()
            shelves.append(item_text)

        config.setting[ShelfConstants.CONFIG_SHELVES_KEY] = shelves
        config.setting[ShelfConstants.CONFIG_WORKFLOW_STAGE_1_KEY] = (
            self.ui.workflow_stage_1.currentText()
        )
        config.setting[ShelfConstants.CONFIG_WORKFLOW_STAGE_2_KEY] = (
            self.ui.workflow_stage_2.currentText()
        )
        config.setting[ShelfConstants.CONFIG_WORKFLOW_ENABLED_KEY] = (
            self.ui.workflow_enabled.isChecked()
        )

        log.debug("%s: Saved %d shelves to config", PLUGIN_NAME, len(shelves))

    def add_shelf(self) -> None:
        """Add a new shelf."""
        shelf_name, ok = QtWidgets.QInputDialog.getText(
            self, "Add Shelf", "Enter shelf name:"
        )

        if not ok or not shelf_name:
            return

        shelf_name = shelf_name.strip()
        is_valid, message = validate_shelf_name(shelf_name)

        if not is_valid:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", message)
            return

        # Check if already exists
        existing_shelves = self._get_existing_shelves()
        if shelf_name in existing_shelves:
            QtWidgets.QMessageBox.information(
                self, "Already Exists", f"Shelf '{shelf_name}' already exists."
            )
            return

        self.ui.shelf_list.addItem(shelf_name)
        self.ui.workflow_stage_1.addItem(shelf_name)
        self.ui.workflow_stage_2.addItem(shelf_name)
        self.ui.shelf_list.sortItems()

    def remove_shelf(self) -> None:
        """Remove the selected shelf."""
        current_item = self.ui.shelf_list.currentItem()
        if not current_item:
            return

        shelf_name = current_item.text()

        # Warn if it's a workflow shelf
        if shelf_name in [
            self.ui.workflow_stage_1.currentText(),
            self.ui.workflow_stage_2.currentText(),
        ]:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Remove Workflow Shelf?",
                f"'{shelf_name}' is a workflow stage shelf. "
                "Are you sure you want to remove it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        self.ui.shelf_list.takeItem(self.ui.shelf_list.row(current_item))

    def scan_music_directory(self) -> None:
        """Scan Picard's target directory for shelves."""
        try:
            music_dir_str = config.setting["move_files_to"]
        except KeyError:
            QtWidgets.QMessageBox.warning(
                self,
                "No Directory Configured",
                "Please configure 'Move files to' directory in Picard settings first.",
            )
            return

        music_dir = Path(music_dir_str)
        if not music_dir.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Directory Not Found",
                f"The directory '{music_dir}' does not exist.",
            )
            return

        try:
            shelves_found = [entry.name for entry in music_dir.iterdir() if entry.is_dir()]

            if not shelves_found:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Shelves Found",
                    "No subdirectories found in the selected directory.",
                )
                return

            existing_shelves = self._get_existing_shelves()
            # added = 0

            for shelf in shelves_found:
                if shelf not in existing_shelves:
                    is_valid, _ = validate_shelf_name(shelf)
                    if is_valid:
                        self.ui.shelf_list.addItem(shelf)
                        self.ui.workflow_stage_1.addItem(shelf)
                        self.ui.workflow_stage_2.addItem(shelf)
                        # added += 1

            self.ui.shelf_list.sortItems()

            # if added > 0:
            #     QtWidgets.QMessageBox.information(
            #         self,
            #         "Scan Complete",
            #         f"Found {len(shelves_found)} directories.\nAdded {added} new shelf(s).",
            #     )

        except (OSError, PermissionError) as e:
            log.error("%s: Error scanning directory: %s", PLUGIN_NAME, e)
            QtWidgets.QMessageBox.critical(
                self, "Scan Error", f"Error scanning directory: {e}"
            )

    def rebuild_rename_snippet(self) -> str:
        """
        Build the rename snippet

        Returns:
            The complete rename snippet
        """

        return """$set(_shelffolder,$shelf())
$set(_shelffolder,$if($not($eq(%_shelffolder%,)),%_shelffolder%/))

%_shelffolder%
$if2(%albumartist%,%artist%)/%album%/%title%"""

    def on_shelf_list_selection_changed(self) -> None:
        """ Enable / disable remove button based on selection. """
        self.ui.remove_shelf_button.setEnabled(
            self.ui.shelf_list.currentItem() is not None
        )

    def on_workflow_enabled_changed(self) -> None:
        """ Handle workflow enabled state change. """
        is_enabled = self.ui.workflow_enabled.isChecked()
        log.debug("%s: on_workflow_enabled_changed: %s", PLUGIN_NAME, is_enabled)
        self.ui.workflow_transitions.setEnabled(is_enabled)

        # Update preview when workflow is toggled
        snippet = self.rebuild_rename_snippet()
        self.ui.script_preview.setPlainText(snippet)

    def on_workflow_stage_changed(self) -> None:
        """Handle workflow stage change."""
        log.debug(
            "%s: on_workflow_stage_changed: stage_1='%s', stage_2='%s'",
            PLUGIN_NAME,
            self.ui.workflow_stage_1.currentText(),
            self.ui.workflow_stage_2.currentText(),
        )
        snippet = self.rebuild_rename_snippet()
        self.ui.script_preview.setPlainText(snippet)

    def _get_existing_shelves(self) -> Set[str]:
        """
        Get set of currently listed shelves.

        Returns: Set of shelf names
        """
        return {
            self.ui.shelf_list.item(i).text()
            for i in range(self.ui.shelf_list.count())
        }


def set_shelf_in_metadata(
        album: Any, metadata: Dict[str, Any], track: Any, release: Any
) -> None:
    """
    Set shelf in track metadata from album assignment.

    Args:
        album: Album object metadata: Track metadata dictionary
        track: Track object
        release: Release object
    """
    album_id = metadata.get("musicbrainz_albumid")
    if not album_id:
        return

    log.debug("%s: set_shelf_in_metadata '%s'", PLUGIN_NAME, album_id)

    shelf_name = shelf_manager.get_album_shelf(album_id)
    if shelf_name:
        metadata[ShelfConstants.TAG_KEY] = shelf_name
        log.debug("%s: Set shelf '%s' on track", PLUGIN_NAME, shelf_name)


def func_shelf(parser):
    """
    Picard script function: `$shelf()`
    Used in the code snippet created by the plugin and can only be used in conjunction with the plugin.
    Returns the shelf name, optionally applying workflow transition.

    Args:
        parser: Picard script parser
    Returns:
        The shelf name (taking workflow transitions into account, if activated)
    """
    shelf = parser.context.get("shelf", "")
    try:
        is_workflow = config.setting[ShelfConstants.CONFIG_WORKFLOW_ENABLED_KEY]
    except KeyError:
        return shelf

    if not is_workflow:
        return shelf

    try:
        workflow_stage_1 = config.setting[ShelfConstants.CONFIG_WORKFLOW_STAGE_1_KEY]
        workflow_stage_2 = config.setting[ShelfConstants.CONFIG_WORKFLOW_STAGE_2_KEY]
    except KeyError:
        return shelf

    # Apply workflow transition
    if shelf == workflow_stage_1:
        log.debug(
            "%s: Applying workflow transition: '%s' -> '%s'",
            PLUGIN_NAME,
            workflow_stage_1,
            workflow_stage_2,
        )
        return workflow_stage_2

    return shelf


# Registration
log.debug("%s: Registering plugin components", PLUGIN_NAME)

# Register file processor
register_file_post_load_processor(file_post_load_processor)
register_file_post_save_processor(file_post_save_processor)

# Register context menu actions
register_album_action(SetShelfAction())

# Register options page
register_options_page(ShelvesOptionsPage)

# Register metadata processor
register_track_metadata_processor(set_shelf_in_metadata)

# Register script function for use in file naming
register_script_function(func_shelf, "shelf")

log.info("%s v%s loaded successfully", PLUGIN_NAME, __version__)
log.info(
    "%s: Script function $shelf() registered. "
    "Use in file naming: $shelf() or $shelf(Incoming,Standard)",
    PLUGIN_NAME,
)
