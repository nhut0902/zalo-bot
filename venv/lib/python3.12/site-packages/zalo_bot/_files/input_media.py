"""Base class for Zalo Bot InputMedia Objects."""
from typing import Final, Optional, Sequence, Tuple, Union

from zalo_bot import constants
from zalo_bot._files.animation import Animation
from zalo_bot._files.audio import Audio
from zalo_bot._files.document import Document
from zalo_bot._files.input_file import InputFile
from zalo_bot._files.photo_size import PhotoSize
from zalo_bot._files.video import Video
from zalo_bot._message_entity import MessageEntity
from zalo_bot._zalo_object import ZaloObject
from zalo_bot._utils import enum
from zalo_bot._utils.argument_parsing import parse_sequence_arg
from zalo_bot._utils.default_value import DEFAULT_NONE
from zalo_bot._utils.files import parse_file_input
from zalo_bot._utils.types import FileInput, JSONDict, ODVInput
from zalo_bot.constants import InputMediaType

MediaType = Union[Animation, Audio, Document, PhotoSize, Video]


class InputMedia(ZaloObject):
    """
    Base class for Zalo Bot InputMedia Objects.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>`

    Args:
        media_type (:obj:`str`): Type of media that the instance represents.
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.Animation` |  :class:`zalo_bot.Audio` | \
            :class:`zalo_bot.Document` | :class:`zalo_bot.PhotoSize` | \
            :class:`zalo_bot.Video`): File to send.
            |fileinputnopath|
            Lastly you can pass an existing Zalo Bot media object of the corresponding type
            to send.
        caption (:obj:`str`, optional): Caption of the media to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters after entities
            parsing.
        caption_entities (Sequence[:class:`zalo_bot.MessageEntity`], optional): |caption_entities|


                |sequenceclassargs|

        parse_mode (:obj:`str`, optional): |parse_mode|

    Attributes:
        type (:obj:`str`): Type of the input media.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Media to send.
        caption (:obj:`str`): Optional. Caption of the media to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters after entities
            parsing.
        parse_mode (:obj:`str`): Optional. |parse_mode|
        caption_entities (Tuple[:class:`zalo_bot.MessageEntity`]): Optional. |captionentitiesattr|



                * |tupleclassattrs|
                * |alwaystuple|

    """

    __slots__ = ("caption", "caption_entities", "media", "parse_mode", "type")

    def __init__(
        self,
        media_type: str,
        media: Union[str, InputFile, MediaType],
        caption: Optional[str] = None,
        caption_entities: Optional[Sequence[MessageEntity]] = None,
        parse_mode: ODVInput[str] = DEFAULT_NONE,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        self.type: str = enum.get_member(constants.InputMediaType, media_type, media_type)
        self.media: Union[str, InputFile, Animation, Audio, Document, PhotoSize, Video] = media
        self.caption: Optional[str] = caption
        self.caption_entities: Tuple[MessageEntity, ...] = parse_sequence_arg(caption_entities)
        self.parse_mode: ODVInput[str] = parse_mode

        self._freeze()

    @staticmethod
    def _parse_thumbnail_input(thumbnail: Optional[FileInput]) -> Optional[Union[str, InputFile]]:
        # We use local_mode=True because we don't have access to the actual setting and want
        # things to work in local mode.
        return (
            parse_file_input(thumbnail, attach=True, local_mode=True)
            if thumbnail is not None
            else thumbnail
        )


class InputPaidMedia(ZaloObject):
    """
    Base class for Zalo Bot InputPaidMedia Objects. Currently, it can be one of:

    * :class:`zalo_bot.InputMediaPhoto`
    * :class:`zalo_bot.InputMediaVideo`

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>

    Args:
        type (:obj:`str`): Type of media that the instance represents.
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.PhotoSize` | :class:`zalo_bot.Video`): File
            to send. |fileinputnopath|
            Lastly you can pass an existing Zalo Bot media object of the corresponding type
            to send.

    Attributes:
        type (:obj:`str`): Type of the input media.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Media to send.
    """

    PHOTO: Final[str] = constants.InputPaidMediaType.PHOTO
    """:const:`zalo_bot.constants.InputPaidMediaType.PHOTO`"""
    VIDEO: Final[str] = constants.InputPaidMediaType.VIDEO
    """:const:`zalo_bot.constants.InputPaidMediaType.VIDEO`"""

    __slots__ = ("media", "type")

    def __init__(
        self,
        type: str,  # pylint: disable=redefined-builtin
        media: Union[str, InputFile, PhotoSize, Video],
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        self.type: str = enum.get_member(constants.InputPaidMediaType, type, type)
        self.media: Union[str, InputFile, PhotoSize, Video] = media

        self._freeze()


class InputPaidMediaPhoto(InputPaidMedia):
    """The paid media to send is a photo.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.PhotoSize`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.PhotoSize` object to send.

    Attributes:
        type (:obj:`str`): Type of the media, always
            :tg-const:`zalo_bot.constants.InputPaidMediaType.PHOTO`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Photo to send.
    """

    __slots__ = ()

    def __init__(
        self,
        media: Union[FileInput, PhotoSize],
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        media = parse_file_input(media, PhotoSize, attach=True, local_mode=True)
        super().__init__(type=InputPaidMedia.PHOTO, media=media, api_kwargs=api_kwargs)
        self._freeze()


class InputPaidMediaVideo(InputPaidMedia):
    """
    The paid media to send is a video.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>

    Note:
        *  When using a :class:`zalo_bot.Video` for the :attr:`media` attribute, it will take the
           width, height and duration from that video, unless otherwise specified with the optional
           arguments.
        *  :paramref:`thumbnail` will be ignored for small video files, for which Zalo Bot can
           easily generate thumbnails. However, this behaviour is undocumented and might be
           changed by Zalo Bot.

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.Video`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.Video` object to send.
        thumbnail (:term:`file object` | :obj:`bytes` | :class:`pathlib.Path` | :obj:`str`, \
                optional): |thumbdocstringnopath|
        width (:obj:`int`, optional): Video width.
        height (:obj:`int`, optional): Video height.
        duration (:obj:`int`, optional): Video duration in seconds.
        supports_streaming (:obj:`bool`, optional): Pass :obj:`True`, if the uploaded video is
            suitable for streaming.

    Attributes:
        type (:obj:`str`): Type of the media, always
            :tg-const:`zalo_bot.constants.InputPaidMediaType.VIDEO`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Video to send.
        thumbnail (:class:`zalo_bot.InputFile`): Optional. |thumbdocstringbase|
        width (:obj:`int`): Optional. Video width.
        height (:obj:`int`): Optional. Video height.
        duration (:obj:`int`): Optional. Video duration in seconds.
        supports_streaming (:obj:`bool`): Optional. :obj:`True`, if the uploaded video is
            suitable for streaming.
    """

    __slots__ = ("duration", "height", "supports_streaming", "thumbnail", "width")

    def __init__(
        self,
        media: Union[FileInput, Video],
        thumbnail: Optional[FileInput] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[int] = None,
        supports_streaming: Optional[bool] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        if isinstance(media, Video):
            width = width if width is not None else media.width
            height = height if height is not None else media.height
            duration = duration if duration is not None else media.duration
            media = media.file_id
        else:
            # We use local_mode=True because we don't have access to the actual setting and want
            # things to work in local mode.
            media = parse_file_input(media, attach=True, local_mode=True)

        super().__init__(type=InputPaidMedia.VIDEO, media=media, api_kwargs=api_kwargs)
        with self._unfrozen():
            self.thumbnail: Optional[Union[str, InputFile]] = InputMedia._parse_thumbnail_input(
                thumbnail
            )
            self.width: Optional[int] = width
            self.height: Optional[int] = height
            self.duration: Optional[int] = duration
            self.supports_streaming: Optional[bool] = supports_streaming


class InputMediaAnimation(InputMedia):
    """Represents an animation file (GIF or H.264/MPEG-4 AVC video without sound) to be sent.

    Note:
        When using a :class:`zalo_bot.Animation` for the :attr:`media` attribute, it will take the
        width, height and duration from that animation, unless otherwise specified with the
        optional arguments.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>`
      |removed_thumb_note|

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.Animation`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.Animation` object to send.


               Accept :obj:`bytes` as input.
        filename (:obj:`str`, optional): Custom file name for the animation, when uploading a
            new file. Convenience parameter, useful e.g. when sending files generated by the
            :obj:`tempfile` module.

        caption (:obj:`str`, optional): Caption of the animation to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters
            after entities parsing.
        parse_mode (:obj:`str`, optional): |parse_mode|
        caption_entities (Sequence[:class:`zalo_bot.MessageEntity`], optional): |caption_entities|


                |sequenceclassargs|

        width (:obj:`int`, optional): Animation width.
        height (:obj:`int`, optional): Animation height.
        duration (:obj:`int`, optional): Animation duration in seconds.
        has_spoiler (:obj:`bool`, optional): Pass :obj:`True`, if the animation needs to be covered
            with a spoiler animation.

        thumbnail (:term:`file object` | :obj:`bytes` | :class:`pathlib.Path` | :obj:`str`, \
                optional): |thumbdocstringnopath|

        show_caption_above_media (:obj:`bool`, optional): Pass |show_cap_above_med|


    Attributes:
        type (:obj:`str`): :tg-const:`zalo_bot.constants.InputMediaType.ANIMATION`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Animation to send.
        caption (:obj:`str`): Optional. Caption of the animation to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters
            after entities parsing.
        parse_mode (:obj:`str`): Optional. The parse mode to use for text formatting.
        caption_entities (Tuple[:class:`zalo_bot.MessageEntity`]): Optional. |captionentitiesattr|



                * |tupleclassattrs|
                * |alwaystuple|
        width (:obj:`int`): Optional. Animation width.
        height (:obj:`int`): Optional. Animation height.
        duration (:obj:`int`): Optional. Animation duration in seconds.
        has_spoiler (:obj:`bool`): Optional. :obj:`True`, if the animation is covered with a
            spoiler animation.

        thumbnail (:class:`zalo_bot.InputFile`): Optional. |thumbdocstringbase|

        show_caption_above_media (:obj:`bool`): Optional. |show_cap_above_med|

    """

    __slots__ = (
        "duration",
        "has_spoiler",
        "height",
        "show_caption_above_media",
        "thumbnail",
        "width",
    )

    def __init__(
        self,
        media: Union[FileInput, Animation],
        caption: Optional[str] = None,
        parse_mode: ODVInput[str] = DEFAULT_NONE,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[int] = None,
        caption_entities: Optional[Sequence[MessageEntity]] = None,
        filename: Optional[str] = None,
        has_spoiler: Optional[bool] = None,
        thumbnail: Optional[FileInput] = None,
        show_caption_above_media: Optional[bool] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        if isinstance(media, Animation):
            width = media.width if width is None else width
            height = media.height if height is None else height
            duration = media.duration if duration is None else duration
            media = media.file_id
        else:
            # We use local_mode=True because we don't have access to the actual setting and want
            # things to work in local mode.
            media = parse_file_input(media, filename=filename, attach=True, local_mode=True)

        super().__init__(
            InputMediaType.ANIMATION,
            media,
            caption,
            caption_entities,
            parse_mode,
            api_kwargs=api_kwargs,
        )
        with self._unfrozen():
            self.thumbnail: Optional[Union[str, InputFile]] = self._parse_thumbnail_input(
                thumbnail
            )
            self.width: Optional[int] = width
            self.height: Optional[int] = height
            self.duration: Optional[int] = duration
            self.has_spoiler: Optional[bool] = has_spoiler
            self.show_caption_above_media: Optional[bool] = show_caption_above_media


class InputMediaPhoto(InputMedia):
    """Represents a photo to be sent.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>`

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.PhotoSize`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.PhotoSize` object to send.


               Accept :obj:`bytes` as input.
        filename (:obj:`str`, optional): Custom file name for the photo, when uploading a
            new file. Convenience parameter, useful e.g. when sending files generated by the
            :obj:`tempfile` module.

        caption (:obj:`str`, optional ): Caption of the photo to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters after
            entities parsing.
        parse_mode (:obj:`str`, optional): |parse_mode|
        caption_entities (Sequence[:class:`zalo_bot.MessageEntity`], optional): |caption_entities|


                |sequenceclassargs|
        has_spoiler (:obj:`bool`, optional): Pass :obj:`True`, if the photo needs to be covered
            with a spoiler animation.

        show_caption_above_media (:obj:`bool`, optional): Pass |show_cap_above_med|


    Attributes:
        type (:obj:`str`): :tg-const:`zalo_bot.constants.InputMediaType.PHOTO`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Photo to send.
        caption (:obj:`str`): Optional. Caption of the photo to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters
            after entities parsing.
        parse_mode (:obj:`str`): Optional. |parse_mode|
        caption_entities (Tuple[:class:`zalo_bot.MessageEntity`]): Optional. |captionentitiesattr|



                * |tupleclassattrs|
                * |alwaystuple|
        has_spoiler (:obj:`bool`): Optional. :obj:`True`, if the photo is covered with a
            spoiler animation.

        show_caption_above_media (:obj:`bool`): Optional. |show_cap_above_med|

    """

    __slots__ = (
        "has_spoiler",
        "show_caption_above_media",
    )

    def __init__(
        self,
        media: Union[FileInput, PhotoSize],
        caption: Optional[str] = None,
        parse_mode: ODVInput[str] = DEFAULT_NONE,
        caption_entities: Optional[Sequence[MessageEntity]] = None,
        filename: Optional[str] = None,
        has_spoiler: Optional[bool] = None,
        show_caption_above_media: Optional[bool] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        # We use local_mode=True because we don't have access to the actual setting and want
        # things to work in local mode.
        media = parse_file_input(media, PhotoSize, filename=filename, attach=True, local_mode=True)
        super().__init__(
            InputMediaType.PHOTO,
            media,
            caption,
            caption_entities,
            parse_mode,
            api_kwargs=api_kwargs,
        )

        with self._unfrozen():
            self.has_spoiler: Optional[bool] = has_spoiler
            self.show_caption_above_media: Optional[bool] = show_caption_above_media


class InputMediaVideo(InputMedia):
    """Represents a video to be sent.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>`

    Note:
        *  When using a :class:`zalo_bot.Video` for the :attr:`media` attribute, it will take the
           width, height and duration from that video, unless otherwise specified with the optional
           arguments.
        *  :paramref:`thumbnail` will be ignored for small video files, for which ZaloBot can
            easily generate thumbnails. However, this behaviour is undocumented and might be
            changed by Zalo Bot.

      |removed_thumb_note|

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.Video`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.Video` object to send.


               Accept :obj:`bytes` as input.
        filename (:obj:`str`, optional): Custom file name for the video, when uploading a
            new file. Convenience parameter, useful e.g. when sending files generated by the
            :obj:`tempfile` module.

        caption (:obj:`str`, optional): Caption of the video to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters after
            entities parsing.
        parse_mode (:obj:`str`, optional): |parse_mode|
        caption_entities (Sequence[:class:`zalo_bot.MessageEntity`], optional): |caption_entities|


                |sequenceclassargs|

        width (:obj:`int`, optional): Video width.
        height (:obj:`int`, optional): Video height.
        duration (:obj:`int`, optional): Video duration in seconds.
        supports_streaming (:obj:`bool`, optional): Pass :obj:`True`, if the uploaded video is
            suitable for streaming.
        has_spoiler (:obj:`bool`, optional): Pass :obj:`True`, if the video needs to be covered
            with a spoiler animation.

        thumbnail (:term:`file object` | :obj:`bytes` | :class:`pathlib.Path` | :obj:`str`, \
                optional): |thumbdocstringnopath|

        show_caption_above_media (:obj:`bool`, optional): Pass |show_cap_above_med|


    Attributes:
        type (:obj:`str`): :tg-const:`zalo_bot.constants.InputMediaType.VIDEO`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Video file to send.
        caption (:obj:`str`): Optional. Caption of the video to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters
            after entities parsing.
        parse_mode (:obj:`str`): Optional. |parse_mode|
        caption_entities (Tuple[:class:`zalo_bot.MessageEntity`]): Optional. |captionentitiesattr|



                * |tupleclassattrs|
                * |alwaystuple|
        width (:obj:`int`): Optional. Video width.
        height (:obj:`int`): Optional. Video height.
        duration (:obj:`int`): Optional. Video duration in seconds.
        supports_streaming (:obj:`bool`): Optional. :obj:`True`, if the uploaded video is
            suitable for streaming.
        has_spoiler (:obj:`bool`): Optional. :obj:`True`, if the video is covered with a
            spoiler animation.

        thumbnail (:class:`zalo_bot.InputFile`): Optional. |thumbdocstringbase|

        show_caption_above_media (:obj:`bool`): Optional. |show_cap_above_med|

    """

    __slots__ = (
        "duration",
        "has_spoiler",
        "height",
        "show_caption_above_media",
        "supports_streaming",
        "thumbnail",
        "width",
    )

    def __init__(
        self,
        media: Union[FileInput, Video],
        caption: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[int] = None,
        supports_streaming: Optional[bool] = None,
        parse_mode: ODVInput[str] = DEFAULT_NONE,
        caption_entities: Optional[Sequence[MessageEntity]] = None,
        filename: Optional[str] = None,
        has_spoiler: Optional[bool] = None,
        thumbnail: Optional[FileInput] = None,
        show_caption_above_media: Optional[bool] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        if isinstance(media, Video):
            width = width if width is not None else media.width
            height = height if height is not None else media.height
            duration = duration if duration is not None else media.duration
            media = media.file_id
        else:
            # We use local_mode=True because we don't have access to the actual setting and want
            # things to work in local mode.
            media = parse_file_input(media, filename=filename, attach=True, local_mode=True)

        super().__init__(
            InputMediaType.VIDEO,
            media,
            caption,
            caption_entities,
            parse_mode,
            api_kwargs=api_kwargs,
        )
        with self._unfrozen():
            self.width: Optional[int] = width
            self.height: Optional[int] = height
            self.duration: Optional[int] = duration
            self.thumbnail: Optional[Union[str, InputFile]] = self._parse_thumbnail_input(
                thumbnail
            )
            self.supports_streaming: Optional[bool] = supports_streaming
            self.has_spoiler: Optional[bool] = has_spoiler
            self.show_caption_above_media: Optional[bool] = show_caption_above_media


class InputMediaAudio(InputMedia):
    """Represents an audio file to be treated as music to be sent.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>`

    Note:
        When using a :class:`zalo_bot.Audio` for the :attr:`media` attribute, it will take the
        duration, performer and title from that video, unless otherwise specified with the
        optional arguments.
      |removed_thumb_note|

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` | \
            :class:`pathlib.Path` | :class:`zalo_bot.Audio`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.Audio` object to send.


               Accept :obj:`bytes` as input.
        filename (:obj:`str`, optional): Custom file name for the audio, when uploading a
            new file. Convenience parameter, useful e.g. when sending files generated by the
            :obj:`tempfile` module.

        caption (:obj:`str`, optional): Caption of the audio to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters after
            entities parsing.
        parse_mode (:obj:`str`, optional): |parse_mode|
        caption_entities (Sequence[:class:`zalo_bot.MessageEntity`], optional): |caption_entities|


                |sequenceclassargs|

        duration (:obj:`int`, optional): Duration of the audio in seconds as defined by the sender.
        performer (:obj:`str`, optional): Performer of the audio as defined by the sender or by
            audio tags.
        title (:obj:`str`, optional): Title of the audio as defined by the sender or by audio tags.
        thumbnail (:term:`file object` | :obj:`bytes` | :class:`pathlib.Path` | :obj:`str`, \
                optional): |thumbdocstringnopath|


    Attributes:
        type (:obj:`str`): :tg-const:`zalo_bot.constants.InputMediaType.AUDIO`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): Audio file to send.
        caption (:obj:`str`): Optional. Caption of the audio to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters
            after entities parsing.
        parse_mode (:obj:`str`): Optional. |parse_mode|
        caption_entities (Tuple[:class:`zalo_bot.MessageEntity`]): Optional. |captionentitiesattr|



                * |tupleclassattrs|
                * |alwaystuple|
        duration (:obj:`int`): Optional. Duration of the audio in seconds.
        performer (:obj:`str`): Optional. Performer of the audio as defined by the sender or by
            audio tags.
        title (:obj:`str`): Optional. Title of the audio as defined by the sender or by audio tags.
        thumbnail (:class:`zalo_bot.InputFile`): Optional. |thumbdocstringbase|


    """

    __slots__ = ("duration", "performer", "thumbnail", "title")

    def __init__(
        self,
        media: Union[FileInput, Audio],
        caption: Optional[str] = None,
        parse_mode: ODVInput[str] = DEFAULT_NONE,
        duration: Optional[int] = None,
        performer: Optional[str] = None,
        title: Optional[str] = None,
        caption_entities: Optional[Sequence[MessageEntity]] = None,
        filename: Optional[str] = None,
        thumbnail: Optional[FileInput] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        if isinstance(media, Audio):
            duration = media.duration if duration is None else duration
            performer = media.performer if performer is None else performer
            title = media.title if title is None else title
            media = media.file_id
        else:
            # We use local_mode=True because we don't have access to the actual setting and want
            # things to work in local mode.
            media = parse_file_input(media, filename=filename, attach=True, local_mode=True)

        super().__init__(
            InputMediaType.AUDIO,
            media,
            caption,
            caption_entities,
            parse_mode,
            api_kwargs=api_kwargs,
        )
        with self._unfrozen():
            self.thumbnail: Optional[Union[str, InputFile]] = self._parse_thumbnail_input(
                thumbnail
            )
            self.duration: Optional[int] = duration
            self.title: Optional[str] = title
            self.performer: Optional[str] = performer


class InputMediaDocument(InputMedia):
    """Represents a general file to be sent.

    .. seealso:: :wiki:`Working with Files and Media <Working-with-Files-and-Media>`
      |removed_thumb_note|

    Args:
        media (:obj:`str` | :term:`file object` | :class:`~zalo_bot.InputFile` | :obj:`bytes` \
            | :class:`pathlib.Path` | :class:`zalo_bot.Document`): File to send. |fileinputnopath|
            Lastly you can pass an existing :class:`zalo_bot.Document` object to send.


               Accept :obj:`bytes` as input.
        filename (:obj:`str`, optional): Custom file name for the document, when uploading a
            new file. Convenience parameter, useful e.g. when sending files generated by the
            :obj:`tempfile` module.

        caption (:obj:`str`, optional): Caption of the document to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters after
            entities parsing.
        parse_mode (:obj:`str`, optional): |parse_mode|
        caption_entities (Sequence[:class:`zalo_bot.MessageEntity`], optional): |caption_entities|


                |sequenceclassargs|

        disable_content_type_detection (:obj:`bool`, optional): Disables automatic server-side
            content type detection for files uploaded using multipart/form-data. Always
            :obj:`True`, if the document is sent as part of an album.
        thumbnail (:term:`file object` | :obj:`bytes` | :class:`pathlib.Path` | :obj:`str`, \
                optional): |thumbdocstringnopath|


    Attributes:
        type (:obj:`str`): :tg-const:`zalo_bot.constants.InputMediaType.DOCUMENT`.
        media (:obj:`str` | :class:`zalo_bot.InputFile`): File to send.
        caption (:obj:`str`): Optional. Caption of the document to be sent,
            0-:tg-const:`zalo_bot.constants.MessageLimit.CAPTION_LENGTH` characters
            after entities parsing.
        parse_mode (:obj:`str`): Optional. |parse_mode|
        caption_entities (Tuple[:class:`zalo_bot.MessageEntity`]): Optional. |captionentitiesattr|



                * |tupleclassattrs|
                * |alwaystuple|
        disable_content_type_detection (:obj:`bool`): Optional. Disables automatic server-side
            content type detection for files uploaded using multipart/form-data. Always
            :obj:`True`, if the document is sent as part of an album.
        thumbnail (:class:`zalo_bot.InputFile`): Optional. |thumbdocstringbase|

    """

    __slots__ = ("disable_content_type_detection", "thumbnail")

    def __init__(
        self,
        media: Union[FileInput, Document],
        caption: Optional[str] = None,
        parse_mode: ODVInput[str] = DEFAULT_NONE,
        disable_content_type_detection: Optional[bool] = None,
        caption_entities: Optional[Sequence[MessageEntity]] = None,
        filename: Optional[str] = None,
        thumbnail: Optional[FileInput] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        # We use local_mode=True because we don't have access to the actual setting and want
        # things to work in local mode.
        media = parse_file_input(media, Document, filename=filename, attach=True, local_mode=True)

        super().__init__(
            InputMediaType.DOCUMENT,
            media,
            caption,
            caption_entities,
            parse_mode,
            api_kwargs=api_kwargs,
        )
        with self._unfrozen():
            self.thumbnail: Optional[Union[str, InputFile]] = self._parse_thumbnail_input(
                thumbnail
            )
            self.disable_content_type_detection: Optional[bool] = disable_content_type_detection
