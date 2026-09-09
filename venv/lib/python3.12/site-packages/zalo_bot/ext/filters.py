from __future__ import annotations

from typing import Callable

from zalo_bot._update import Update


class BaseFilter:
    def __init__(self, func: Callable[[Update], bool]):
        self.func = func

    def __call__(self, update: Update) -> bool:
        return self.func(update)

    def __and__(self, other: 'BaseFilter') -> 'BaseFilter':
        return BaseFilter(lambda update: self(update) and other(update))

    def __or__(self, other: 'BaseFilter') -> 'BaseFilter':
        return BaseFilter(lambda update: self(update) or other(update))

    def __invert__(self) -> 'BaseFilter':
        return BaseFilter(lambda update: not self(update))


TEXT = BaseFilter(lambda update: bool(update.message and update.message.text))
COMMAND = BaseFilter(
    lambda update: bool(update.message and update.message.text and update.message.text.startswith('/'))
)
PHOTO = BaseFilter(lambda update: bool(update.message and update.message.photo_url))
STICKER = BaseFilter(lambda update: bool(update.message and update.message.sticker))
ALL = BaseFilter(lambda update: True)
