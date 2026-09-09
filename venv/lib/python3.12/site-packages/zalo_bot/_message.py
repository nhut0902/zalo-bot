from typing import TYPE_CHECKING, Optional, Union
from zalo_bot._utils.default_value import DEFAULT_NONE, DefaultValue
from zalo_bot._zalo_object import ZaloObject
from zalo_bot._user import User  # assume you have this
from zalo_bot._chat import Chat  # assume you have this
from zalo_bot._utils.types import JSONDict, ODVInput
import datetime

if TYPE_CHECKING:
    from zalo_bot import Chat, User


class Message(ZaloObject):
    __slots__ = ("message_id", "date", "chat", "text", "from_user", "sticker", "photo_url", "message_type")

    def __init__(
        self,
        message_id: str,
        date: datetime.datetime,
        chat: Chat,
        message_type: ODVInput[Union[str, DefaultValue]] = DEFAULT_NONE,
        text: Optional[str] = None,
        sticker: Optional[str] = None,
        photo_url: Optional[str] = None,
        from_user: Optional[User] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        self.message_id = message_id
        self.date = date
        self.chat = chat
        self.text = text
        self.message_type = message_type if message_type is not DEFAULT_NONE else "CHAT_MESSAGE"
        self.sticker = sticker
        self.photo_url = photo_url
        self.from_user = from_user

        self._id_attrs = (self.message_id, self.chat)
        self._freeze()

    @classmethod
    def de_json(cls, data: Optional[JSONDict], bot=None) -> Optional["Message"]:
        data = cls._parse_data(data)
        if not data:
            return None
        message = cls(
            message_id=data["message_id"],
            date=datetime.datetime.fromtimestamp(data["date"] / 1000),
            chat=Chat.de_json(data.get("chat"), bot),
            message_type=data.get("message_type", "CHAT_MESSAGE"),
            text=data.get("text"),
            sticker=data.get("sticker"),
            photo_url=data.get("photo_url"),
            from_user=User.de_json(data.get("from"), bot),
            api_kwargs=data,
        )
        message.set_bot(bot)
        return message

    def reply_text(self, text: str) -> "Message":
        """
        Reply method that sends a message back to the same chat.
        """
        return self.get_bot().send_message(
            chat_id=self.chat.id,
            text=text,
        )

    def reply_photo(self, photo: str, caption: str) -> "Message":
        """
        Reply method that sends a photo back to the same chat.
        """
        return self.get_bot().send_photo(
            chat_id=self.chat.id,
            photo=photo,
            caption=caption,
        )
    
    def reply_sticker(self, sticker: str) -> "Message":
        """
        Reply method that sends a sticker back to the same chat.
        """
        return self.get_bot().send_sticker(
            chat_id=self.chat.id,
            sticker=sticker,
        )
    
    def reply_action(self, action: str) -> "Message":
        """
        Reply method that sends a chat action back to the same chat.
        """
        return self.get_bot().send_chat_action(
            chat_id=self.chat.id,
            action=action,
        )
    
