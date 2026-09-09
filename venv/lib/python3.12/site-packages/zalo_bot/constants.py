"""Constants used in the Zalo bot library."""

from typing import Final

from zalo_bot._utils.enum import StringEnum

__all__ = [
    "BASE_URL",
    "ChatAction",
    "InputMediaType",
    "InputPaidMediaType",
    "MaskPosition",
    "MessageEntityType",
    "StickerType",
]

BASE_URL: Final[str] = "https://bot-api.zapps.me"


class ChatAction(StringEnum):
    """Available chat actions that can be sent."""

    __slots__ = ()

    TYPING = "typing"


class InputMediaType(StringEnum):
    """Available input media types."""

    __slots__ = ()

    ANIMATION = "animation"
    DOCUMENT = "document"
    AUDIO = "audio"
    PHOTO = "photo"
    VIDEO = "video"


class InputPaidMediaType(StringEnum):
    """Available input paid media types."""

    __slots__ = ()

    PHOTO = "photo"
    VIDEO = "video"


class MaskPosition(StringEnum):
    """Positions for mask stickers."""

    __slots__ = ()

    FOREHEAD = "forehead"
    EYES = "eyes"
    MOUTH = "mouth"
    CHIN = "chin"


class MessageEntityType(StringEnum):
    """Supported message entity types."""

    __slots__ = ()

    BLOCKQUOTE = "blockquote"
    BOLD = "bold"
    BOT_COMMAND = "bot_command"
    CASHTAG = "cashtag"
    CODE = "code"
    CUSTOM_EMOJI = "custom_emoji"
    EMAIL = "email"
    EXPANDABLE_BLOCKQUOTE = "expandable_blockquote"
    HASHTAG = "hashtag"
    ITALIC = "italic"
    MENTION = "mention"
    PHONE_NUMBER = "phone_number"
    PRE = "pre"
    SPOILER = "spoiler"
    STRIKETHROUGH = "strikethrough"
    TEXT_LINK = "text_link"
    TEXT_MENTION = "text_mention"
    UNDERLINE = "underline"
    URL = "url"


class StickerType(StringEnum):
    """Types of stickers."""

    __slots__ = ()

    REGULAR = "regular"
    MASK = "mask"
    CUSTOM_EMOJI = "custom_emoji"
