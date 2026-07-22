"""Tests for the load-more support in ResourceListScreen."""

from datetime import datetime  # noqa: TC003
import threading
from typing import TYPE_CHECKING, Self

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from awst.aws.models import AwsError
from awst.screens.resource_list import ResourceListScreen

if TYPE_CHECKING:
    from collections.abc import Callable


class PagedScreen(ResourceListScreen[str]):
    """Minimal paged list: each page is a list of item names.

    ``fail_more`` makes ``_list_more`` raise instead of returning a page; ``gate`` (set by
    ``started`` once entered) lets tests freeze a load-more mid-flight, mirroring the
    ``empty_gate`` precedent in ``tests/fakes.py``. ``sort`` opts into alphabetical
    re-sorting after every fetch, mirroring the paginated list screens.
    """

    TITLE = "Paged"
    COLUMNS = ("Name",)
    NOUN = "thing"

    def __init__(
        self: Self,
        pages: list[list[str]],
        fail_more: AwsError | None = None,
        gate: threading.Event | None = None,
        started: threading.Event | None = None,
        sort: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        super().__init__()
        self._pages = pages
        self._next = 0
        self._fail_more = fail_more
        self._gate = gate
        self._started = started
        self._sort = sort
        self.more_calls = 0

    def _list(self: Self) -> list[str]:
        self._next = 1
        return list(self._pages[0])

    def _has_more(self: Self) -> bool:
        return self._next < len(self._pages)

    def _list_more(self: Self) -> list[str]:
        self.more_calls += 1
        if self._started is not None:
            self._started.set()
        if self._fail_more is not None:
            raise self._fail_more
        if self._gate is not None:
            self._gate.wait(timeout=5)
        page = self._pages[self._next]
        self._next += 1
        return list(page)

    def _sort_key(self: Self) -> Callable[[str], str] | None:
        return (lambda item: item) if self._sort else None

    def _row(self: Self, item: str, now: datetime) -> tuple[str, ...]:  # noqa: ARG002
        return (item,)

    def _item_name(self: Self, item: str) -> str:
        return item


class PagedApp(App[None]):
    """Minimal harness that opens a PagedScreen directly."""

    def __init__(
        self: Self,
        pages: list[list[str]],
        fail_more: AwsError | None = None,
        gate: threading.Event | None = None,
        started: threading.Event | None = None,
        sort: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        super().__init__()
        self.pages = pages
        self.fail_more = fail_more
        self.gate = gate
        self.started = started
        self.sort = sort

    def on_mount(self: Self) -> None:
        self.push_screen(
            PagedScreen(self.pages, fail_more=self.fail_more, gate=self.gate, started=self.started, sort=self.sort)
        )


async def _settle(app: App[None]) -> None:
    await app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_more_binding_hidden_when_there_is_no_more() -> None:
    app = PagedApp([["a", "b"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        assert app.screen.check_action("load_more", ()) is False
        assert str(app.screen.query_one("#count", Static).content) == "2 things"


@pytest.mark.asyncio
async def test_count_shows_plus_suffix_while_more_pages_remain() -> None:
    app = PagedApp([["a", "b"], ["c"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        assert app.screen.check_action("load_more", ()) is True
        assert str(app.screen.query_one("#count", Static).content) == "2+ things"


@pytest.mark.asyncio
async def test_m_appends_the_next_page() -> None:
    app = PagedApp([["a", "b"], ["c"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("m")
        await _settle(app)
        await pilot.pause()
        table = app.screen.query_one(DataTable)

        assert table.row_count == 3
        assert table.get_row_at(2)[0] == "c"
        assert str(app.screen.query_one("#count", Static).content) == "3 things"
        assert app.screen.check_action("load_more", ()) is False


@pytest.mark.asyncio
async def test_m_with_no_more_pages_does_nothing() -> None:
    app = PagedApp([["a"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("m")
        await _settle(app)
        await pilot.pause()

        assert app.screen.query_one(DataTable).row_count == 1


@pytest.mark.asyncio
async def test_refresh_restarts_from_the_first_page() -> None:
    app = PagedApp([["a", "b"], ["c"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()
        await pilot.press("m")
        await _settle(app)
        await pilot.pause()
        assert app.screen.query_one(DataTable).row_count == 3

        await pilot.press("r")
        await _settle(app)
        await pilot.pause()

        assert app.screen.query_one(DataTable).row_count == 2
        assert str(app.screen.query_one("#count", Static).content) == "2+ things"


@pytest.mark.asyncio
async def test_filtering_fetches_remaining_pages_and_drops_plus_suffix() -> None:
    app = PagedApp([["apple", "banana"], ["cherry"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("slash")
        await pilot.press(*"app")
        await _settle(app)
        await pilot.pause()

        # Auto-fetch-on-filter (default True) fetches every remaining page, so once settled
        # there's no "+" left to show: "cherry" was fetched too, just filtered out of view.
        assert str(app.screen.query_one("#count", Static).content) == "1 of 3 things"


@pytest.mark.asyncio
async def test_load_more_failure_keeps_rows_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    toasts: list[str] = []

    def record_notify(self: App[None], message: str, **kwargs: object) -> None:
        toasts.append(message)

    monkeypatch.setattr(App, "notify", record_notify)
    app = PagedApp([["a", "b"], ["c"]], fail_more=AwsError("throttled"))

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("m")
        await _settle(app)
        await pilot.pause()
        table = app.screen.query_one(DataTable)

        assert table.row_count == 2  # existing rows kept, nothing appended
        assert toasts == ["throttled"]
        assert str(app.screen.query_one("#count", Static).content) == "2+ things"  # not stuck on "loading more…"
        assert app.screen.check_action("load_more", ()) is True  # More still available so the user can retry


@pytest.mark.asyncio
async def test_second_m_press_is_ignored_while_a_load_more_is_in_flight() -> None:
    gate = threading.Event()
    started = threading.Event()
    app = PagedApp([["a", "b"], ["c"]], gate=gate, started=started)

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PagedScreen)

        await pilot.press("m")
        assert started.wait(timeout=5)  # the worker has actually entered _list_more
        await pilot.pause()

        assert screen.check_action("load_more", ()) is False
        assert screen.more_calls == 1

        await pilot.press("m")  # a second press must not start another fetch
        await pilot.pause()
        assert screen.more_calls == 1

        gate.set()
        await _settle(app)
        await pilot.pause()

        table = screen.query_one(DataTable)
        assert table.row_count == 3  # the released page was appended exactly once
        assert screen.more_calls == 1
        assert screen.check_action("load_more", ()) is False


@pytest.mark.asyncio
async def test_m_press_keeps_accumulated_items_sorted() -> None:
    app = PagedApp([["banana"], ["apple"]], sort=True)

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("m")
        await _settle(app)
        await pilot.pause()
        table = app.screen.query_one(DataTable)

        assert table.row_count == 2
        assert table.get_row_at(0)[0] == "apple"
        assert table.get_row_at(1)[0] == "banana"


@pytest.mark.asyncio
async def test_typing_a_filter_fetches_every_remaining_page() -> None:
    app = PagedApp([["apple"], ["banana"], ["cherry"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PagedScreen)

        await pilot.press("slash")
        await pilot.press(*"c")
        await _settle(app)
        await pilot.pause()

        assert screen.more_calls == 2  # both remaining pages fetched in one go
        assert screen.check_action("load_more", ()) is False
        table = app.screen.query_one(DataTable)
        assert table.row_count == 1
        assert table.get_row_at(0)[0] == "cherry"


@pytest.mark.asyncio
async def test_count_shows_searching_while_fetching_remaining_pages() -> None:
    gate = threading.Event()
    started = threading.Event()
    app = PagedApp([["apple"], ["banana"]], gate=gate, started=started)

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("slash")
        await pilot.press(*"a")
        assert started.wait(timeout=5)  # the worker has actually entered _list_more
        await pilot.pause()

        assert str(app.screen.query_one("#count", Static).content) == "searching…"

        gate.set()
        await _settle(app)
        await pilot.pause()
