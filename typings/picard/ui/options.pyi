from typing import Any, Optional, Callable


class OptionsCheckError(Exception):
    ...


class OptionsPage:
    NAME: str
    TITLE: str
    PARENT: Optional[str]

    def __init__(self, parent: Any = ...) -> None: ...

    def load(self) -> None: ...

    def save(self) -> None: ...


def register_options_page(page: OptionsPage) -> None: ...


# minimal re-exports commonly used by the plugin
def register_album_metadata_processor(func: Callable[..., Any]) -> None: ...
