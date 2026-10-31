"""Playwright adapter for PlayOK Durak."""

from .browser import BrowserConfig, launch_browser
from .js_state import LiveBoardState, read_live_state
from .loop import BotLoop, LoopConfig
from .parser import ParsedTable, find_game_page, parse_page

__all__ = [
    "BrowserConfig",
    "launch_browser",
    "LiveBoardState",
    "read_live_state",
    "BotLoop",
    "LoopConfig",
    "ParsedTable",
    "find_game_page",
    "parse_page",
]
