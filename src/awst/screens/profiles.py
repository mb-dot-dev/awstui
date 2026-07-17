"""Profile selection screen, shown at startup when no AWS profile is active."""

from typing import TYPE_CHECKING, ClassVar, Self

from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class ProfileSelectScreen(Screen[str]):
    """Pick the AWS profile the whole app will use; dismisses with its name."""

    TITLE = "awst"

    BINDINGS: ClassVar[list[BindingType]] = [("q", "app.quit", "Quit")]

    DEFAULT_CSS = """
    #prompt { padding: 1 2 0 2; color: $text-muted; }
    #profiles { margin: 1 2; }
    """

    def __init__(self: Self, profile_names: list[str]) -> None:
        super().__init__()
        self._profile_names = profile_names

    def compose(self: Self) -> ComposeResult:
        yield Static("Select an AWS profile", id="prompt")
        yield OptionList(*[Option(name, id=name) for name in self._profile_names], id="profiles")
        yield Footer()

    def on_option_list_option_selected(self: Self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(event.option.id)
