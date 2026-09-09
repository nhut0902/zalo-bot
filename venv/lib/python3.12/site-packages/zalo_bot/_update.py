from typing import Optional, TYPE_CHECKING
from zalo_bot._zalo_object import ZaloObject
from zalo_bot._utils.types import JSONDict
from zalo_bot._message import Message

if TYPE_CHECKING:
    from zalo_bot import Bot, User

class Update(ZaloObject):
    __slots__ = ("message", "_effective_user")

    def __init__(
        self,
        message: Optional["Message"] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        self.message: Optional["Message"] = message
        self._effective_user: Optional["User"] = None

    @property
    def effective_user(self) -> Optional["User"]:
        if self._effective_user:
            return self._effective_user
        if self.message:
            self._effective_user = self.message.from_user
        return self._effective_user

    @classmethod
    def de_json(cls, data: Optional[JSONDict], bot: Optional["Bot"] = None) -> Optional["Update"]:
        data = cls._parse_data(data)
        if not data:
            return None
        data["message"] = Message.de_json(data.get("message"), bot)
        update = cls(
            message=data.get("message"),
            api_kwargs=data,
        )
        update.set_bot(bot)
        return update
