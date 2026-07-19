"""Tests for the load-more support in ResourceListScreen."""

from datetime import datetime  # noqa: TC003
from typing import Self

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from awst.screens.resource_list import ResourceListScreen


class PagedScreen(ResourceListScreen[str]):
    """Minimal paged list: each page is a list of item names."""

    TITLE = "Paged"
    COLUMNS = ("Name",)
    NOUN = "thing"

    def __init__(self: Self, pages: list[list[str]]) -> None:
        super().__init__()
        self._pages = pages
        self._next = 0

    def _list(self: Self) -> list[str]:
        self._next = 1
        return list(self._pages[0])

    def _has_more(self: Self) -> bool:
        return self._next < len(self._pages)

    def _list_more(self: Self) -> list[str]:
        page = self._pages[self._next]
        self._next += 1
        return list(page)

    def _row(self: Self, item: str, now: datetime) -> tuple[str, ...]:  # noqa: ARG002
        return (item,)

    def _item_name(self: Self, item: str) -> str:
        return item


class PagedApp(App[None]):
    """Minimal harness that opens a PagedScreen directly."""

    def __init__(self: Self, pages: list[list[str]]) -> None:
        super().__init__()
        self.pages = pages

    def on_mount(self: Self) -> None:
        self.push_screen(PagedScreen(self.pages))


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
async def test_filtered_count_keeps_plus_suffix() -> None:
    app = PagedApp([["apple", "banana"], ["cherry"]])

    async with app.run_test() as pilot:
        await _settle(app)
        await pilot.pause()

        await pilot.press("slash")
        await pilot.press(*"app")
        await pilot.pause()

        assert str(app.screen.query_one("#count", Static).content) == "1 of 2+ things"
