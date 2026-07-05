"""S3 bucket list screen."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Protocol, Self

from textual import work
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, Static
from textual.worker import WorkerState

from awst.aws.models import AwsError
from awst.screens.formatting import relative_age

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType
    from textual.worker import Worker

    from awst.aws.models import BucketSummary

COLUMNS = ("Name", "Region", "Created")


class BucketLister(Protocol):
    """The slice of the S3 gateway this screen needs."""

    def list_buckets(self: Self) -> list[BucketSummary]: ...


class BucketListScreen(Screen[None]):
    """Read-only list of the account's S3 buckets."""

    TITLE = "S3 buckets"

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back_or_clear", "Back"),
        ("r", "refresh", "Refresh"),
        ("slash", "focus_filter", "Filter"),
    ]

    DEFAULT_CSS = """
    #count { height: 1; padding: 0 1; color: $text-muted; }
    #error { display: none; padding: 1 2; color: $text-error; }
    """

    def __init__(self: Self, gateway: BucketLister) -> None:
        super().__init__()
        self._gateway = gateway
        self._all_buckets: list[BucketSummary] = []
        self._loaded = False

    def compose(self: Self) -> ComposeResult:
        yield Static(id="count")
        yield Input(placeholder="filter buckets by name", id="filter")
        yield DataTable(id="buckets")
        yield Static(id="error")
        yield Footer()

    def on_mount(self: Self) -> None:
        table = self.query_one("#buckets", DataTable)
        table.cursor_type = "row"
        table.add_columns(*COLUMNS)
        table.loading = True
        table.focus()
        self._fetch_buckets()

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _fetch_buckets(self: Self) -> list[BucketSummary]:
        return self._gateway.list_buckets()

    def on_worker_state_changed(self: Self, event: Worker.StateChanged) -> None:
        if event.worker.name != "_fetch_buckets":
            return
        if event.state == WorkerState.SUCCESS:
            was_loaded = self._loaded
            self._loaded = True
            self._all_buckets = event.worker.result or []
            table = self.query_one("#buckets", DataTable)
            table.loading = False
            self._render_rows()
            if not was_loaded:
                table.focus()
        elif event.state == WorkerState.ERROR:
            error = event.worker.error
            if isinstance(error, AwsError):
                self._show_error(error)
            elif error is not None:
                raise error

    def _show_error(self: Self, error: AwsError) -> None:
        if self._loaded:
            message = error.message if error.hint is None else f"{error.message} ({error.hint})"
            self.notify(message, title="Refresh failed", severity="error")
            self._render_rows()  # restores the count text over "refreshing…"
            return
        table = self.query_one("#buckets", DataTable)
        table.loading = False
        table.display = False
        self.query_one("#filter", Input).display = False
        self.query_one("#count", Static).display = False
        self.set_focus(None)
        panel = self.query_one("#error", Static)
        panel.update(error.message if error.hint is None else f"{error.message}\n{error.hint}")
        panel.display = True

    def _render_rows(self: Self) -> None:
        table = self.query_one("#buckets", DataTable)
        query = self.query_one("#filter", Input).value.strip().lower()
        visible = [bucket for bucket in self._all_buckets if query in bucket.name.lower()]
        previous = self._cursor_bucket_name(table)
        table.clear()
        now = datetime.now(tz=UTC)
        for bucket in visible:
            table.add_row(bucket.name, bucket.region, relative_age(bucket.created, now), key=bucket.name)
        names = [bucket.name for bucket in visible]
        if previous in names:
            table.move_cursor(row=names.index(previous))
        total = len(self._all_buckets)
        noun = "bucket" if total == 1 else "buckets"
        count = f"{len(visible)} of {total} {noun}" if query else f"{total} {noun}"
        self.query_one("#count", Static).update(count)

    def _cursor_bucket_name(self: Self, table: DataTable) -> str | None:
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return row_key.value

    def on_input_changed(self: Self, event: Input.Changed) -> None:
        if event.input.id == "filter":
            self._render_rows()

    def action_focus_filter(self: Self) -> None:
        self.query_one("#filter", Input).focus()

    def action_refresh(self: Self) -> None:
        self.query_one("#error", Static).display = False
        table = self.query_one("#buckets", DataTable)
        table.display = True
        self.query_one("#filter", Input).display = True
        self.query_one("#count", Static).display = True
        if self._loaded:
            self.query_one("#count", Static).update("refreshing…")
        else:
            table.loading = True
        self._fetch_buckets()

    def action_back_or_clear(self: Self) -> None:
        filter_input = self.query_one("#filter", Input)
        if filter_input.has_focus or filter_input.value:
            filter_input.value = ""
            self.query_one("#buckets", DataTable).focus()
        else:
            self.app.pop_screen()
