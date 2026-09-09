"""Helper functions for file handling.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""

from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional, Tuple, Type, TypeVar, Union, cast, overload

from zalo_bot._utils.types import FileInput, FilePathInput

if TYPE_CHECKING:
    from zalo_bot import InputFile, ZaloObject

_T = TypeVar("_T", bound=Union[bytes, "InputFile", str, Path, None])


@overload
def load_file(obj: IO[bytes]) -> Tuple[Optional[str], bytes]: ...


@overload
def load_file(obj: _T) -> Tuple[None, _T]: ...


def load_file(
    obj: Optional[FileInput],
) -> Tuple[Optional[str], Union[bytes, "InputFile", str, Path, None]]:
    """Read file handle data and name, or return input unchanged."""
    if obj is None:
        return None, None

    try:
        contents = obj.read()  # type: ignore[union-attr]
    except AttributeError:
        return None, cast(Union[bytes, "InputFile", str, Path], obj)

    filename = guess_file_name(obj)

    return filename, contents


def guess_file_name(obj: FileInput) -> Optional[str]:
    """Get filename from file handle, or return input unchanged."""
    if hasattr(obj, "name") and not isinstance(obj.name, int):
        return Path(obj.name).name

    return None


def is_local_file(obj: Optional[FilePathInput]) -> bool:
    """Check if string is a local file.

    Args:
        obj: The string to check.
    """
    if obj is None:
        return False

    path = Path(obj)
    try:
        return path.is_file()
    except Exception:
        return False


def parse_file_input(  # pylint: disable=too-many-return-statements
    file_input: Union[FileInput, "ZaloObject"],
    tg_type: Optional[Type["ZaloObject"]] = None,
    filename: Optional[str] = None,
    attach: bool = False,
    local_mode: bool = False,
) -> Union[str, "InputFile", Any]:
    """Parse input for sending files.

    * String input: if absolute path of local file:
        * local_mode=True: add file:// prefix
        * local_mode=False: load as binary data and build InputFile
    * Path objects: treated same as strings
    * IO/bytes input: return InputFile
    * If tg_type specified and input is that type: return file_id attribute

    Args:
        file_input: The input to parse.
        tg_type: Zalo Bot media type the input can be.
        filename: Filename for InputFile.
        attach: Use attach:// URI for multipart data.
        local_mode: Bot running in --local mode.

    Returns:
        Parsed input or untouched file_input.
    """
    # Import here to avoid cyclic import errors
    from zalo_bot import InputFile  # pylint: disable=import-outside-toplevel

    if isinstance(file_input, str) and file_input.startswith("file://"):
        if not local_mode:
            raise ValueError("Specified file input is a file URI, but local mode is not enabled.")
        return file_input
    if isinstance(file_input, (str, Path)):
        if is_local_file(file_input):
            path = Path(file_input)
            if local_mode:
                return path.absolute().as_uri()
            return InputFile(path.open(mode="rb"), filename=filename, attach=attach)

        return file_input
    if isinstance(file_input, bytes):
        return InputFile(file_input, filename=filename, attach=attach)
    if hasattr(file_input, "read"):
        return InputFile(cast(IO, file_input), filename=filename, attach=attach)
    if tg_type and isinstance(file_input, tg_type):
        return file_input.file_id  # type: ignore[attr-defined]
    return file_input
