from __future__ import annotations

import asyncio
from typing import List

from zalo_bot._bot import Bot
from zalo_bot._update import Update
from zalo_bot._utils.default_value import DEFAULT_NONE
from zalo_bot._utils.logging import get_logger

from ._handler import CommandHandler


class Application:
    """Main class that dispatches updates to handlers."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.handlers: List[CommandHandler] = []
        self._running = False
        self._logger = get_logger(__name__, "Application")
        self.update_queue: asyncio.Queue[object] = DEFAULT_NONE

    def add_handler(self, handler: CommandHandler) -> None:
        self.handlers.append(handler)
    
    async def process_update(self, update: Update) -> None:
        for handler in self.handlers:
            if handler.check_update(update):
                coroutine = handler.handle_update(update, self)
                task = asyncio.create_task(coroutine)
                await task
                break

    def process_update_sync(self, update: Update) -> None:
        asyncio.run(self.process_update(update))

    async def _polling_loop(self) -> None:
        await self.bot.initialize()
        self._running = True
        try:
            while self._running:
                try:
                    update = await self.bot.get_update(timeout=30)
                except Exception as exc:  # pragma: no cover - logging only
                    self._logger.exception("Error while fetching updates: %s", exc)
                    await asyncio.sleep(1)
                    continue
                if update:
                    await self.process_update(update)
                else:
                    await asyncio.sleep(1)
        finally:
            await self.bot.shutdown()

    def run_polling(self) -> None:
        asyncio.run(self._polling_loop())


class ApplicationBuilder:
    """Builder for :class:`Application`."""

    def __init__(self) -> None:
        self._token: str | None = None

    def token(self, token: str) -> 'ApplicationBuilder':
        self._token = token
        return self
    
    def base_url(self, base_url: str) -> 'ApplicationBuilder':
        if not self._token:
            raise ValueError("Token must be set before setting base URL")
        self._base_url = base_url
        return self

    def build(self) -> Application:
        if not self._token:
            raise ValueError("Token must be set")
        bot = Bot(token=self._token, base_url=self._base_url if hasattr(self, '_base_url') else None)
        return Application(bot)
