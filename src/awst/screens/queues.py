"""SQS queue list screen."""

from typing import TYPE_CHECKING, Protocol, Self

from textual.worker import get_current_worker

from awst.aws.models import Page, QueueSummary
from awst.screens.resource_list import ResourceListScreen

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime


class QueueLister(Protocol):
    """The slice of the SQS gateway this screen needs."""

    def list_queues(self: Self, next_token: str | None = None) -> Page[QueueSummary]: ...


class QueueListScreen(ResourceListScreen[QueueSummary]):
    """Read-only list of the region's SQS queues."""

    TITLE = "SQS queues"
    COLUMNS = ("Name", "Type")
    NOUN = "queue"

    def __init__(self: Self, gateway: QueueLister) -> None:
        super().__init__()
        self._gateway = gateway
        self._next_token: str | None = None

    def _list(self: Self) -> list[QueueSummary]:
        page = self._gateway.list_queues()
        if not get_current_worker().is_cancelled:
            self._next_token = page.next_token
        return list(page.items)

    def _has_more(self: Self) -> bool:
        return self._next_token is not None

    def _list_more(self: Self) -> list[QueueSummary]:
        page = self._gateway.list_queues(self._next_token)
        if not get_current_worker().is_cancelled:
            self._next_token = page.next_token
        return list(page.items)

    def _sort_key(self: Self) -> Callable[[QueueSummary], str]:
        return lambda queue: queue.name

    def _row(self: Self, item: QueueSummary, now: datetime) -> tuple[str, ...]:  # noqa: ARG002 - no timestamp column
        return (item.name, "FIFO" if item.is_fifo else "Standard")

    def _item_name(self: Self, item: QueueSummary) -> str:
        return item.name
