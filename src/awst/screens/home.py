"""Home screen: pick an AWS service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self, cast

from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from awst.screens.stacks import StackListScreen

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from awst.app import AwstApp


@dataclass(frozen=True, slots=True)
class ServiceEntry:
    """One row in the service menu."""

    option_id: str
    name: str
    resource: str
    enabled: bool


SERVICES = (
    ServiceEntry(option_id="cloudformation", name="CloudFormation", resource="Stacks", enabled=True),
    ServiceEntry(option_id="s3", name="S3", resource="Buckets", enabled=False),
    ServiceEntry(option_id="sqs", name="SQS", resource="Queues", enabled=False),
)


def _prompt(entry: ServiceEntry) -> str:
    suffix = "" if entry.enabled else "  (soon)"
    return f"{entry.name:<18}{entry.resource}{suffix}"


class HomeScreen(Screen[None]):
    """Service picker; the app's landing screen."""

    TITLE = "awst"

    BINDINGS: ClassVar[list[BindingType]] = [("q", "app.quit", "Quit")]

    DEFAULT_CSS = """
    #prompt { padding: 1 2 0 2; color: $text-muted; }
    #services { margin: 1 2; }
    """

    def compose(self: Self) -> ComposeResult:
        yield Static("Select a service", id="prompt")
        yield OptionList(
            *[Option(_prompt(entry), id=entry.option_id, disabled=not entry.enabled) for entry in SERVICES],
            id="services",
        )
        yield Footer()

    def on_option_list_option_selected(self: Self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "cloudformation":
            app = cast("AwstApp", self.app)
            app.push_screen(StackListScreen(app.cloudformation_gateway))
