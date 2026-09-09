"""This module contains a class that describes a single parameter of a request to the Bot API."""
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple, final

from zalo_bot._files.input_file import InputFile
from zalo_bot._files.input_media import InputMedia, InputPaidMedia
from zalo_bot._files.input_sticker import InputSticker
from zalo_bot._zalo_object import ZaloObject
from zalo_bot._utils.datetime import to_timestamp
from zalo_bot._utils.enum import StringEnum
from zalo_bot._utils.types import UploadFileDict


@final
@dataclass(repr=True, eq=False, order=False, frozen=True)
class RequestParameter:
    """Instances of this class represent a single parameter to be sent along with a request to
    the Bot API.

    Warning:
        This class intended is to be used internally by the library and *not* by the user. Changes
        to this class are not considered breaking changes and may not be documented in the
        changelog.

    Args:
        name (:obj:`str`): The name of the parameter.
        value (:obj:`object` | :obj:`None`): The value of the parameter. Must be JSON-dumpable.
        input_files (List[:class:`zalo_bot.InputFile`], optional): A list of files that should be
            uploaded along with this parameter.

    Attributes:
        name (:obj:`str`): The name of the parameter.
        value (:obj:`object` | :obj:`None`): The value of the parameter.
        input_files (List[:class:`zalo_bot.InputFile` | :obj:`None`): A list of files that should
            be uploaded along with this parameter.
    """

    __slots__ = ("input_files", "name", "value")

    name: str
    value: object
    input_files: Optional[List[InputFile]]

    @property
    def json_value(self) -> Optional[str]:
        """The JSON dumped :attr:`value` or :obj:`None` if :attr:`value` is :obj:`None`.
        The latter can currently only happen if :attr:`input_files` has exactly one element that
        must not be uploaded via an attach:// URI.
        """
        if isinstance(self.value, str):
            return self.value
        if self.value is None:
            return None
        return json.dumps(self.value)

    @property
    def multipart_data(self) -> Optional[UploadFileDict]:
        """A dict with the file data to upload, if any.

        .. versionchanged:: 21.5
            Content may now be a file handle.
        """
        if not self.input_files:
            return None
        return {
            (input_file.attach_name or self.name): input_file.field_tuple
            for input_file in self.input_files
        }

    @staticmethod
    def _value_and_input_files_from_input(  # pylint: disable=too-many-return-statements
        value: object,
    ) -> Tuple[object, List[InputFile]]:
        """Converts `value` into something that we can json-dump. Returns two values:
        1. the JSON-dumpable value. May be `None` in case the value is an InputFile which must
           not be uploaded via an attach:// URI
        2. A list of InputFiles that should be uploaded for this value

        This method only does some special casing for our own helper class StringEnum, but not
        for general enums. This is because:
        * tg.constants currently only uses IntEnum as second enum type and json dumping that
          is no problem
        * if a user passes a custom enum, it's unlikely that we can actually properly handle it
          even with some special casing.
        """
        if isinstance(value, datetime):
            return to_timestamp(value), []
        if isinstance(value, StringEnum):
            return value.value, []
        if isinstance(value, InputFile):
            if value.attach_uri:
                return value.attach_uri, [value]
            return None, [value]

        if isinstance(value, (InputMedia, InputPaidMedia)) and isinstance(value.media, InputFile):
            # We call to_dict and change the returned dict instead of overriding
            # value.media in case the same value is reused for another request
            data = value.to_dict()
            if value.media.attach_uri:
                data["media"] = value.media.attach_uri
            else:
                data.pop("media", None)

            thumbnail = data.get("thumbnail", None)
            if isinstance(thumbnail, InputFile):
                if thumbnail.attach_uri:
                    data["thumbnail"] = thumbnail.attach_uri
                else:
                    data.pop("thumbnail", None)
                return data, [value.media, thumbnail]

            return data, [value.media]
        if isinstance(value, InputSticker) and isinstance(value.sticker, InputFile):
            # We call to_dict and change the returned dict instead of overriding
            # value.sticker in case the same value is reused for another request
            data = value.to_dict()
            data["sticker"] = value.sticker.attach_uri
            return data, [value.sticker]

        if isinstance(value, ZaloObject):
            # Needs to be last, because InputMedia is a subclass of ZaloObject
            return value.to_dict(), []
        return value, []

    @classmethod
    def from_input(cls, key: str, value: object) -> "RequestParameter":
        """Builds an instance of this class for a given key-value pair that represents the raw
        input as passed along from a method of :class:`zalo_bot.Bot`.
        """
        if not isinstance(value, (str, bytes)) and isinstance(value, Sequence):
            param_values = []
            input_files = []
            for obj in value:
                param_value, input_file = cls._value_and_input_files_from_input(obj)
                if param_value is not None:
                    param_values.append(param_value)
                input_files.extend(input_file)
            return RequestParameter(
                name=key, value=param_values, input_files=input_files if input_files else None
            )

        param_value, input_files = cls._value_and_input_files_from_input(value)
        return RequestParameter(
            name=key, value=param_value, input_files=input_files if input_files else None
        )
