import pytest
from textual.widgets import Label

from awst.skeleton_app import SkeletonApp


@pytest.mark.asyncio
async def test_happy_path() -> None:
    # arrange
    app = SkeletonApp()

    # act
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        label = app.query_one(Label)

    # assert
    assert label.content == "Hello AWS TUI"
