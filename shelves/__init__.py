# -*- coding: utf-8 -*-

"""
Shelves Plugin for MusicBrainz Picard.

This plugin adds virtual shelf management to MusicBrainz Picard,
allowing music files to be organised by top-level folders.
"""

from __future__ import annotations

from typing import Any, Dict

from picard import log
from picard.file import register_file_post_load_processor, register_file_post_save_processor
from picard.metadata import register_track_metadata_processor
from picard.script import register_script_function
from picard.ui.itemviews import register_album_action
from picard.ui.options import register_options_page

from .actions import SetShelfAction as _SetShelfActionBase
from .manager import ShelfManager
from .options import ShelvesOptionsPage as _ShelvesOptionsPageBase
from .processors import (
    file_post_load_processor,
    file_post_save_processor,
    set_shelf_in_metadata,
)
from .script_functions import func_shelf as _func_shelf_base


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


# Global shelf manager instance
shelf_manager = ShelfManager()


# Wrapper classes to ensure proper plugin registration
class ShelvesOptionsPage(_ShelvesOptionsPageBase):
    """Wrapper class for the ShelvesOptionsPage to ensure proper plugin registration."""
    pass


class SetShelfAction(_SetShelfActionBase):
    """Wrapper class for SetShelfAction to ensure proper plugin registration."""
    pass


# Wrapper for script function
def func_shelf(parser: Any) -> str:
    """Wrapper for func_shelf to ensure proper plugin registration."""
    return _func_shelf_base(parser)


# Wrapper functions that pass shelf_manager to processors
def _file_post_load_processor_wrapper(file: Any) -> None:
    """Wrapper for file_post_load_processor."""
    file_post_load_processor(file, shelf_manager)


def _file_post_save_processor_wrapper(file: Any) -> None:
    """Wrapper for file_post_save_processor."""
    file_post_save_processor(file, shelf_manager)


def _set_shelf_in_metadata_wrapper(
    album: Any, metadata: Dict[str, Any], track: Any, release: Any
) -> None:
    """Wrapper for set_shelf_in_metadata."""
    set_shelf_in_metadata(album, metadata, track, release, shelf_manager)  # noqa: F841


# Registration
log.debug("%s: Registering plugin components", PLUGIN_NAME)

# Register file processors
register_file_post_load_processor(_file_post_load_processor_wrapper)
register_file_post_save_processor(_file_post_save_processor_wrapper)

# Register context menu actions
register_album_action(SetShelfAction())

# Register options page
register_options_page(ShelvesOptionsPage)

# Register metadata processor
register_track_metadata_processor(_set_shelf_in_metadata_wrapper)

# Register a script function for use in file naming
register_script_function(func_shelf, "shelf")

log.info(
    "%s: Script function $shelf() registered. "
    "Use in file naming: $shelf()",
    PLUGIN_NAME,
)
log.info("%s v%s loaded successfully", PLUGIN_NAME, __version__)

