"""DefaultValue class for immutable default arguments.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""
from typing import Generic, TypeVar, Union, overload

DVType = TypeVar("DVType", bound=object)  # pylint: disable=invalid-name
OT = TypeVar("OT", bound=object)


class DefaultValue(Generic[DVType]):
    """Wrapper for immutable default arguments to check if default was set explicitly.

    Usage::

        default_one = DefaultValue(1)
        def f(arg=default_one):
            if arg is default_one:
                print('`arg` is the default')
                arg = arg.value
            else:
                print('`arg` was set explicitly')
            print(f'`arg` = {str(arg)}')

    This yields::

        >>> f()
        `arg` is the default
        `arg` = 1
        >>> f(1)
        `arg` was set explicitly
        `arg` = 1
        >>> f(2)
        `arg` was set explicitly
        `arg` = 2

    Also allows truthiness evaluation::

        default = DefaultValue(value)
        if default:
            ...

    is equivalent to::

        default = DefaultValue(value)
        if value:
            ...

    Args:
        value: The default argument value
    Attributes:
        value: The default argument value
    """

    __slots__ = ("value",)

    def __init__(self, value: DVType):
        self.value: DVType = value

    def __bool__(self) -> bool:
        return bool(self.value)

    # For debugging readability
    def __str__(self) -> str:
        return f"DefaultValue({self.value})"

    # For nice doc rendering
    def __repr__(self) -> str:
        return repr(self.value)

    @overload
    @staticmethod
    def get_value(obj: "DefaultValue[OT]") -> OT: ...

    @overload
    @staticmethod
    def get_value(obj: OT) -> OT: ...

    @staticmethod
    def get_value(obj: Union[OT, "DefaultValue[OT]"]) -> OT:
        """Shortcut for::

            return obj.value if isinstance(obj, DefaultValue) else obj

        Args:
            obj: The object to process

        Returns:
            The value
        """
        return obj.value if isinstance(obj, DefaultValue) else obj


DEFAULT_NONE: DefaultValue[None] = DefaultValue(None)
"""Default None"""

DEFAULT_FALSE: DefaultValue[bool] = DefaultValue(False)
"""Default False"""

DEFAULT_TRUE: DefaultValue[bool] = DefaultValue(True)
"""Default True"""


DEFAULT_20: DefaultValue[int] = DefaultValue(20)
"""Default 20"""

DEFAULT_IP: DefaultValue[str] = DefaultValue("127.0.0.1")
"""Default 127.0.0.1"""

DEFAULT_80: DefaultValue[int] = DefaultValue(80)
"""Default 80"""
