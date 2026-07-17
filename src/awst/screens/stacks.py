"""CloudFormation stack list screen."""

from typing import TYPE_CHECKING, Protocol, Self

from rich.text import Text
from textual.widgets import DataTable  # noqa: TC002 -- needed at runtime: Textual inspects handler annotations

from awst.aws.models import StackSummary
from awst.screens.formatting import relative_age, status_style
from awst.screens.resource_list import ResourceListScreen
from awst.screens.stack_detail import StackDetailScreen, StackInspector

if TYPE_CHECKING:
    from datetime import datetime


class StackLister(Protocol):
    """The slice of the CloudFormation gateway this screen needs."""

    def list_stacks(self: Self) -> list[StackSummary]: ...


class StackGateway(StackLister, StackInspector, Protocol):
    """Everything the stack screens collectively need from CloudFormation."""


class StackListScreen(ResourceListScreen[StackSummary]):
    """Read-only list of the account's CloudFormation stacks."""

    TITLE = "CloudFormation stacks"
    COLUMNS = ("Name", "Status", "Created", "Updated")
    NOUN = "stack"

    def __init__(self: Self, gateway: StackGateway) -> None:
        super().__init__()
        self._gateway = gateway

    def _list(self: Self) -> list[StackSummary]:
        return self._gateway.list_stacks()

    def _row(self: Self, item: StackSummary, now: datetime) -> tuple[str | Text, ...]:
        return (
            item.name,
            Text(item.status, style=status_style(item.status)),
            relative_age(item.created, now),
            relative_age(item.updated, now),
        )

    def _item_name(self: Self, item: StackSummary) -> str:
        return item.name

    def on_data_table_row_selected(self: Self, event: DataTable.RowSelected) -> None:
        name = event.row_key.value
        if name is not None:
            self.app.push_screen(StackDetailScreen(self._gateway, name))

    def on_screen_resume(self: Self) -> None:
        if self._loaded:  # skip the initial push; on_mount already fetches
            self.action_refresh()
