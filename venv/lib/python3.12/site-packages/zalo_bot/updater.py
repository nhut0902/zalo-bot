from __future__ import annotations

from ._bot import Bot
from .ext._dispatcher import Dispatcher


class Updater:
    """Simple wrapper that provides a bot and dispatcher."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.bot = Bot(token=token)
        self.dispatcher = Dispatcher(self.bot)

    def start_polling(self) -> None:
        """Placeholder for polling logic."""
        raise NotImplementedError

    def idle(self) -> None:
        """Placeholder for idle logic."""
        raise NotImplementedError
