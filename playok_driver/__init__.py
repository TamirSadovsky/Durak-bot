"""Playwright adapter for PlayOK Durak."""

from .browser import BrowserConfig, launch_browser
from .loop import BotLoop, LoopConfig
from .parser import ParsedTable, find_game_page, parse_page

__all__ = [
    "BrowserConfig",
    "launch_browser",
    "BotLoop",
    "LoopConfig",
    "ParsedTable",
    "find_game_page",
    "parse_page",
]
