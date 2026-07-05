"""Tests for the app shell and home-screen navigation."""

import pytest
from textual.widgets import DataTable, OptionList

from awst.app import AwstApp
from awst.screens.buckets import BucketListScreen
from awst.screens.home import HomeScreen
from awst.screens.stack_detail import StackDetailScreen
from awst.screens.stacks import StackListScreen
from tests.fakes import FakeCloudFormationGateway, FakeS3Gateway, make_bucket, make_detail, make_stack


@pytest.mark.asyncio
async def test_home_screen_lists_services_with_sqs_still_disabled() -> None:
    app = AwstApp(cloudformation_gateway=FakeCloudFormationGateway())

    async with app.run_test() as pilot:
        await pilot.pause()
        options = app.screen.query_one(OptionList)

        assert isinstance(app.screen, HomeScreen)
        assert options.option_count == 3
        assert options.get_option("cloudformation").disabled is False
        assert options.get_option("s3").disabled is False
        assert options.get_option("sqs").disabled is True


@pytest.mark.asyncio
async def test_disabled_services_are_skipped_by_navigation() -> None:
    app = AwstApp(cloudformation_gateway=FakeCloudFormationGateway())

    async with app.run_test() as pilot:
        await pilot.pause()
        options = app.screen.query_one(OptionList)
        assert options.highlighted == 0

        await pilot.press("down")
        await pilot.pause()
        assert options.highlighted == 1  # s3 is enabled now

        await pilot.press("down")
        await pilot.pause()
        assert options.highlighted == 1  # nowhere to go: sqs below is disabled


@pytest.mark.asyncio
async def test_enter_opens_stack_list_and_escape_returns_home() -> None:
    gateway = FakeCloudFormationGateway(stacks=[make_stack("prod-api")])
    app = AwstApp(cloudformation_gateway=gateway)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert isinstance(app.screen, StackListScreen)
        assert app.screen.query_one(DataTable).row_count == 1

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, HomeScreen)


@pytest.mark.asyncio
async def test_selecting_s3_opens_bucket_list() -> None:
    app = AwstApp(
        cloudformation_gateway=FakeCloudFormationGateway(),
        s3_gateway=FakeS3Gateway(buckets=[make_bucket("assets")]),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # highlight s3
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert isinstance(app.screen, BucketListScreen)
        assert app.screen.query_one(DataTable).row_count == 1


@pytest.mark.asyncio
async def test_enter_twice_drills_from_home_into_stack_details() -> None:
    gateway = FakeCloudFormationGateway(stacks=[make_stack("prod-api")], detail=make_detail())
    app = AwstApp(cloudformation_gateway=gateway)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert isinstance(app.screen, StackDetailScreen)


@pytest.mark.asyncio
async def test_q_quits_from_home() -> None:
    app = AwstApp(cloudformation_gateway=FakeCloudFormationGateway())

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()

    assert app.return_code == 0
