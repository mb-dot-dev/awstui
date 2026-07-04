"""
Skeleton app for testing the awstui package.
"""

from typing import Self

from textual.app import App, ComposeResult
from textual.widgets import Label


class SkeletonApp(App):
    CSS = """
    Screen { align: center middle; }
    Label { width: auto; }
    """

    def compose(self: Self) -> ComposeResult:
        yield Label("Hello AWS TUI")
