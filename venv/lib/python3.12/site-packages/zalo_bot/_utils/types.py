"""Custom typing aliases for internal library use.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""

from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Collection,
    Dict,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from zalo_bot import (
        InputFile,
    )
    from zalo_bot._utils.default_value import DefaultValue

FileLike = Union[IO[bytes], "InputFile"]
"""Bytes-stream or InputFile."""

FilePathInput = Union[str, Path]
"""Filepath as string or Path object."""

FileInput = Union[FilePathInput, FileLike, bytes, str]
"""Valid file input: file id, file-like object, local path, or file contents."""

JSONDict = Dict[str, Any]
"""Dictionary for Zalo Bot API requests/responses."""

DVValueType = TypeVar("DVValueType")  # pylint: disable=invalid-name
DVType = Union[DVValueType, "DefaultValue[DVValueType]"]
"""Type that can be either `type` or `DefaultValue[type]`."""
ODVInput = Optional[
    Union["DefaultValue[DVValueType]", DVValueType, "DefaultValue[None]"]
]
"""Optional parameter type with defaults."""
DVInput = Union["DefaultValue[DVValueType]", DVValueType, "DefaultValue[None]"]
"""Parameter type with defaults."""

RT = TypeVar("RT")
SCT = Union[RT, Collection[RT]]  # pylint: disable=invalid-name
"""Single instance or collection of instances."""

FieldTuple = Tuple[str, Union[bytes, IO[bytes]], str]
"""Return type of InputFile.field_tuple."""
UploadFileDict = Dict[str, FieldTuple]
"""File data for API upload."""

HTTPVersion = Literal["1.1", "2.0", "2"]
"""Allowed HTTP versions."""

CorrectOptionID = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

MarkdownVersion = Literal[1, 2]

SocketOpt = Union[
    Tuple[int, int, int],
    Tuple[int, int, Union[bytes, bytearray]],
    Tuple[int, int, None, int],
]
