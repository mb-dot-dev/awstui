"""Region selection screen, opened from anywhere with ctrl+g."""

from typing import TYPE_CHECKING, ClassVar, Self

from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class RegionSelectScreen(Screen[str | None]):
    """Pick the AWS region the whole app will use; dismisses with its name, or None to cancel."""

    TITLE = "awst"

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "Back")]

    DEFAULT_CSS = """
    #prompt { padding: 1 2 0 2; color: $text-muted; }
    #regions { margin: 1 2; }
    """

    def __init__(self: Self, region_names: list[str], current: str | None) -> None:
        super().__init__()
        self._region_names = region_names
        self._current = current

    def compose(self: Self) -> ComposeResult:
        yield Static("Select an AWS region", id="prompt")
        yield OptionList(*[Option(name, id=name) for name in self._region_names], id="regions")
        yield Footer()

    def on_mount(self: Self) -> None:
        if self._current in self._region_names:
            self.query_one("#regions", OptionList).highlighted = self._region_names.index(self._current)

    def on_option_list_option_selected(self: Self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self: Self) -> None:
        self.dismiss(None)
