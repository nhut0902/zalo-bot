"""This module contains helper functions related to enums.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""
import enum as _enum
import sys
from typing import Type, TypeVar, Union

_A = TypeVar("_A")
_B = TypeVar("_B")
_Enum = TypeVar("_Enum", bound=_enum.Enum)


def get_member(enum_cls: Type[_Enum], value: _A, default: _B) -> Union[_Enum, _A, _B]:
    """Tries to call ``enum_cls(value)`` to convert the value into an enumeration member.
    If that fails, the ``default`` is returned.
    """
    try:
        return enum_cls(value)
    except ValueError:
        return default


# Python 3.11 and above has a different output for mixin classes for IntEnum, StrEnum and IntFlag
# see https://docs.python.org/3.11/library/enum.html#notes. We want e.g. str(StrEnumTest.FOO) to
# return "foo" instead of "StrEnumTest.FOO", which is not the case < py3.11
class StringEnum(str, _enum.Enum):
    """Helper class for string enums where ``str(member)`` prints the value, but ``repr(member)``
    gives ``EnumName.MEMBER_NAME``.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name}>"

    def __str__(self) -> str:
        return str.__str__(self)


# Apply the __repr__ modification and __str__ fix to IntEnum
class IntEnum(_enum.IntEnum):  # pylint: disable=invalid-slots
    """Helper class for int enums where ``str(member)`` prints the value, but ``repr(member)``
    gives ``EnumName.MEMBER_NAME``.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name}>"

    if sys.version_info < (3, 11):

        def __str__(self) -> str:
            return str(self.value)
