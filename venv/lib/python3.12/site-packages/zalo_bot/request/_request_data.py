"""This module contains a class that holds the parameters of a request to the Bot API."""
import json
from typing import Any, Dict, List, Optional, Union, final
from urllib.parse import urlencode

from zalo_bot._utils.strings import TextEncoding
from zalo_bot._utils.types import UploadFileDict
from zalo_bot.request._request_parameter import RequestParameter


@final
class RequestData:
    """Instances of this class collect the data needed for one request to the Bot API, including
    all parameters and files to be sent along with the request.

    Warning:
        How exactly instances of this are created should be considered an implementation detail
        and not part of PTBs public API. Users should exclusively rely on the documented
        attributes, properties and methods.

    Attributes:
        contains_files (:obj:`bool`): Whether this object contains files to be uploaded via
            ``multipart/form-data``.
    """

    __slots__ = ("_parameters", "contains_files")

    def __init__(self, parameters: Optional[List[RequestParameter]] = None):
        self._parameters: List[RequestParameter] = parameters or []
        self.contains_files: bool = any(param.input_files for param in self._parameters)

    @property
    def parameters(self) -> Dict[str, Union[str, int, List[Any], Dict[Any, Any]]]:
        """Gives the parameters as mapping of parameter name to the parameter value, which can be
        a single object of type :obj:`int`, :obj:`float`, :obj:`str` or :obj:`bool` or any
        (possibly nested) composition of lists, tuples and dictionaries, where each entry, key
        and value is of one of the mentioned types.

        Returns:
            Dict[:obj:`str`, Union[:obj:`str`, :obj:`int`, List[any], Dict[any, any]]]
        """
        return {
            param.name: param.value  # type: ignore[misc]
            for param in self._parameters
            if param.value is not None
        }

    @property
    def json_parameters(self) -> Dict[str, str]:
        """Gives the parameters as mapping of parameter name to the respective JSON encoded
        value.

        Tip:
            By default, this property uses the standard library's :func:`json.dumps`.
            To use a custom library for JSON encoding, you can directly encode the keys of
            :attr:`parameters` - note that string valued keys should not be JSON encoded.

        Returns:
            Dict[:obj:`str`, :obj:`str`]
        """
        return {
            param.name: param.json_value
            for param in self._parameters
            if param.json_value is not None
        }

    def url_encoded_parameters(self, encode_kwargs: Optional[Dict[str, Any]] = None) -> str:
        """Encodes the parameters with :func:`urllib.parse.urlencode`.

        Args:
            encode_kwargs (Dict[:obj:`str`, any], optional): Additional keyword arguments to pass
                along to :func:`urllib.parse.urlencode`.

        Returns:
            :obj:`str`
        """
        if encode_kwargs:
            return urlencode(self.json_parameters, **encode_kwargs)
        return urlencode(self.json_parameters)

    def parametrized_url(self, url: str, encode_kwargs: Optional[Dict[str, Any]] = None) -> str:
        """Shortcut for attaching the return value of :meth:`url_encoded_parameters` to the
        :paramref:`url`.

        Args:
            url (:obj:`str`): The URL the parameters will be attached to.
            encode_kwargs (Dict[:obj:`str`, any], optional): Additional keyword arguments to pass
                along to :func:`urllib.parse.urlencode`.

        Returns:
            :obj:`str`
        """
        url_parameters = self.url_encoded_parameters(encode_kwargs=encode_kwargs)
        return f"{url}?{url_parameters}"

    @property
    def json_payload(self) -> bytes:
        """The :attr:`parameters` as UTF-8 encoded JSON payload.

        Tip:
            By default, this property uses the standard library's :func:`json.dumps`.
            To use a custom library for JSON encoding, you can directly encode the keys of
            :attr:`parameters` - note that string valued keys should not be JSON encoded.

        Returns:
            :obj:`bytes`
        """
        return json.dumps(self.json_parameters).encode(TextEncoding.UTF_8)

    @property
    def multipart_data(self) -> UploadFileDict:
        """Gives the files contained in this object as mapping of part name to encoded content."""
        multipart_data: UploadFileDict = {}
        for param in self._parameters:
            m_data = param.multipart_data
            if m_data:
                multipart_data.update(m_data)
        return multipart_data
