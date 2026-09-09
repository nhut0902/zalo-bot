"""Zalo Bot error classes."""

__all__ = (
    "BadRequest",
    "ChatMigrated",
    "Conflict",
    "EndPointNotFound",
    "Forbidden",
    "InvalidToken",
    "NetworkError",
    "PassportDecryptionError",
    "RetryAfter",
    "ZaloError",
    "TimedOut",
)

from typing import Optional, Tuple, Union


def _lstrip_str(in_s: str, lstr: str) -> str:
    """Strip substring from left side of string.

    Args:
        in_s: Input string
        lstr: Substring to strip

    Returns:
        Stripped string
    """
    return in_s[len(lstr) :] if in_s.startswith(lstr) else in_s


class ZaloError(Exception):
    """Base class for Zalo Bot errors.

    Tip:
        Objects of this type can be serialized via Python's :mod:`pickle` module and pickled
        objects from one version of PTB are usually loadable in future versions. However, we can
        not guarantee that this compatibility will always be provided. At least a manual one-time
        conversion of the data may be needed on major updates of the library.

    .. seealso:: :wiki:`Exceptions, Warnings and Logging <Exceptions%2C-Warnings-and-Logging>`
    """

    __slots__ = ("message",)

    def __init__(self, message: str):
        super().__init__()

        msg = _lstrip_str(message, "Error: ")
        msg = _lstrip_str(msg, "[Error]: ")
        msg = _lstrip_str(msg, "Bad Request: ")
        if msg != message:
            # Capitalize API error messages
            msg = msg.capitalize()
        self.message: str = msg

    def __str__(self) -> str:
        """Get string representation of exception message.

        Returns:
           :obj:`str`
        """
        return self.message

    def __repr__(self) -> str:
        """Get unambiguous string representation of exception.

        Returns:
           :obj:`str`
        """
        return f"{self.__class__.__name__}('{self.message}')"

    def __reduce__(self) -> Tuple[type, Tuple[str]]:
        """Define serialization for pickle.

        .. seealso::
               :py:meth:`object.__reduce__`, :mod:`pickle`.

        Returns:
            :obj:`tuple`
        """
        return self.__class__, (self.message,)


class Forbidden(ZaloError):
    """Raised when bot lacks rights to perform requested action.

    Examples:
        :any:`Raw API Bot <examples.rawapibot>`

    .. versionchanged:: 20.0
        This class was previously named ``Unauthorized``.
    """

    __slots__ = ()


class InvalidToken(ZaloError):
    """Raised when token is invalid.

    Args:
        message: Additional information about exception.

            .. versionadded:: 20.0
    """

    __slots__ = ()

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__("Invalid token" if message is None else message)


class EndPointNotFound(ZaloError):
    """Raised when requested endpoint is not found. Only relevant for
    :meth:`zalo_bot.Bot.do_api_request`.

    .. versionadded:: 20.8
    """

    __slots__ = ()


class NetworkError(ZaloError):
    """Base class for networking error exceptions.

    Tip:
        This exception (and its subclasses) usually originates from the networking backend
        used by :class:`~zalo_bot.request.HTTPXRequest`, or a custom implementation of
        :class:`~zalo_bot.request.BaseRequest`. In this case, the original exception can be
        accessed via the ``__cause__``
        `attribute <https://docs.python.org/3/library/exceptions.html#exception-context>`_.

    Examples:
        :any:`Raw API Bot <examples.rawapibot>`

    .. seealso::
        :wiki:`Handling network errors <Handling-network-errors>`
    """

    __slots__ = ()


class BadRequest(NetworkError):
    """Raised when Zalo Bot could not process the request correctly."""

    __slots__ = ()


class TimedOut(NetworkError):
    """Raised when request took too long to finish.

    .. seealso::
        :wiki:`Handling network errors <Handling-network-errors>`

    Args:
        message: Additional information about exception.

            .. versionadded:: 20.0
    """

    __slots__ = ()

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or "Timed out")


class ChatMigrated(ZaloError):
    """Raised when group chat migrated to supergroup with new chat id.

    .. seealso::
        :wiki:`Storing Bot, User and Chat Related Data <Storing-bot%2C-user-and-chat-related-data>`

    Args:
        new_chat_id: The new chat id of the group.

    Attributes:
        new_chat_id: The new chat id of the group.
    """

    __slots__ = ("new_chat_id",)

    def __init__(self, new_chat_id: int):
        super().__init__(f"Group migrated to supergroup. New chat id: {new_chat_id}")
        self.new_chat_id: int = new_chat_id

    def __reduce__(self) -> Tuple[type, Tuple[int]]:  # type: ignore[override]
        return self.__class__, (self.new_chat_id,)


class RetryAfter(ZaloError):
    """Raised when flood limits were exceeded.

    Args:
        retry_after: Time in seconds after which bot can retry request.

    Attributes:
        retry_after: Time in seconds after which bot can retry request.
    """

    __slots__ = ("retry_after",)

    def __init__(self, retry_after: int):
        super().__init__(f"Flood control exceeded. Retry in {retry_after} seconds")
        self.retry_after: int = retry_after

    def __reduce__(self) -> Tuple[type, Tuple[float]]:  # type: ignore[override]
        return self.__class__, (self.retry_after,)


class Conflict(ZaloError):
    """Raised when long poll or webhook conflicts with another one."""

    __slots__ = ()

    def __reduce__(self) -> Tuple[type, Tuple[str]]:
        return self.__class__, (self.message,)


class PassportDecryptionError(ZaloError):
    """Something went wrong with decryption."""

    __slots__ = ("_msg",)

    def __init__(self, message: Union[str, Exception]):
        super().__init__(f"PassportDecryptionError: {message}")
        self._msg = str(message)

    def __reduce__(self) -> Tuple[type, Tuple[str]]:
        return self.__class__, (self._msg,)
