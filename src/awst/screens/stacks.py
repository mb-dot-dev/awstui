"""CloudFormation stack list screen."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Protocol, Self

from rich.text import Text
from textual import work
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static
from textual.worker import WorkerState

from awst.screens.formatting import relative_age, status_style

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType
    from textual.worker import Worker

    from awst.aws.models import StackSummary

COLUMNS = ("Name", "Status", "Created", "Updated")


class StackLister(Protocol):
    """The slice of the CloudFormation gateway this screen needs."""

    def list_stacks(self: Self) -> list[StackSummary]: ...


class StackListScreen(Screen[None]):
    """Read-only list of the account's CloudFormation stacks."""

    TITLE = "CloudFormation stacks"

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "back", "Back")]

    DEFAULT_CSS = """
    #count { height: 1; padding: 0 1; color: $text-muted; }
    """

    def __init__(self: Self, gateway: StackLister) -> None:
        super().__init__()
        self._gateway = gateway
        self._all_stacks: list[StackSummary] = []

    def compose(self: Self) -> ComposeResult:
        yield Static(id="count")
        yield DataTable(id="stacks")
        yield Footer()

    def on_mount(self: Self) -> None:
        table = self.query_one("#stacks", DataTable)
        table.cursor_type = "row"
        table.add_columns(*COLUMNS)
        table.loading = True
        table.focus()
        self._fetch_stacks()

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _fetch_stacks(self: Self) -> list[StackSummary]:
        return self._gateway.list_stacks()

    def on_worker_state_changed(self: Self, event: Worker.StateChanged) -> None:
        if event.worker.name != "_fetch_stacks":
            return
        if event.state == WorkerState.SUCCESS:
            self._all_stacks = event.worker.result or []
            self.query_one("#stacks", DataTable).loading = False
            self._render_rows()
        elif event.state == WorkerState.ERROR and event.worker.error is not None:
            raise event.worker.error

    def _render_rows(self: Self) -> None:
        table = self.query_one("#stacks", DataTable)
        table.clear()
        now = datetime.now(tz=UTC)
        for stack in self._all_stacks:
            table.add_row(
                stack.name,
                Text(stack.status, style=status_style(stack.status)),
                relative_age(stack.created, now),
                relative_age(stack.updated, now),
                key=stack.name,
            )
        self.query_one("#count", Static).update(f"{len(self._all_stacks)} stacks")

    def action_back(self: Self) -> None:
        self.app.pop_screen()
