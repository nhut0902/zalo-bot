"""Abstract class for making POST and GET requests."""
import abc
import json
from http import HTTPStatus
from types import TracebackType
from typing import AsyncContextManager, Final, List, Optional, Tuple, Type, TypeVar, Union, final

from zalo_bot._utils.default_value import DEFAULT_NONE as _DEFAULT_NONE
from zalo_bot._utils.default_value import DefaultValue
from zalo_bot._utils.logging import get_logger
from zalo_bot._utils.strings import TextEncoding
from zalo_bot._utils.types import JSONDict, ODVInput
from zalo_bot._utils.warnings import warn
from zalo_bot._version import __version__ as ptb_ver
from zalo_bot.error import (
    BadRequest,
    ChatMigrated,
    Conflict,
    Forbidden,
    InvalidToken,
    NetworkError,
    RetryAfter,
    ZaloError,
)
from zalo_bot.request._request_data import RequestData
from zalo_bot.warnings import PTBDeprecationWarning

RT = TypeVar("RT", bound="BaseRequest")

_LOGGER = get_logger(__name__, class_name="BaseRequest")


class BaseRequest(
    AsyncContextManager["BaseRequest"],
    abc.ABC,
):
    """Abstract interface for making requests to the Bot API.

    Can be implemented via different asyncio HTTP libraries. Must implement all abstract methods.

    Instances can be used as asyncio context managers:

    .. code:: python

        async with request_object:
            # code

    is roughly equivalent to:

    .. code:: python

        try:
            await request_object.initialize()
            # code
        finally:
            await request_object.shutdown()

    Tip:
        JSON encoding/decoding uses standard library :mod:`json` by default.
        Override :meth:`parse_json_payload` for custom logic.

    .. seealso:: :wiki:`Architecture Overview <Architecture>`,
        :wiki:`Builder Pattern <Builder-Pattern>`

    .. versionadded:: 20.0
    """

    __slots__ = ()

    USER_AGENT: Final[str] = f"zalo-bot v{ptb_ver}"
    """User agent for Bot API requests."""
    DEFAULT_NONE: Final[DefaultValue[None]] = _DEFAULT_NONE
    """Special object indicating argument was not explicitly passed.

    Example:
        When calling ``request.post(url)``, use default timeouts.
        When calling ``request.post(url, connect_timeout=5, read_timeout=None)``,
        use ``5`` for connect timeout and :obj:`None` for read timeout.

        Use ``if parameter is (not) BaseRequest.DEFAULT_NONE:`` to check.
    """

    async def __aenter__(self: RT) -> RT:
        """Initialize the Request.

        Returns:
            The initialized Request instance.

        Raises:
            :exc:`Exception`: If initialization fails, shutdown is called.
        """
        try:
            await self.initialize()
        except Exception:
            await self.shutdown()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Shut down the Request."""
        # Don't return True so exceptions are not suppressed
        # https://docs.python.org/3/reference/datamodel.html?#object.__aexit__
        await self.shutdown()

    @property
    def read_timeout(self) -> Optional[float]:
        """Default read timeout in seconds.

        Used when :paramref:`post.read_timeout` is not passed/equal to :attr:`DEFAULT_NONE`.

        Warning:
            For now this property does not need to be implemented by subclasses and will raise
            :exc:`NotImplementedError` if accessed without being overridden. However, in future
            versions, this property will be abstract and must be implemented by subclasses.

        Returns:
            :obj:`float` | :obj:`None`: The read timeout in seconds.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initialize resources used by this class. Must be implemented by a subclass."""

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """Stop & clear resources used by this class. Must be implemented by a subclass."""

    @final
    async def post(
        self,
        url: str,
        request_data: Optional[RequestData] = None,
        read_timeout: ODVInput[float] = DEFAULT_NONE,
        write_timeout: ODVInput[float] = DEFAULT_NONE,
        connect_timeout: ODVInput[float] = DEFAULT_NONE,
        pool_timeout: ODVInput[float] = DEFAULT_NONE,
    ) -> Union[JSONDict, List[JSONDict], bool]:
        """Make request to Bot API, handle return code and parse answer.

        Warning:
            This method will be called by :class:`zalo_bot.Bot` methods and should *not* be
            called manually.

        Args:
            url: The URL to request.
            request_data: Object containing parameters and files to upload.
            read_timeout: Maximum time to wait for response from Zalo Bot server.
            write_timeout: Maximum time to wait for write operation to complete.
            connect_timeout: Maximum time to wait for connection attempt to succeed.
            pool_timeout: Maximum time to wait for connection to become available.

        Returns:
          The JSON response of the Bot API.
        """
        result = await self._request_wrapper(
            url=url,
            method="POST",
            request_data=request_data,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            connect_timeout=connect_timeout,
            pool_timeout=pool_timeout,
        )
        json_data = self.parse_json_payload(result)
        return json_data.get("result")

    @final
    async def retrieve(
        self,
        url: str,
        read_timeout: ODVInput[float] = DEFAULT_NONE,
        write_timeout: ODVInput[float] = DEFAULT_NONE,
        connect_timeout: ODVInput[float] = DEFAULT_NONE,
        pool_timeout: ODVInput[float] = DEFAULT_NONE,
    ) -> bytes:
        """Retrieve the contents of a file by its URL.

        Warning:
            This method will be called by the methods of :class:`zalo_bot.Bot` and should *not* be
            called manually.

        Args:
            url (:obj:`str`): The web location we want to retrieve.
            read_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a response from Zalo Bot's server instead
                of the time specified during creating of this object. Defaults to
                :attr:`DEFAULT_NONE`.
            write_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a write operation to complete (in terms of
                a network socket; i.e. POSTing a request or uploading a file) instead of the time
                specified during creating of this object. Defaults to :attr:`DEFAULT_NONE`.
            connect_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the
                maximum amount of time (in seconds) to wait for a connection attempt to a server
                to succeed instead of the time specified during creating of this object. Defaults
                to :attr:`DEFAULT_NONE`.
            pool_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a connection to become available instead
                of the time specified during creating of this object. Defaults to
                :attr:`DEFAULT_NONE`.

        Returns:
            :obj:`bytes`: The files contents.

        """
        return await self._request_wrapper(
            url=url,
            method="GET",
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            connect_timeout=connect_timeout,
            pool_timeout=pool_timeout,
        )

    async def _request_wrapper(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        read_timeout: ODVInput[float] = DEFAULT_NONE,
        write_timeout: ODVInput[float] = DEFAULT_NONE,
        connect_timeout: ODVInput[float] = DEFAULT_NONE,
        pool_timeout: ODVInput[float] = DEFAULT_NONE,
    ) -> bytes:
        """Wraps the real implementation request method.

        Performs the following tasks:
        * Handle the various HTTP response codes.
        * Parse the Zalo Bot server response.

        Args:
            url (:obj:`str`): The URL to request.
            method (:obj:`str`): HTTP method (i.e. 'POST', 'GET', etc.).
            request_data (:class:`zalo_bot.request.RequestData`, optional): An object containing
                information about parameters and files to upload for the request.
            read_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a response from Zalo Bot's server instead
                of the time specified during creating of this object. Defaults to
                :attr:`DEFAULT_NONE`.
            write_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a write operation to complete (in terms of
                a network socket; i.e. POSTing a request or uploading a file) instead of the time
                specified during creating of this object. Defaults to :attr:`DEFAULT_NONE`.
            connect_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the
                maximum amount of time (in seconds) to wait for a connection attempt to a server
                to succeed instead of the time specified during creating of this object. Defaults
                to :attr:`DEFAULT_NONE`.
            pool_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a connection to become available instead
                of the time specified during creating of this object. Defaults to
                :attr:`DEFAULT_NONE`.

        Returns:
            bytes: The payload part of the HTTP server response.

        Raises:
            ZaloError

        """
        # Import needs to be here since HTTPXRequest is a subclass of BaseRequest
        from zalo_bot.request import HTTPXRequest  # pylint: disable=import-outside-toplevel

        # 20 is the documented default value for all the media related bot methods and custom
        # implementations of BaseRequest may explicitly rely on that. Hence, we follow the
        # standard deprecation policy and deprecate starting with version 20.7.
        # For our own implementation HTTPXRequest, we can handle that ourselves, so we skip the
        # warning in that case.
        has_files = request_data and request_data.multipart_data
        if (
            has_files
            and not isinstance(self, HTTPXRequest)
            and isinstance(write_timeout, DefaultValue)
        ):
            warn(
                PTBDeprecationWarning(
                    "20.7",
                    f"The `write_timeout` parameter passed to {self.__class__.__name__}.do_request"
                    " will default to `BaseRequest.DEFAULT_NONE` instead of 20 in future versions "
                    "for *all* methods of the `Bot` class, including methods sending media.",
                ),
                stacklevel=3,
            )
            write_timeout = 20

        try:
            code, payload = await self.do_request(
                url=url,
                method=method,
                request_data=request_data,
                read_timeout=read_timeout,
                write_timeout=write_timeout,
                connect_timeout=connect_timeout,
                pool_timeout=pool_timeout,
            )
        except ZaloError:
            raise
        except Exception as exc:
            raise NetworkError(f"Unknown error in HTTP implementation: {exc!r}") from exc

        if HTTPStatus.OK <= code <= 299:
            # 200-299 range are HTTP success statuses
            return payload

        response_data = self.parse_json_payload(payload)

        description = response_data.get("description")
        message = description if description else "Unknown HTTPError"

        parameters = response_data.get("parameters")
        if parameters:
            migrate_to_chat_id = parameters.get("migrate_to_chat_id")
            if migrate_to_chat_id:
                raise ChatMigrated(migrate_to_chat_id)
            retry_after = parameters.get("retry_after")
            if retry_after:
                raise RetryAfter(retry_after)

            message += f"\nThe server response contained unknown parameters: {parameters}"

        if code == HTTPStatus.FORBIDDEN:  # 403
            raise Forbidden(message)
        if code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNAUTHORIZED):  # 404 and 401
            # TG returns 404 Not found for
            #   1) malformed tokens
            #   2) correct tokens but non-existing method, e.g. api.tg.org/botTOKEN/unkonwnMethod
            # 2) is relevant only for Bot.do_api_request, where we have special handing for it.
            # TG returns 401 Unauthorized for correctly formatted tokens that are not valid
            raise InvalidToken(message)
        if code == HTTPStatus.BAD_REQUEST:  # 400
            raise BadRequest(message)
        if code == HTTPStatus.CONFLICT:  # 409
            raise Conflict(message)
        if code == HTTPStatus.BAD_GATEWAY:  # 502
            raise NetworkError(description or "Bad Gateway")
        raise NetworkError(f"{message} ({code})")

    @staticmethod
    def parse_json_payload(payload: bytes) -> JSONDict:
        """Parse the JSON returned from Zalo Bot.

        Tip:
            By default, this method uses the standard library's :func:`json.loads` and
            ``errors="replace"`` in :meth:`bytes.decode`.
            You can override it to customize either of these behaviors.

        Args:
            payload (:obj:`bytes`): The UTF-8 encoded JSON payload as returned by Zalo Bot.

        Returns:
            dict: A JSON parsed as Python dict with results.

        Raises:
            ZaloError: If loading the JSON data failed
        """
        decoded_s = payload.decode(TextEncoding.UTF_8, "replace")
        try:
            return json.loads(decoded_s)
        except ValueError as exc:
            _LOGGER.exception('Can not load invalid JSON data: "%s"', decoded_s)
            raise ZaloError("Invalid server response") from exc

    @abc.abstractmethod
    async def do_request(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        read_timeout: ODVInput[float] = DEFAULT_NONE,
        write_timeout: ODVInput[float] = DEFAULT_NONE,
        connect_timeout: ODVInput[float] = DEFAULT_NONE,
        pool_timeout: ODVInput[float] = DEFAULT_NONE,
    ) -> Tuple[int, bytes]:
        """Makes a request to the Bot API. Must be implemented by a subclass.

        Warning:
            This method will be called by :meth:`post` and :meth:`retrieve`. It should *not* be
            called manually.

        Args:
            url (:obj:`str`): The URL to request.
            method (:obj:`str`): HTTP method (i.e. ``'POST'``, ``'GET'``, etc.).
            request_data (:class:`zalo_bot.request.RequestData`, optional): An object containing
                information about parameters and files to upload for the request.
            read_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a response from Zalo Bot's server instead
                of the time specified during creating of this object. Defaults to
                :attr:`DEFAULT_NONE`.
            write_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a write operation to complete (in terms of
                a network socket; i.e. POSTing a request or uploading a file) instead of the time
                specified during creating of this object. Defaults to :attr:`DEFAULT_NONE`.
            connect_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the
                maximum amount of time (in seconds) to wait for a connection attempt to a server
                to succeed instead of the time specified during creating of this object. Defaults
                to :attr:`DEFAULT_NONE`.
            pool_timeout (:obj:`float` | :obj:`None`, optional): If passed, specifies the maximum
                amount of time (in seconds) to wait for a connection to become available instead
                of the time specified during creating of this object. Defaults to
                :attr:`DEFAULT_NONE`.

        Returns:
            Tuple[:obj:`int`, :obj:`bytes`]: The HTTP return code & the payload part of the server
            response.
        """
