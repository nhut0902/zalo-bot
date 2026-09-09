"""This module contains an object that represents a Zalo Bot Video."""
from typing import Optional

from zalo_bot._files._base_thumbed_medium import _BaseThumbedMedium
from zalo_bot._files.photo_size import PhotoSize
from zalo_bot._utils.types import JSONDict


class Video(_BaseThumbedMedium):
    """This object represents a video file.

    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if their :attr:`file_unique_id` is equal.

    .. versionchanged:: 20.5
      |removed_thumb_note|

    Args:
        file_id (:obj:`str`): Identifier for this file, which can be used to download
            or reuse the file.
        file_unique_id (:obj:`str`): Unique identifier for this file, which
            is supposed to be the same over time and for different bots.
            Can't be used to download or reuse the file.
        width (:obj:`int`): Video width as defined by the sender.
        height (:obj:`int`): Video height as defined by the sender.
        duration (:obj:`int`): Duration of the video in seconds as defined by the sender.
        file_name (:obj:`str`, optional): Original filename as defined by the sender.
        mime_type (:obj:`str`, optional): MIME type of a file as defined by the sender.
        file_size (:obj:`int`, optional): File size in bytes.
        thumbnail (:class:`zalo_bot.PhotoSize`, optional): Video thumbnail.

    Attributes:
        file_id (:obj:`str`): Identifier for this file, which can be used to download
            or reuse the file.
        file_unique_id (:obj:`str`): Unique identifier for this file, which
            is supposed to be the same over time and for different bots.
            Can't be used to download or reuse the file.
        width (:obj:`int`): Video width as defined by the sender.
        height (:obj:`int`): Video height as defined by the sender.
        duration (:obj:`int`): Duration of the video in seconds as defined by the sender.
        file_name (:obj:`str`): Optional. Original filename as defined by the sender.
        mime_type (:obj:`str`): Optional. MIME type of a file as defined by the sender.
        file_size (:obj:`int`): Optional. File size in bytes.
        thumbnail (:class:`zalo_bot.PhotoSize`): Optional. Video thumbnail.
    """

    __slots__ = ("duration", "file_name", "height", "mime_type", "width")

    def __init__(
        self,
        file_id: str,
        file_unique_id: str,
        width: int,
        height: int,
        duration: int,
        mime_type: Optional[str] = None,
        file_size: Optional[int] = None,
        file_name: Optional[str] = None,
        thumbnail: Optional[PhotoSize] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_size=file_size,
            thumbnail=thumbnail,
            api_kwargs=api_kwargs,
        )
        with self._unfrozen():
            # Required
            self.width: int = width
            self.height: int = height
            self.duration: int = duration
            # Optional
            self.mime_type: Optional[str] = mime_type
            self.file_name: Optional[str] = file_name
