from _typeshed import Incomplete

from PyQt5 import QtCore


class Memovar:
    dirty: bool
    value: Incomplete

    def __init__(self) -> None: ...


class ConfigUpgradeError(Exception): ...


class ConfigSection(QtCore.QObject):
    def __init__(self, config, name) -> None: ...

    def key(self, name): ...

    def __getitem__(self, name): ...

    def __setitem__(self, name, value) -> None: ...

    def __contains__(self, name) -> bool: ...

    def as_dict(self): ...

    def remove(self, name) -> None: ...

    def raw_value(self, name, qtype=None): ...

    def value(self, name, option_type, default=None): ...


class SettingConfigSection(ConfigSection):
    PROFILES_KEY: str
    SETTINGS_KEY: str

    @classmethod
    def init_profile_options(cls) -> None: ...

    profiles_override: Incomplete
    settings_override: Incomplete

    def __init__(self, config, name) -> None: ...

    def __getitem__(self, name): ...

    def __setitem__(self, name, value) -> None: ...

    def set_profiles_override(self, new_profiles=None) -> None: ...

    def set_settings_override(self, new_settings=None) -> None: ...


class Config(QtCore.QSettings):
    def __init__(self) -> None: ...

    def event(self, event): ...

    def sync(self) -> None: ...

    def get_lockfile_name(self): ...

    @classmethod
    def from_app(cls, parent): ...

    @classmethod
    def from_file(cls, parent, filename): ...

    def register_upgrade_hook(self, func, *args) -> None: ...

    def run_upgrade_hooks(self, outputfunc=None) -> None: ...

    def save_user_backup(self, backup_path): ...


class Option(QtCore.QObject):
    registry: Incomplete
    qtype: Incomplete
    section: Incomplete
    name: Incomplete
    default: Incomplete

    def __init__(self, section, name, default) -> None: ...

    @classmethod
    def get(cls, section, name): ...

    @classmethod
    def add_if_missing(cls, section, name, default) -> None: ...

    @classmethod
    def exists(cls, section, name): ...

    def convert(self, value): ...


class TextOption(Option):
    convert = str
    qtype: str


class BoolOption(Option):
    convert = bool
    qtype = bool


class IntOption(Option):
    convert = int


class FloatOption(Option):
    convert = float


class ListOption(Option):
    convert = list
    qtype: str


config: Incomplete
setting: Incomplete
persist: Incomplete
profiles: Incomplete


def setup_config(app, filename=None) -> None: ...


def get_config(): ...


def load_new_config(filename=None): ...
