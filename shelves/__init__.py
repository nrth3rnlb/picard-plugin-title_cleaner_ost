# -*- coding: utf-8 -*-

"""
This plugin adds virtual shelf management to MusicBrainz Picard, allowing music files to be organized by top-level folders.
"""

__version__ = "1.0.0"

import re

from picard.config import ListOption, TextOption, BoolOption
from picard.file import register_file_post_load_processor
from picard.metadata import register_track_metadata_processor
from picard.ui.itemviews import BaseAction, register_album_action
from picard.ui.options import OptionsPage, register_options_page

PLUGIN_NAME = "Shelves"
PLUGIN_AUTHOR = "nrth3rnlb"
PLUGIN_DESCRIPTION = """
This plugin adds virtual shelf management to MusicBrainz Picard, allowing music files to be organized by top-level folders.
"""
PLUGIN_VERSION = __version__
PLUGIN_API_VERSIONS = ["2.0", "2.1", "2.2", "2.3"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"

import os
from pathlib import Path

from PyQt5 import QtWidgets
from picard import log, config

from .ui_shelves_config import Ui_ShelvesConfigPage

# Tag-Konstanten

TAG_KEY = "shelf"
BACKUP_TAG_KEY = "shelf_backup"

WORKFLOW_STAGE_1_PLACEHOLDER = """~~~workflow_stage_1~~~"""
WORKFLOW_STAGE_2_PLACEHOLDER = """~~~workflow_stage_2~~~"""

# Standard-Shelves

# Config-Key für bekannte Shelves

CONFIG_SHELVES_KEY = "shelves_known_shelves"
CONFIG_ALBUM_SHELF_KEY = "shelves_album_shelf"
CONFIG_WORKFLOW_STAGE_1_KEY = "shelves_workflow_stage_1"
CONFIG_WORKFLOW_STAGE_2_KEY = "shelves_workflow_stage_2"
CONFIG_WORKFLOW_ENABLED_KEY = "shelves_workflow_enabled"
CONFIG_RENAME_SNIPPET_SKELETON_KEY = "shelves_rename_snippet_skeleton"

DEFAULT_SHELVES = {CONFIG_WORKFLOW_STAGE_1_KEY: "Incoming", CONFIG_WORKFLOW_STAGE_2_KEY: "Standard"}

RENAME_SNIPPET_SKELETON = ("""
$set(_basefolder,$if(%shelf%,%shelf%))
$set(_basefolder,$if($eq(%_basefolder%,""" + WORKFLOW_STAGE_1_PLACEHOLDER + ("""),""" + WORKFLOW_STAGE_2_PLACEHOLDER + """,%_basefolder%))
$set(_basefolder,$if($not($eq(%_basefolder%,)),%_basefolder%/))

%_basefolder%$if2(%albumartist%,%artist%)/%album%/%title%
"""))

shelves_by_album = {}


def get_known_shelves():
    """Gibt die Liste der bekannten Shelves aus der Config zurück"""
    try:
        shelves = config.setting[CONFIG_SHELVES_KEY]
    except KeyError:
        shelves = DEFAULT_SHELVES

    if isinstance(shelves, str):
        shelves = [s.strip() for s in shelves.split(',') if s.strip()]
    return list(set(shelves))  # Duplikate entfernen


def add_known_shelf(shelf_name):
    """Fügt einen Shelf-Namen zur Liste der bekannten Shelves hinzu"""
    if not shelf_name or shelf_name.strip() == "":
        return

    shelves = get_known_shelves()
    if shelf_name not in shelves:
        shelves.append(shelf_name)
        config.setting[CONFIG_SHELVES_KEY] = shelves
        log.debug(f"{PLUGIN_NAME}: Added shelf '{shelf_name}' to known shelves")


def remove_known_shelf(shelf_name):
    """Entfernt einen Shelf-Namen aus der Liste der bekannten Shelves"""
    shelves = get_known_shelves()
    if shelf_name in shelves:
        shelves.remove(shelf_name)
        config.setting[CONFIG_SHELVES_KEY] = shelves
        log.debug(f"{PLUGIN_NAME}: Removed shelf '{shelf_name}' from known shelves")


def is_likely_shelf_name(name):
    """
    Prüft, ob ein Name wahrscheinlich ein Shelf-Name ist oder eher ein Künstler/Album-Name.
    Gibt (is_likely_shelf, reason) zurück.
    """
    if not name:
        return False, "Empty name"

    # Default-Shelves sind immer OK
    if name in DEFAULT_SHELVES.values():
        return True, None

    # Bekannte Shelves sind OK
    if name in get_known_shelves():
        return True, None

    # Heuristiken für verdächtige Namen
    suspicious_reasons = []

    # 1. Enthält ` - ` (typisch für "Artist - Album")
    if " - " in name:
        suspicious_reasons.append("contains ' - ' (typical for 'Artist - Album' format)")

    # 2. Zu lang (Shelf-Namen sind normalerweise kurz)
    if len(name) > 30:
        suspicious_reasons.append(f"too long ({len(name)} chars)")

    # 3. Zu viele Wörter (mehr als 2-3 Wörter ist verdächtig)
    word_count = len(name.split())
    if word_count > 3:
        suspicious_reasons.append(f"too many words ({word_count})")

    # 4. Enthält typische Album-Indikatoren
    album_indicators = ['Vol.', 'Volume', 'Disc', 'CD', 'Part']
    if any(indicator in name for indicator in album_indicators):
        suspicious_reasons.append("contains album indicator (Vol., Disc, etc.)")

    if suspicious_reasons:
        return False, "; ".join(suspicious_reasons)

    return True, None


def get_shelf_from_path(path):
    """
    Extrahiert den Shelf-Namen aus dem Dateipfad.
    Annahme: ~/Music/ShelfName/Artist/Album/file.mp3
    Der Shelf ist das erste Verzeichnis unter dem Music-Basisverzeichnis.
    """
    try:
        log.debug(f"{PLUGIN_NAME}: Extracting shelf from path: {path}")

        # Suche nach /Music/ und nimm das nächste Verzeichnis
        match = re.search(r'/Music/([^/]+)', path)
        if match:
            shelf_name = match.group(1)
            log.debug(f"{PLUGIN_NAME}: Found potential shelf: {shelf_name}")

            # Prüfe, ob das ein plausibler Shelf-Name ist
            is_likely, reason = is_likely_shelf_name(shelf_name)
            if not is_likely:
                log.warning(
                    f"{PLUGIN_NAME}: '{shelf_name}' looks like an artist/album name, not a shelf "
                    f"({reason}). Using 'Standard' instead. "
                    f"If this is actually a shelf, add it in plugin settings."
                )
                return "Standard"

            log.debug(f"{PLUGIN_NAME}: Confirmed shelf: {shelf_name}")
            return shelf_name

        # Fallback: nimm das vorletzte Verzeichnis vor der Datei
        parts = [p for p in path.split(os.sep) if p]
        if len(parts) >= 3:
            # Annahme: [... , ShelfName, Artist, Album, file]
            # Wir nehmen das 3. von hinten (ohne Datei)
            shelf_name = parts[-3] if len(parts) >= 3 else "Standard"
            log.debug(f"{PLUGIN_NAME}: Fallback potential shelf: {shelf_name}")

            # Auch hier Plausibilitätsprüfung
            is_likely, reason = is_likely_shelf_name(shelf_name)
            if not is_likely:
                log.warning(
                    f"{PLUGIN_NAME}: Fallback '{shelf_name}' looks suspicious ({reason}). "
                    f"Using 'Standard' instead."
                )
                return "Standard"

            return shelf_name

        log.debug(f"{PLUGIN_NAME}: No shelf found, using Standard")
        return "Standard"

    except Exception as e:
        log.error(f"{PLUGIN_NAME}: Error extracting shelf from path '{path}': {e}")
        return "Standard"


def set_album_shelf(album_id, shelf_name):
    """Sichert den Namen des Album Shelf"""
    log.debug(f"{PLUGIN_NAME}: set_album_shelf '{shelf_name}' for {album_id}")
    if not shelf_name or shelf_name.strip() == "":
        return

    log.debug(f"{PLUGIN_NAME}: Set shelf '{shelf_name}' as album shelf for {album_id}")
    shelves_by_album[album_id] = shelf_name


def file_post_load_processor(file):
    """
    Wird aufgerufen, wenn Picard eine Datei gescannt hat.
    """
    try:
        log.debug(f"{PLUGIN_NAME}: Processing file: {file.filename}")

        for keys in file.metadata:
            log.debug(f"{PLUGIN_NAME}: File metadata: [{keys}]: {file.metadata[keys]}")

        if TAG_KEY not in file.metadata or not file.metadata[TAG_KEY]:
            shelf = get_shelf_from_path(file.filename)
            file.metadata[TAG_KEY] = shelf
            add_known_shelf(shelf)
            log.debug(f"{PLUGIN_NAME}: Set shelf '{shelf}' for: {file.filename}")
        else:
            existing_shelf = file.metadata[TAG_KEY]
            log.debug(f"{PLUGIN_NAME}: Shelf already set to '{existing_shelf}'")
            add_known_shelf(existing_shelf)

        album_id = file.metadata["musicbrainz_albumid"]
        set_album_shelf(album_id, file.metadata[TAG_KEY])


    except Exception as e:
        log.error(f"{PLUGIN_NAME}: Error in file processor: {e}")
        import traceback
        log.error(f"{PLUGIN_NAME}: Traceback: {traceback.format_exc()}")


def validate_shelf_name(name):
    """
    Validiert einen Shelf-Namen für die Verwendung als Verzeichnisname.
    Gibt (is_valid, warning_message) zurück.
    """
    if not name or name.strip() == "":
        return False, "Shelf name cannot be empty"

    # Zeichen, die in Pfaden problematisch sind
    invalid_chars = r'<>:"|?*'
    found_invalid = [c for c in invalid_chars if c in name]

    if found_invalid:
        return False, f"Contains invalid characters: {', '.join(found_invalid)}"

    if name.startswith('.') or name.endswith('.'):
        return True, "Warning: Names starting or ending with '.' may cause issues on some systems"

    if name in ['.', '..']:
        return False, "Cannot use '.' or '..' as shelf name"

    return True, None


class SetShelfAction(BaseAction):
    """Kontextmenü-Aktion: Shelf-Namen setzen"""
    NAME = "Set shelf name…"

    def callback(self, objs):
        log.debug(f"{PLUGIN_NAME}: SetShelfAction called with {len(objs)} objects")

        # Bekannte Shelves holen
        known_shelves = get_known_shelves()

        # Dialog erstellen
        dialog = QtWidgets.QInputDialog(self.tagger.window)
        dialog.setWindowTitle("Set Shelf Name")
        dialog.setLabelText("Select or enter shelf name:")
        dialog.setComboBoxItems(known_shelves)
        dialog.setComboBoxEditable(True)
        dialog.setOption(QtWidgets.QInputDialog.UseListViewForComboBoxItems, True)

        # Validierungs-Label hinzufügen
        layout = dialog.layout()
        validation_label = QtWidgets.QLabel("")
        validation_label.setStyleSheet("QLabel { color: orange; }")
        layout.addWidget(validation_label)

        # Validierung bei Texteingabe
        def on_text_changed(text):
            is_valid, message = validate_shelf_name(text)
            if message:
                validation_label.setText(message)
                validation_label.setStyleSheet(
                    "QLabel { color: red; }" if not is_valid else "QLabel { color: orange; }"
                )
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
                    f"Cannot use this shelf name: {message}"
                )
                return

            # Shelf-Namen auf alle ausgewählten Objekte anwenden
            for obj in objs:
                self._set_shelf_recursive(obj, shelf_name)

            add_known_shelf(shelf_name)
            log.info(f"{PLUGIN_NAME}: Set shelf to '{shelf_name}' for {len(objs)} object(s)")

    @staticmethod
    def _set_shelf_recursive(obj, shelf_name):
        """Setzt den Shelf-Namen rekursiv auf alle Files in einem Objekt"""
        if hasattr(obj, 'metadata'):
            # Backup des alten Werts
            old_value = obj.metadata.get(TAG_KEY, "")
            if old_value:
                obj.metadata[BACKUP_TAG_KEY] = old_value

            # Neuen Wert setzen
            obj.metadata[TAG_KEY] = shelf_name
            log.debug(f"{PLUGIN_NAME}: Set shelf '{shelf_name}' on {type(obj).__name__}")

        # Rekursiv auf Kinder anwenden
        if hasattr(obj, 'iterfiles'):
            for file in obj.iterfiles():
                old_value = file.metadata.get(TAG_KEY, "")
                if old_value:
                    file.metadata[BACKUP_TAG_KEY] = old_value
                file.metadata[TAG_KEY] = shelf_name


class UndoSetShelfAction(BaseAction):
    """Kontextmenü-Aktion: Shelf-Namen zurücksetzen"""
    NAME = "Undo set shelf name"

    def callback(self, objs):
        log.debug(f"{PLUGIN_NAME}: UndoSetShelfAction called with {len(objs)} objects")

        count = 0
        for obj in objs:
            count += self._undo_shelf_recursive(obj)

        if count > 0:
            log.info(f"{PLUGIN_NAME}: Restored shelf for {count} file(s)")
        else:
            QtWidgets.QMessageBox.information(
                self.tagger.window,
                "No Backup Found",
                "No shelf backup found for the selected items."
            )

    @staticmethod
    def _undo_shelf_recursive(obj):
        """Stellt den Shelf-Namen rekursiv für alle Files wieder her"""
        count = 0

        if hasattr(obj, 'metadata'):
            backup_value = obj.metadata.get(BACKUP_TAG_KEY, None)
            if backup_value:
                obj.metadata[TAG_KEY] = backup_value
                del obj.metadata[BACKUP_TAG_KEY]
                count += 1
                log.debug(f"{PLUGIN_NAME}: Restored shelf to '{backup_value}' on {type(obj).__name__}")

        if hasattr(obj, 'iterfiles'):
            for file in obj.iterfiles():
                backup_value = file.metadata.get(BACKUP_TAG_KEY, None)
                if backup_value:
                    file.metadata[TAG_KEY] = backup_value
                    del file.metadata[BACKUP_TAG_KEY]
                    count += 1

        return count


class ShelvesOptionsPage(OptionsPage):
    """Options-Seite für das Shelves-Plugin"""
    NAME = "shelves"
    TITLE = "Shelves"
    PARENT = "plugins"

    options = [
        ListOption("setting", CONFIG_SHELVES_KEY, DEFAULT_SHELVES.values()),
        TextOption("setting", CONFIG_ALBUM_SHELF_KEY, ""),
        TextOption("setting", CONFIG_WORKFLOW_STAGE_1_KEY, DEFAULT_SHELVES[CONFIG_WORKFLOW_STAGE_1_KEY]),
        TextOption("setting", CONFIG_WORKFLOW_STAGE_2_KEY, DEFAULT_SHELVES[CONFIG_WORKFLOW_STAGE_2_KEY]),
        BoolOption("setting", CONFIG_WORKFLOW_ENABLED_KEY, True),
        TextOption("setting", CONFIG_RENAME_SNIPPET_SKELETON_KEY, RENAME_SNIPPET_SKELETON),
    ]

    def __init__(self, parent=None):
        super(ShelvesOptionsPage, self).__init__(parent)
        self.ui = Ui_ShelvesConfigPage()
        self.ui.setupUi(self)

        # Button-Verbindungen
        self.ui.add_shelf_button.clicked.connect(self.add_shelf)
        self.ui.remove_shelf_button.clicked.connect(self.remove_shelf)
        self.ui.scan_shelves_button.clicked.connect(self.scan_music_directory)
        self.ui.shelf_list.itemSelectionChanged.connect(self.on_shelf_list_selection_changed)
        self.ui.workflow_enabled.stateChanged.connect(self.on_workflow_enabled_changed)
        self.ui.workflow_stage_1.currentTextChanged.connect(self.on_workflow_stage_1_changed)
        self.ui.workflow_stage_2.currentTextChanged.connect(self.on_workflow_stage_2_changed)

    def load(self):
        """Lädt die bekannten Shelves"""
        shelves = sorted(get_known_shelves())
        self.ui.shelf_list.clear()
        self.ui.shelf_list.addItems(shelves)

        self.ui.workflow_stage_1.clear()
        self.ui.workflow_stage_1.addItems(shelves)
        self.ui.workflow_stage_1.setCurrentText(config.setting[CONFIG_WORKFLOW_STAGE_1_KEY])

        self.ui.workflow_stage_2.clear()
        self.ui.workflow_stage_2.addItems(shelves)
        self.ui.workflow_stage_2.setCurrentText(config.setting[CONFIG_WORKFLOW_STAGE_2_KEY])

        # Preview mit aktuellen Werten aktualisieren
        snippet = self.rebuild_rename_snippet()
        self.ui.script_preview.setPlainText(snippet)

    def save(self):
        """Speichert die Shelves-Liste"""
        shelves = []
        for i in range(self.ui.shelf_list.count()):
            shelves.append(self.ui.shelf_list.item(i).text())
            if self.ui.shelf_list.item(i).text() == self.ui.workflow_stage_1.currentText():
                config.setting[CONFIG_WORKFLOW_STAGE_1_KEY] = self.ui.workflow_stage_1.currentText()
            if self.ui.shelf_list.item(i).text() == self.ui.workflow_stage_2.currentText():
                config.setting[CONFIG_WORKFLOW_STAGE_2_KEY] = self.ui.workflow_stage_2.currentText()

        config.setting[CONFIG_SHELVES_KEY] = shelves
        log.debug(f"{PLUGIN_NAME}: Saved {len(shelves)} shelves to config")

    def add_shelf(self):
        """Fügt ein neues Shelf hinzu"""
        shelf_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Shelf",
            "Enter shelf name:"
        )

        if ok and shelf_name:
            shelf_name = shelf_name.strip()
            is_valid, message = validate_shelf_name(shelf_name)

            if not is_valid:
                QtWidgets.QMessageBox.warning(self, "Invalid Name", message)
                return

            # Prüfen ob bereits vorhanden
            for i in range(self.ui.shelf_list.count()):
                if self.ui.shelf_list.item(i).text() == shelf_name:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Already Exists",
                        f"Shelf '{shelf_name}' already exists."
                    )
                    return

            self.ui.shelf_list.addItem(shelf_name)
            self.ui.workflow_stage_1.addItem(shelf_name)
            self.ui.workflow_stage_2.addItem(shelf_name)
            self.ui.shelf_list.sortItems()

    def remove_shelf(self):
        """Entfernt das ausgewählte Shelf"""
        current_item = self.ui.shelf_list.currentItem()
        if current_item:
            shelf_name = current_item.text()

            # Warnung bei Standard-Shelves
            if shelf_name == config.setting[CONFIG_WORKFLOW_STAGE_1_KEY] or shelf_name == config.setting[
                CONFIG_WORKFLOW_STAGE_2_KEY]:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Remove Workflow Shelf?",
                    f"'{shelf_name}' is a workflow stage shelf. Are you sure you want to remove it?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.No:
                    return

            self.ui.shelf_list.takeItem(self.ui.shelf_list.row(current_item))

    def scan_music_directory(self):
        """Scannt Picards Zielverzeichnis"""
        music_dir = Path(config.setting["move_files_to"])

        if not music_dir:
            return

        try:
            # Scanne erste Ebene
            shelves_found = []
            for entry in os.listdir(music_dir):
                full_path = os.path.join(music_dir, entry)
                if os.path.isdir(full_path):
                    shelves_found.append(entry)

            if not shelves_found:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Shelves Found",
                    "No subdirectories found in the selected directory."
                )
                return

            # Füge neue Shelves hinzu
            added = 0
            existing_shelves = set()
            for i in range(self.ui.shelf_list.count()):
                existing_shelves.add(self.ui.shelf_list.item(i).text())

            for shelf in shelves_found:
                if shelf not in existing_shelves:
                    self.ui.shelf_list.addItem(shelf)
                    self.ui.workflow_stage_1.addItem(shelf)
                    self.ui.workflow_stage_2.addItem(shelf)
                    added += 1

            self.ui.shelf_list.sortItems()

            # QtWidgets.QMessageBox.information(
            #     self,
            #     "Scan Complete",
            #     f"Found {len(shelves_found)} shelves.\nAdded {added} new shelf(s)."
            # )

        except Exception as e:
            log.error(f"{PLUGIN_NAME}: Error scanning directory: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Scan Error",
                f"Error scanning directory: {str(e)}"
            )

    def rebuild_rename_snippet(self):
        """Erstellt das Rename-Snippet mit beiden aktuellen Workflow-Stage-Werten"""
        snippet = config.setting[CONFIG_RENAME_SNIPPET_SKELETON_KEY]

        # Beide Platzhalter nacheinander ersetzen
        stage_1_value = self.ui.workflow_stage_1.currentText()
        stage_2_value = self.ui.workflow_stage_2.currentText()

        log.debug(f"{PLUGIN_NAME}: rebuild_rename_snippet: stage_1: '{stage_1_value}', stage_2: '{stage_2_value}'")

        # Erst Platzhalter 1 ersetzen
        snippet = snippet.replace(WORKFLOW_STAGE_1_PLACEHOLDER, stage_1_value)
        # Dann Platzhalter 2 ersetzen
        snippet = snippet.replace(WORKFLOW_STAGE_2_PLACEHOLDER, stage_2_value)

        return snippet

    def on_shelf_list_selection_changed(self):
        """Aktiviert/Deaktiviert den Remove-Button basierend auf der Auswahl"""
        self.ui.remove_shelf_button.setEnabled(
            self.ui.shelf_list.currentItem() is not None
        )

    def on_workflow_enabled_changed(self):
        log.debug(f"{PLUGIN_NAME}: on_workflow_enabled_changed '{self.ui.workflow_enabled.checkState()}'")
        self.ui.workflow_transitions.setEnabled(
            self.ui.workflow_enabled.checkState()
        )

    def on_workflow_stage_1_changed(self):
        log.debug(f"{PLUGIN_NAME}: on_workflow_stage_1_changed '{self.ui.workflow_stage_1.currentText()}'")
        snippet = self.rebuild_rename_snippet()
        log.debug(f"{PLUGIN_NAME}: on_workflow_stage_1_changed script_preview: '{snippet}'")
        self.ui.script_preview.setPlainText(snippet)

    def on_workflow_stage_2_changed(self):
        log.debug(f"{PLUGIN_NAME}: on_workflow_stage_2_changed '{self.ui.workflow_stage_2.currentText()}'")
        snippet = self.rebuild_rename_snippet()
        log.debug(f"{PLUGIN_NAME}: on_workflow_stage_2_changed script_preview: '{snippet}'")
        self.ui.script_preview.setPlainText(snippet)


def set_shelf_in_metadata(album, metadata, track, release):
    musicbrainz_albumid = metadata["musicbrainz_albumid"]

    log.debug(f"{PLUGIN_NAME}: set_shelf_in_metadata '{musicbrainz_albumid}'")

    shelf_name = shelves_by_album[musicbrainz_albumid]
    metadata[TAG_KEY] = shelf_name
    log.debug(f"{PLUGIN_NAME}: Set shelf '{shelf_name}' on track")


# Registrierung

log.debug(f"{PLUGIN_NAME}: Registering plugin components")
register_file_post_load_processor(file_post_load_processor)
register_album_action(SetShelfAction())
# register_track_action(SetShelfAction())
register_album_action(UndoSetShelfAction())
# register_track_action(UndoSetShelfAction())
register_options_page(ShelvesOptionsPage)
register_track_metadata_processor(set_shelf_in_metadata)

log.info(f"{PLUGIN_NAME} v{__version__} loaded successfully")
