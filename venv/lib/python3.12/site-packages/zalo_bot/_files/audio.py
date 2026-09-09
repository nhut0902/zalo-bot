"""This module contains an object that represents a Zalo Bot Audio."""
from typing import Optional

from zalo_bot._files._base_thumbed_medium import _BaseThumbedMedium
from zalo_bot._files.photo_size import PhotoSize
from zalo_bot._utils.types import JSONDict


class Audio(_BaseThumbedMedium):
    """This object represents an audio file to be treated as music by the Zalo Bot clients.

    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if their :attr:`file_unique_id` is equal.


    Args:
        file_id (:obj:`str`): Identifier for this file, which can be used to download
            or reuse the file.
        file_unique_id (:obj:`str`): Unique identifier for this file, which is supposed to be
            the same over time and for different bots. Can't be used to download or reuse the file.
        duration (:obj:`int`): Duration of the audio in seconds as defined by the sender.
        performer (:obj:`str`, optional): Performer of the audio as defined by the sender or by
            audio tags.
        title (:obj:`str`, optional): Title of the audio as defined by the sender or by audio tags.
        file_name (:obj:`str`, optional): Original filename as defined by the sender.
        mime_type (:obj:`str`, optional): MIME type of the file as defined by the sender.
        file_size (:obj:`int`, optional): File size in bytes.
        thumbnail (:class:`zalo_bot.PhotoSize`, optional): Thumbnail of the album cover to
            which the music file belongs.

    Attributes:
        file_id (:obj:`str`): Identifier for this file, which can be used to download
            or reuse the file.
        file_unique_id (:obj:`str`): Unique identifier for this file, which is supposed to be
            the same over time and for different bots. Can't be used to download or reuse the file.
        duration (:obj:`int`): Duration of the audio in seconds as defined by the sender.
        performer (:obj:`str`): Optional. Performer of the audio as defined by the sender or by
            audio tags.
        title (:obj:`str`): Optional. Title of the audio as defined by the sender or by audio tags.
        file_name (:obj:`str`): Optional. Original filename as defined by the sender.
        mime_type (:obj:`str`): Optional. MIME type of the file as defined by the sender.
        file_size (:obj:`int`): Optional. File size in bytes.
        thumbnail (:class:`zalo_bot.PhotoSize`): Optional. Thumbnail of the album cover to
            which the music file belongs.


    """

    __slots__ = ("duration", "file_name", "mime_type", "performer", "title")

    def __init__(
        self,
        file_id: str,
        file_unique_id: str,
        duration: int,
        performer: Optional[str] = None,
        title: Optional[str] = None,
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
            self.duration: int = duration
            # Optional
            self.performer: Optional[str] = performer
            self.title: Optional[str] = title
            self.mime_type: Optional[str] = mime_type
            self.file_name: Optional[str] = file_name
