"""Common base class for media objects with thumbnails"""
from typing import TYPE_CHECKING, Optional, Type, TypeVar

from zalo_bot._files._base_medium import _BaseMedium
from zalo_bot._files.photo_size import PhotoSize
from zalo_bot._utils.types import JSONDict

if TYPE_CHECKING:
    from zalo_bot import Bot

# pylint: disable=invalid-name
ThumbedMT_co = TypeVar("ThumbedMT_co", bound="_BaseThumbedMedium", covariant=True)


class _BaseThumbedMedium(_BaseMedium):
    """
    Base class for objects representing the various media file types that may include a thumbnail.

    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if their :attr:`file_unique_id` is equal.

    Args:
        file_id (:obj:`str`): Identifier for this file, which can be used to download
            or reuse the file.
        file_unique_id (:obj:`str`): Unique identifier for this file, which
            is supposed to be the same over time and for different bots.
            Can't be used to download or reuse the file.
        file_size (:obj:`int`, optional): File size.
        thumbnail (:class:`zalo_bot.PhotoSize`, optional): Thumbnail as defined by the sender.

    Attributes:
        file_id (:obj:`str`): File identifier.
        file_unique_id (:obj:`str`): Unique identifier for this file, which
            is supposed to be the same over time and for different bots.
            Can't be used to download or reuse the file.
        file_size (:obj:`int`): Optional. File size.
        thumbnail (:class:`zalo_bot.PhotoSize`): Optional. Thumbnail as defined by the sender.

    """

    __slots__ = ("thumbnail",)

    def __init__(
        self,
        file_id: str,
        file_unique_id: str,
        file_size: Optional[int] = None,
        thumbnail: Optional[PhotoSize] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_size=file_size,
            api_kwargs=api_kwargs,
        )

        self.thumbnail: Optional[PhotoSize] = thumbnail

    @classmethod
    def de_json(
        cls: Type[ThumbedMT_co], data: Optional[JSONDict], bot: Optional["Bot"] = None
    ) -> Optional[ThumbedMT_co]:
        """See :meth:`zalo_bot.ZaloObject.de_json`."""
        data = cls._parse_data(data)

        if not data:
            return None

        # In case this wasn't already done by the subclass
        if not isinstance(data.get("thumbnail"), PhotoSize):
            data["thumbnail"] = PhotoSize.de_json(data.get("thumbnail"), bot)

        api_kwargs = {}
        # This is a deprecated field that TG still returns for backwards compatibility
        # Let's filter it out to speed up the de-json process
        if data.get("thumb") is not None:
            api_kwargs["thumb"] = data.pop("thumb")

        return super()._de_json(data=data, bot=bot, api_kwargs=api_kwargs)
