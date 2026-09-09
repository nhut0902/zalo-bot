from __future__ import annotations

from typing import Callable, Awaitable, Any
import inspect

from zalo_bot._update import Update
from ._context import ContextTypes, CallbackContext


class CommandHandler:
    """Handle commands like ``/start``."""

    def __init__(self, command: str, callback: Callable[[Update, CallbackContext], Awaitable[None]]):
        self.command = command
        self.callback = callback

    def check_update(self, update: Update) -> bool:
        if update.message and update.message.text:
            return update.message.text.strip().split()[0] == f"/{self.command}"
        return False

    async def handle_update(self, update: Update, application: 'Application') -> None:
        text = update.message.text if update.message else ''
        args = text.split()[1:] if text else []
        context = ContextTypes.DEFAULT_TYPE(application, args=args)
        result: Any = self.callback(update, context)
        if inspect.isawaitable(result):
            await result

class MessageHandler:
    """Handle non-command text messages using filters."""

    def __init__(self, filters: Callable[[Update], bool], callback: Callable[[Update, CallbackContext], Awaitable[None]]):
        self.filters = filters
        self.callback = callback

    def check_update(self, update: Update) -> bool:
        return bool(update.message and self.filters(update))

    async def handle_update(self, update: Update, application: 'Application') -> None:
        context = ContextTypes.DEFAULT_TYPE(application)
        result: Any = self.callback(update, context)
        if inspect.isawaitable(result):
            await result
