from typing import Optional
from zalo_bot._utils.types import JSONDict
from zalo_bot._zalo_object import ZaloObject


class Webhook(ZaloObject):
    """
    Webhook class for handling Zalo Bot webhooks.
    """
    
    __slots__ = ("url", "updated_at")

    def __init__(
        self,
        url: str,
        updated_at: str,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        self.url: str = url
        self.updated_at: Optional[str] = updated_at

        self._freeze()