from _typeshed import Incomplete

from PyQt5 import QtWidgets


class OptionsCheckError(Exception):
    title: Incomplete
    info: Incomplete

    def __init__(self, title, info) -> None: ...


class OptionsPage(QtWidgets.QWidget):
    PARENT: Incomplete
    SORT_ORDER: int
    ACTIVE: bool
    HELP_URL: Incomplete
    STYLESHEET_ERROR: str
    STYLESHEET: str
    deleted: bool

    def __init__(self, *args, **kwargs) -> None: ...

    dialog: Incomplete

    def set_dialog(self, dialog) -> None: ...

    def check(self) -> None: ...

    def load(self) -> None: ...

    def save(self) -> None: ...

    def restore_defaults(self) -> None: ...

    def display_error(self, error) -> None: ...

    def init_regex_checker(self, regex_edit, regex_error) -> None: ...


def register_options_page(page_class) -> None: ...
