"""Networking backend classes for zalo-bot."""

from ._base_request import BaseRequest
from ._httpx_request import HTTPXRequest
from ._request_data import RequestData

__all__ = ("BaseRequest", "HTTPXRequest", "RequestData")