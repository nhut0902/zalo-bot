from zalo_bot._zalo_object import ZaloObject
from zalo_bot._utils.types import JSONDict

class Chat(ZaloObject):
    __slots__ = ("id", "type")

    def __init__(self, id: str, chat_type: str, *, api_kwargs: JSONDict = None):
        super().__init__(api_kwargs=api_kwargs)
        self.id = id
        self.type = chat_type

        self._id_attrs = (self.id, self.type)
        self._freeze()

    @classmethod
    def de_json(cls, data, bot=None):
        data = cls._parse_data(data)
        if not data:
            return None
        chat = cls(
            id=data["id"],
            chat_type=data.get("chat_type"),
        )
        chat.set_bot(bot)
        return chat
