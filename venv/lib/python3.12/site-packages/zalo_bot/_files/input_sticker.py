"""This module contains an object that represents a Zalo Bot InputSticker."""

from typing import TYPE_CHECKING, Optional, Sequence, Tuple, Union

from zalo_bot._files.sticker import MaskPosition
from zalo_bot._zalo_object import ZaloObject
from zalo_bot._utils.argument_parsing import parse_sequence_arg
from zalo_bot._utils.files import parse_file_input
from zalo_bot._utils.types import FileInput, JSONDict

if TYPE_CHECKING:
    from zalo_bot._files.input_file import InputFile


class InputSticker(ZaloObject):
    """
    This object describes a sticker to be added to a sticker set.

    Args:
        sticker (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` \
            | :class:`pathlib.Path`): The
            added sticker. |uploadinputnopath| Animated and video stickers can't be uploaded via
            HTTP URL.
        emoji_list (Sequence[:obj:`str`]): Sequence of
            :tg-const:`zalo_bot.constants.StickerLimit.MIN_STICKER_EMOJI` -
            :tg-const:`zalo_bot.constants.StickerLimit.MAX_STICKER_EMOJI` emoji associated with the
            sticker.
        mask_position (:class:`zalo_bot.MaskPosition`, optional): Position where the mask should be
            placed on faces. For ":tg-const:`zalo_bot.constants.StickerType.MASK`" stickers only.
        keywords (Sequence[:obj:`str`], optional): Sequence of
            0-:tg-const:`zalo_bot.constants.StickerLimit.MAX_SEARCH_KEYWORDS` search keywords
            for the sticker with the total length of up to
            :tg-const:`zalo_bot.constants.StickerLimit.MAX_KEYWORD_LENGTH` characters. For
            ":tg-const:`zalo_bot.constants.StickerType.REGULAR`" and
            ":tg-const:`zalo_bot.constants.StickerType.CUSTOM_EMOJI`" stickers only.
        format (:obj:`str`): Format of the added sticker, must be one of
            :tg-const:`zalo_bot.constants.StickerFormat.STATIC` for a
            ``.WEBP`` or ``.PNG`` image, :tg-const:`zalo_bot.constants.StickerFormat.ANIMATED`
            for a ``.TGS`` animation, :tg-const:`zalo_bot.constants.StickerFormat.VIDEO` for a WEBM
            video.

            

    Attributes:
        sticker (:obj:`str` | :class:`zalo_bot.InputFile`): The added sticker.
        emoji_list (Tuple[:obj:`str`]): Tuple of
            :tg-const:`zalo_bot.constants.StickerLimit.MIN_STICKER_EMOJI` -
            :tg-const:`zalo_bot.constants.StickerLimit.MAX_STICKER_EMOJI` emoji associated with the
            sticker.
        mask_position (:class:`zalo_bot.MaskPosition`): Optional. Position where the mask should be
            placed on faces. For ":tg-const:`zalo_bot.constants.StickerType.MASK`" stickers only.
        keywords (Tuple[:obj:`str`]): Optional. Tuple of
            0-:tg-const:`zalo_bot.constants.StickerLimit.MAX_SEARCH_KEYWORDS` search keywords
            for the sticker with the total length of up to
            :tg-const:`zalo_bot.constants.StickerLimit.MAX_KEYWORD_LENGTH` characters. For
            ":tg-const:`zalo_bot.constants.StickerType.REGULAR`" and
            ":tg-const:`zalo_bot.constants.StickerType.CUSTOM_EMOJI`" stickers only.
            ":tg-const:`zalo_bot.constants.StickerType.CUSTOM_EMOJI`" stickers only.
        format (:obj:`str`): Format of the added sticker, must be one of
            :tg-const:`zalo_bot.constants.StickerFormat.STATIC` for a
            ``.WEBP`` or ``.PNG`` image, :tg-const:`zalo_bot.constants.StickerFormat.ANIMATED`
            for a ``.TGS`` animation, :tg-const:`zalo_bot.constants.StickerFormat.VIDEO` for a WEBM
            video.

            
    """

    __slots__ = ("emoji_list", "format", "keywords", "mask_position", "sticker")

    def __init__(
        self,
        sticker: FileInput,
        emoji_list: Sequence[str],
        format: str,  # pylint: disable=redefined-builtin
        mask_position: Optional[MaskPosition] = None,
        keywords: Optional[Sequence[str]] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)

        # We use local_mode=True because we don't have access to the actual setting and want
        # things to work in local mode.
        self.sticker: Union[str, InputFile] = parse_file_input(
            sticker,
            local_mode=True,
            attach=True,
        )
        self.emoji_list: Tuple[str, ...] = parse_sequence_arg(emoji_list)
        self.format: str = format
        self.mask_position: Optional[MaskPosition] = mask_position
        self.keywords: Tuple[str, ...] = parse_sequence_arg(keywords)

        self._freeze()
