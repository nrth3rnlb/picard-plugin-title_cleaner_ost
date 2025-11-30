from _typeshed import Incomplete

from PyQt5 import QtWidgets
from picard.util import restore_method as restore_method

FONT_FAMILY_MONOSPACE: str


class PreserveGeometry:
    defaultsize: Incomplete

    def __init__(self) -> None: ...

    def opt_name(self): ...

    def splitters_name(self): ...

    @restore_method
    def restore_geometry(self) -> None: ...

    def save_geometry(self) -> None: ...


class SingletonDialog:
    @classmethod
    def get_instance(cls, *args, **kwargs): ...

    @classmethod
    def show_instance(cls, *args, **kwargs): ...


class PicardDialog(QtWidgets.QDialog, PreserveGeometry):
    help_url: Incomplete
    flags: Incomplete
    ready_for_display: Incomplete

    def __init__(self, parent=None) -> None: ...

    def keyPressEvent(self, event) -> None: ...

    def showEvent(self, event): ...

    def show_help(self) -> None: ...


class HashableTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    id: Incomplete

    def __init__(self, *args, **kwargs) -> None: ...

    def __eq__(self, other): ...

    def __hash__(self): ...


class HashableListWidgetItem(QtWidgets.QListWidgetItem):
    id: Incomplete

    def __init__(self, *args, **kwargs) -> None: ...

    def __eq__(self, other): ...

    def __hash__(self): ...
