# zalo_bot/ext/dispatcher.py
import asyncio
from typing import List, Optional
from zalo_bot._bot import Bot
from zalo_bot._update import Update
from ._application import Application
from ._handler import CommandHandler


class Dispatcher:
    def __init__(self, bot: Bot, update_queue: Optional[asyncio.Queue] = None, workers: int = 0) -> None:
        self.bot = bot
        self.application = Application(bot)
        self.handlers: List[CommandHandler] = []
        self._external_queue = update_queue
        self.update_queue = None  # defer init
        self.workers = workers
        self._worker_tasks: List[asyncio.Task] = []

    def add_handler(self, handler: CommandHandler) -> None:
        self.handlers.append(handler)
        self.application.add_handler(handler)

    def process_update(self, update: Update) -> None:
        self.application.process_update_sync(update)

    async def start(self) -> None:
        await self.bot.initialize()
        if self.workers > 0:
            for _ in range(self.workers):
                task = asyncio.create_task(self._worker_loop())
                self._worker_tasks.append(task)

    async def stop(self) -> None:
        for _ in range(self.workers):
            await self.update_queue.put(None)
        await asyncio.gather(*self._worker_tasks)
        await self.bot.shutdown()

    async def _worker_loop(self) -> None:
        while True:
            update = await self.update_queue.get()
            if update is None:
                break
            try:
                await self.application.process_update(update)
            finally:
                self.update_queue.task_done()

    async def feed_update(self, update: Update) -> None:
        if self.workers > 0:
            await self.update_queue.put(update)
        else:
            await self.process_update(update)
