# -*- coding: utf-8 -*-

"""
Title Cleaner OST Plugin for MusicBrainz Picard.
Removes soundtrack-related information from album titles using regex.
"""
import os

from PyQt5 import uic
from PyQt5.QtWidgets import QCheckBox

PLUGIN_NAME = "Title Cleaner OST"
PLUGIN_AUTHOR = "nrth3rnlb"
PLUGIN_DESCRIPTION = """
The Plugin “Title Cleaner OST” removes soundtrack-related information (e.g., "OST", "Soundtrack") from album titles.
Supports custom regex patterns, a whitelist and a test field via the plugin settings.
Regular expressions are a powerful tool. They can therefore also cause serious damage.
Use [regex101](https://regex101.com/) or [regex101](https://regex101.com/r/3XS83D/) to test your pattern.
Use at your own risk.
"""
PLUGIN_VERSION = "1.3.3"
PLUGIN_API_VERSIONS = ["2.0"]
PLUGIN_LICENSE = "GPL-2.0"
PLUGIN_LICENSE_URL = "https://www.gnu.org/licenses/gpl-2.0.html"

import re
import unicodedata
import threading

from typing import List, Dict, Any

from PyQt5.QtCore import Qt

from picard import config, log
from picard.config import BoolOption, TextOption, ListOption
from picard.metadata import register_album_metadata_processor
from picard.ui.options import OptionsPage
from picard.ui.options import register_options_page
from picard.ui.options import OptionsCheckError

# No longer used, but kept for config compatibility
# ONLY_SOUNDTRACK = "title_cleaner_ost_only_soundtrack"
OST_WHITELIST = "title_cleaner_ost_whitelist"
OST_REGEX = "title_cleaner_ost_regex"
OST_REGEX_2 = "title_cleaner_ost_regex_2"
ENABLE_REGEX_1 = "title_cleaner_ost_enable_regex_1"
ENABLE_REGEX_2 = "title_cleaner_ost_enable_regex_2"
LIVE_UPDATES = "title_cleaner_ost_live_updates"
APPLY_OPTIONS = "title_cleaner_ost_apply_options"
SCHEMA_VERSION = "title_cleaner_ost_schema_version"


class RemoveReleaseTitleOstIndicatorOptionsPage(OptionsPage):
    """
    Options page for the Title Cleaner OST plugin.
    """
    NAME = "title_cleaner_ost"
    TITLE = "Title Cleaner OST"
    PARENT = "plugins"

    REGEX_DESCRIPTION_MD = """
**Regex explanation (end‑based removal; re.IGNORECASE):**

- Aim: Removes one or more phrases like "Original ... Soundtrack" at the end of the string,
  including any preceding separator.
- Separators (optional, incl. spaces): ` : | ： | ∶ | - | – | — | ( | [ `
- Keywords (as whole words, one or more): `Original|Album|Movie|Motion|Picture|Soundtrack|Score|OST|Music|Edition|Inspired|by|from|the|TV|Series|Video|Game|Film|Show`
- Optional closing bracket: `)` or `]`
- Repeats until the end of the string `(…)+$`
- Example: "Title∶ Music From the Original Soundtrack" » "Title"
- Note: After replacement, multiple spaces are collapsed and leading/trailing whitespace is trimmed.
""".lstrip("\n")

    DEFAULT_REGEX = r'(\s*(?:(?::|：|∶|-|–|—|\(|\[)\s*)?(\b(?:Original|Album|Movie|Motion|Picture|Soundtrack|Score|OST|Music|Edition|Inspired|by|from|the|TV|Series|Video|Game|Film|Show)\b)+(?:\)|\])?\s*)+$'
    DEFAULT_REGEX_2 = r''
    DEFAULT_WHITELIST = ""

    DEFAULT_APPLY_OPTIONS: List[Dict[str, Any]] = [
        {
            "releasetype": "all",
            "text": "All Release Types",
            "tooltip": "The pattern is applied to all albums.",
            "enabled": False,  # use a clear name for the actual enabled state
            "condition": None
        },
        {
            "releasetype": "soundtrack",
            "text": "Soundtracks",
            "tooltip": "The pattern is only applied to albums with release type soundtrack.",
            "enabled": True,
            "condition": {"tag": "releasetype", "value": "soundtrack"}
        }
    ]

    options = [
        TextOption("setting", OST_REGEX, DEFAULT_REGEX),
        TextOption("setting", OST_REGEX_2, DEFAULT_REGEX_2),
        BoolOption("setting", ENABLE_REGEX_1, True),
        BoolOption("setting", ENABLE_REGEX_2, False),
        TextOption("setting", OST_WHITELIST, DEFAULT_WHITELIST),
        BoolOption("setting", LIVE_UPDATES, False),
        ListOption("setting", APPLY_OPTIONS, DEFAULT_APPLY_OPTIONS),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        ui_file = os.path.join(os.path.dirname(__file__), 'title_cleaner_ost_config.ui')
        uic.loadUi(ui_file, self)

        self.regex_pattern_1.setMaximumHeight(100)
        self.regex_pattern_2.setMaximumHeight(100)

        markdown_fmt = getattr(Qt, "MarkdownText", Qt.PlainText)
        self.regex_help.setTextFormat(markdown_fmt)
        self.regex_help.setWordWrap(True)
        self.regex_help.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )

        # Compiled regex cache for preview
        self.compiled_regex = None
        self.compiled_regex_2 = None

        self.regex_help.setVisible(False)
        self.regex_help.setText(self.REGEX_DESCRIPTION_MD)

        # Test field logic
        self.test_input.textChanged.connect(self.update_test_output)
        self.regex_pattern_1.textChanged.connect(self.update_test_output)
        self.regex_pattern_2.textChanged.connect(self.update_test_output)
        self.enable_regex_1.stateChanged.connect(self.update_test_output)
        self.enable_regex_2.stateChanged.connect(self.update_test_output)
        self.whitelist_text.textChanged.connect(self.update_test_output)
        self.enable_live_updates.stateChanged.connect(self.update_test_output)
        self.enable_live_updates.stateChanged.connect(self.update_run_button_state)

        # Reset button for Regex
        self.reset_button.clicked.connect(self.reset_regex_to_default)

        # Regex validation with every change
        self.regex_pattern_1.textChanged.connect(self.on_regex_changed)
        self.regex_pattern_2.textChanged.connect(self.on_regex_changed)

        # Run Update button
        self.run_update.clicked.connect(self.force_update_test_output)

        # Release type checkboxes logic
        self.chk_all_release_types.stateChanged.connect(self.update_release_type_chks)

        self.update_test_output_forced = False

    def update_release_type_chks(self):
        """Updates the state of release type checkboxes."""
        deactivate_selection_option = self.chk_all_release_types.isChecked()
        for i in range(self.gridLayout_2.count()):
            if i > 0:  # Skip the first checkbox (All Release Types)
                self.gridLayout_2.itemAt(i).widget().setDisabled(deactivate_selection_option)

    def force_update_test_output(self):
        """Forces an update of the test output when the 'Run Update' button is clicked."""
        self.update_test_output_forced = True
        self.update_test_output()

    def on_regex_changed(self):
        self.validate_regex_patterns()

    def load(self):
        """Loads the regex, whitelist, and checkbox state from config into the UI."""
        # Clear dynamic checkboxes (keep the first "all" checkbox)
        layout = self.gridLayout_2
        while layout.count() > 1:
            item = layout.takeAt(layout.count() - 1)
            if item:
                w = item.widget()
                if w:
                    w.setParent(None)

        # Read options directly (no migration)
        options = config.setting[APPLY_OPTIONS]

        for option in options:
            log.debug("%s: Processing option for releasetype '%s'", PLUGIN_NAME, option.get("releasetype"))
            if option.get("releasetype") == "all":
                self.chk_all_release_types.setText(option.get("text", self.chk_all_release_types.text()))
                self.chk_all_release_types.setToolTip(option.get("tooltip", self.chk_all_release_types.toolTip()))
                self.chk_all_release_types.setChecked(bool(option.get("enabled", False)))
                self.chk_all_release_types.stateChanged.connect(self.update_release_type_chks)
                continue

            chk = QCheckBox(option.get("releasetype", ""))
            chk.setText(option.get("text", ""))
            chk.setToolTip(option.get("tooltip", ""))
            chk.setChecked(bool(option.get("enabled", False)))
            self.gridLayout_2.addWidget(chk)

        self.update_release_type_chks()

        # Load other settings
        self.regex_pattern_1.setPlainText(config.setting[OST_REGEX])
        self.regex_pattern_2.setPlainText(config.setting[OST_REGEX_2])
        self.enable_regex_1.setChecked(config.setting[ENABLE_REGEX_1])
        self.enable_regex_2.setChecked(config.setting[ENABLE_REGEX_2])
        self.validate_regex_patterns()
        self.whitelist_text.setPlainText(config.setting[OST_WHITELIST])
        self.enable_live_updates.setChecked(config.setting[LIVE_UPDATES])
        self.run_update.setEnabled(not self.enable_live_updates.isChecked())

        self.test_input.setText("")
        self.test_output.setText("")

    def save(self):
        """Saves the configuration settings (no migration)."""
        if not self.validate_regex_patterns():
            raise OptionsCheckError(
                "Invalid Regex Pattern",
                "One or more regex patterns you have entered are invalid. Please correct them before saving."
            )

        original_options = config.setting[APPLY_OPTIONS]
        saved_apply_options = []

        layout = self.gridLayout_2
        layout_index = 1  # itemAt(0) is the "All Release Types" checkbox

        for option in original_options:
            if option.get("releasetype") == "all":
                checked = bool(self.chk_all_release_types.isChecked())
            else:
                item = layout.itemAt(layout_index)
                if item is None or item.widget() is None:
                    checked = bool(option.get("enabled", False))
                else:
                    checked = bool(item.widget().isChecked())
                layout_index += 1

            saved_apply_options.append({
                "releasetype": option.get("releasetype"),
                "text": option.get("text", ""),
                "tooltip": option.get("tooltip", ""),
                "enabled": checked,
                "condition": option.get("condition")
            })

        config.setting[APPLY_OPTIONS] = saved_apply_options  # type: ignore[index]

        # Save other settings
        config.setting[OST_REGEX] = self.regex_pattern_1.toPlainText()  # type: ignore[index]
        config.setting[OST_REGEX_2] = self.regex_pattern_2.toPlainText()  # type: ignore[index]
        config.setting[ENABLE_REGEX_1] = self.enable_regex_1.isChecked()  # type: ignore[index]
        config.setting[ENABLE_REGEX_2] = self.enable_regex_2.isChecked()  # type: ignore[index]
        config.setting[OST_WHITELIST] = self.whitelist_text.toPlainText()  # type: ignore[index]
        config.setting[LIVE_UPDATES] = self.enable_live_updates.isChecked()  # type: ignore[index]

    def reset_regex_to_default(self):
        """Resets the regex to the default pattern."""
        self.regex_pattern_1.setPlainText(self.DEFAULT_REGEX)
        self.regex_pattern_2.setPlainText(self.DEFAULT_REGEX_2)

    def validate_regex_patterns(self) -> bool:
        """Validates both regex patterns, compiles them for caching, and updates the UI accordingly."""
        valid = True
        pattern1 = self.regex_pattern_1.toPlainText()
        try:
            self.compiled_regex = re.compile(pattern1, flags=re.IGNORECASE)
            self.regex_pattern_1.setStyleSheet("")
        except re.error as e:
            log.debug(PLUGIN_NAME + ": Regex 1 validation error: %s", e)
            self.compiled_regex = None
            self.regex_pattern_1.setStyleSheet("background-color: #ffcccc;")
            valid = False

        pattern2 = self.regex_pattern_2.toPlainText()
        if pattern2:  # Only compile if not empty
            try:
                self.compiled_regex_2 = re.compile(pattern2, flags=re.IGNORECASE)
                self.regex_pattern_2.setStyleSheet("")
            except re.error as e:
                log.debug(PLUGIN_NAME + ": Regex 2 validation error: %s", e)
                self.compiled_regex_2 = None
                self.regex_pattern_2.setStyleSheet("background-color: #ffcccc;")
                valid = False
        else:
            self.compiled_regex_2 = None
            self.regex_pattern_2.setStyleSheet("")

        self.regex_error_message.setVisible(not valid)
        if not valid:
            self.regex_error_message.setText("One or more regex patterns are invalid.")
        return valid

    def update_run_button_state(self):
        """Enables or disables the 'Run Update' button based on the live updates checkbox."""
        self.run_update.setEnabled(not self.enable_live_updates.isChecked())

    def update_test_output(self):
        """
        Applies the current regex/whitelist/setting to the test input and shows the result.
        Always shows a preview but indicates when only_soundtrack is enabled.
        """
        if not self.update_test_output_forced and not self.enable_live_updates.isChecked():
            return

        self.update_test_output_forced = False

        album_title = self.test_input.text().strip()
        whitelist = self.whitelist_text.toPlainText()

        # Normalise whitelist titles using Unicode NFC normalization
        whitelist_titles = [
            unicodedata.normalize('NFC', line.strip()).lower()
            for line in whitelist.splitlines() if line.strip()
        ]

        # Normalise album title for comparison
        normalized_title = unicodedata.normalize('NFC', album_title).lower()

        # Whitelist check
        if normalized_title in whitelist_titles:
            self.test_output.setText("Whitelisted – will not be changed!")
            return

        # Always allow preview but use compiled regex if available
        new_title = album_title
        if self.enable_regex_1.isChecked() and self.compiled_regex:
            try:
                new_title = self.compiled_regex.sub('', new_title)
            except Exception as e:
                log.debug(PLUGIN_NAME + ": Preview error on regex 1: %s", e)
                self.test_output.setText(f"Regex 1 error: {e}")
                return

        if self.enable_regex_2.isChecked() and self.compiled_regex_2:
            try:
                new_title = self.compiled_regex_2.sub('', new_title)
            except Exception as e:
                log.debug(PLUGIN_NAME + ": Preview error on regex 2: %s", e)
                self.test_output.setText(f"Regex 2 error: {e}")
                return

        # Normalise whitespace and strip leading/trailing whitespace
        new_title = ' '.join(new_title.split()).strip()
        self.test_output.setText(new_title)


# cache with lock for thread safety
_cache_lock = threading.Lock()
_regex_cache = {
    'compiled_regex': None,
    'compiled_regex_2': None,
    'last_regex': None,
    'last_regex_2': None
}

def title_cleaner_ost(album, metadata, release):
    log.debug("%s: title_cleaner_ost called for album '%s'", PLUGIN_NAME, metadata.get("album", "<no album>"))
    regex = config.setting[OST_REGEX]  # type: ignore[index]
    regex_2 = config.setting[OST_REGEX_2]  # type: ignore[index]

    enable_regex_1 = config.setting[ENABLE_REGEX_1]  # type: ignore[index]
    enable_regex_2 = config.setting[ENABLE_REGEX_2]  # type: ignore[index]
    whitelist = config.setting[OST_WHITELIST]  # type: ignore[index]
    apply_options = config.setting[APPLY_OPTIONS]  # type: ignore[index]

    # Atomic check, compile, and update for regex 1 under lock (only if compilation succeeds)
    with _cache_lock:
        if regex != _regex_cache['last_regex']:
            if regex:
                try:
                    new_compiled = re.compile(regex, flags=re.IGNORECASE)
                    _regex_cache['compiled_regex'] = new_compiled
                    _regex_cache['last_regex'] = regex
                except re.error as e:
                    log.error("%s: Failed to compile regex 1: %s", PLUGIN_NAME, e)
                    # Do not update cache on failure
        compiled_regex = _regex_cache['compiled_regex']

    # Atomic check, compile, and update for regex 2 under lock (only if compilation succeeds)
    with _cache_lock:
        if regex_2 != _regex_cache['last_regex_2']:
            if regex_2:
                try:
                    new_compiled_2 = re.compile(regex_2, flags=re.IGNORECASE)
                    _regex_cache['compiled_regex_2'] = new_compiled_2
                    _regex_cache['last_regex_2'] = regex_2
                except re.error as e:
                    log.error("%s: Failed to compile regex 2: %s", PLUGIN_NAME, e)
                    # Do not update cache on failure
        compiled_regex_2 = _regex_cache['compiled_regex_2']

    # Normalise whitelist titles using Unicode NFC normalization
    whitelist_titles = [
        unicodedata.normalize('NFC', line.strip()).lower()
        for line in whitelist.splitlines() if line.strip()
    ]

    # Example apply_options structure:
    # {
    #     "releasetype": "soundtrack",
    #     "text": "Soundtracks",
    #     "tooltip": "The pattern is only applied to albums with release type soundtrack.",
    #     "enabled": True,
    #     "condition": {"tag": "releasetype", "value": "soundtrack"}
    # }
    # Determine if we should process this album based on release type
    should_process: bool = False

    try:
        for option in apply_options:
            if option.get("enabled"):
                if option.get("releasetype") == "all":
                    log.debug("%s: Applying to all release types", PLUGIN_NAME)
                    should_process = True
                    continue
                elif option.get("condition").get("tag") in metadata and option.get("condition").get("value") in metadata[option.get("condition").get("tag")]:
                    log.debug("%s: Applying to release type '%s'", PLUGIN_NAME, option.get("condition").get("value"))
                    should_process = True
                    continue
    except AttributeError as e:
        log.error("%s: Error processing apply options: %s", PLUGIN_NAME, e)

    if not should_process:
        log.debug("%s: No matching releasetype found", PLUGIN_NAME)
        return

    log.debug("%s: Processing album title with regex '%s'", PLUGIN_NAME, regex)

    if "album" in metadata:
        album_title = metadata["album"].strip()
        normalized_title = unicodedata.normalize('NFC', album_title).lower()

        if normalized_title in whitelist_titles:
            log.debug("%s: Album '%s' is whitelisted, skipping removal", PLUGIN_NAME, album_title)
            return

        if should_process:
            new_title = album_title
            try:
                if enable_regex_1 and compiled_regex:
                    new_title = compiled_regex.sub('', new_title)
                if enable_regex_2 and compiled_regex_2:
                    new_title = compiled_regex_2.sub('', new_title)
                # Normalise whitespace and strip leading/trailing whitespace once after both substitutions
                new_title = ' '.join(new_title.split()).strip()
                metadata["album"] = new_title
                log.debug("%s: Changed album title from '%s' to '%s'", PLUGIN_NAME, album_title, new_title)
            except Exception as e:
                log.error("%s: Regex application error: %s", PLUGIN_NAME, e)


# Register the plugin
register_options_page(RemoveReleaseTitleOstIndicatorOptionsPage)
register_album_metadata_processor(title_cleaner_ost)
