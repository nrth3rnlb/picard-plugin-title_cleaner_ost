import logging
from _typeshed import Incomplete
from collections.abc import Generator
from typing import NamedTuple

from PyQt5 import QtCore

picard_module_path: Incomplete


def set_level(level) -> None: ...


def get_effective_level(): ...


class _feat(NamedTuple):
    name: Incomplete
    prefix: Incomplete
    color_key: Incomplete


levels_features: Incomplete


class TailLogTuple(NamedTuple):
    pos: Incomplete
    message: Incomplete
    level: Incomplete


class TailLogHandler(logging.Handler):
    log_queue: Incomplete
    tail_logger: Incomplete
    log_queue_lock: Incomplete
    pos: int

    def __init__(self, log_queue, tail_logger, log_queue_lock) -> None: ...

    def emit(self, record) -> None: ...


class TailLogger(QtCore.QObject):
    updated: Incomplete
    log_handler: Incomplete

    def __init__(self, maxlen) -> None: ...

    def contents(self, prev: int = -1) -> Generator[Incomplete, Incomplete]: ...

    def clear(self) -> None: ...


main_logger: Incomplete


def name_filter(record): ...


main_tail: Incomplete
main_fmt: str
main_time_fmt: str
main_inapp_fmt = main_fmt
main_inapp_time_fmt = main_time_fmt
main_handler: Incomplete
main_formatter: Incomplete
main_console_handler: Incomplete
main_console_formatter: Incomplete
debug: Incomplete
info: Incomplete
warning: Incomplete
error: Incomplete
exception: Incomplete
log: Incomplete
history_logger: Incomplete
history_tail: Incomplete
history_handler: Incomplete
history_formatter: Incomplete


def history_info(message, *args) -> None: ...
