PLUGIN_NAME = "Shelves"
PLUGIN_AUTHOR = "nrth3rnlb"
PLUGIN_DESCRIPTION = "Manages virtual shelves for organizing music files in Picard."
PLUGIN_VERSION = "1.2"
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2", "2.3"]

from picard import config, log
from picard.metadata import register_track_metadata_processor
from picard.ui.itemviews import BaseAction, register_album_action, register_track_action
from PyQt5 import QtWidgets
import os
import re

TAG_KEY = "shelves_shelf"
UNDO_TAG_KEY = "shelves_shelf_backup"
DEFAULT_SHELVES = ["Standard", "Incoming"]

def get_library_path():
    return config.setting.get("move_files_to", "").rstrip("/")

def get_shelf_from_path(path):
    library_path = get_library_path()
    if not library_path:
        return "Standard"
    escaped = re.escape(library_path)
    match = re.search(rf"{escaped}/([^/]+)/", path)
    return match.group(1) if match else "Standard"

def update_config_shelves(shelf_name):
    shelves = config.setting.setdefault("shelves_list", [])
    if shelf_name not in shelves:
        shelves.append(shelf_name)
        config.setting["shelves_list"] = shelves

def shelf_metadata_processor(track_metadata):
    if TAG_KEY not in track_metadata or not track_metadata[TAG_KEY]:
        shelf = get_shelf_from_path(track_metadata["~filename"])
        track_metadata[TAG_KEY] = shelf
        update_config_shelves(shelf)

register_track_metadata_processor(shelf_metadata_processor)

class SetShelfAction(BaseAction):
    NAME = "Change shelf…"

    def callback(self, objs):
        shelves = config.setting.get("shelves_list", [])
        dialog = QtWidgets.QInputDialog()
        dialog.setComboBoxItems(shelves)
        dialog.setLabelText("Select or enter shelf name:")
        dialog.setWindowTitle("Set Shelf")
        dialog.setTextValue("")
        if dialog.exec_():
            shelf_name = dialog.textValue()
            preview_script = generate_rename_script_fragment(shelf_name)
            QtWidgets.QMessageBox.information(None, "Rename Script Preview", f"Generated script fragment:\n\n{preview_script}")
            for obj in objs:
                metadata = obj.metadata
                metadata[UNDO_TAG_KEY] = metadata.get(TAG_KEY, "")
                metadata[TAG_KEY] = shelf_name

class UndoShelfAction(BaseAction):
    NAME = "Restore previous shelf"

    def callback(self, objs):
        for obj in objs:
            metadata = obj.metadata
            if UNDO_TAG_KEY in metadata:
                metadata[TAG_KEY] = metadata[UNDO_TAG_KEY]
                del metadata[UNDO_TAG_KEY]

    def is_enabled(self, objs):
        return any(UNDO_TAG_KEY in obj.metadata for obj in objs)

def generate_rename_script_fragment(shelf_name=None):
    library_path = get_library_path()
    escaped_path = re.escape(library_path)
    fragment = (
        f"$set(_basefolder,\n"
        f"  $if($or($not(%shelves_shelf%),$eq(%shelves_shelf%,)),\n"
        f"    $replace($rreplace($dirname,\".*/{escaped_path}/([^/]+).*\",\"$1\"),\"Incoming\",\"Standard\"),\n"
        f"    %shelves_shelf%\n"
        f"  )\n"
        f")\n"
        f"$join({library_path},%_basefolder%/<Artist>/<Album>/<Title>)"
    )
    return fragment

register_album_action(SetShelfAction())
register_track_action(SetShelfAction())
register_album_action(UndoShelfAction())
register_track_action(UndoShelfAction())
