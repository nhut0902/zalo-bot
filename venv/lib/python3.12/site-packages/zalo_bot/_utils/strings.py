"""This module contains a helper functions related to string manipulation.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""

from zalo_bot._utils.enum import StringEnum

# pylint: disable=invalid-enum-extension,invalid-slots


class TextEncoding(StringEnum):
    """This enum contains encoding schemes for text."""

    __slots__ = ()

    UTF_8 = "utf-8"
    UTF_16_LE = "utf-16-le"


def to_camel_case(snake_str: str) -> str:
    """Converts a snake_case string to camelCase.

    Args:
        snake_str (:obj:`str`): The string to convert.

    Returns:
        :obj:`str`: The converted string.
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
