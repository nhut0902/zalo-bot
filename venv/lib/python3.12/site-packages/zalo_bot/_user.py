"""This module contains an object that represents a Zalo Bot User."""

from typing import Optional
from zalo_bot._utils.types import JSONDict
from zalo_bot._zalo_object import ZaloObject


class User(ZaloObject):
    """This object represents a Zalo bot.

    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if their :attr:`id` is equal.

    Args:
        id (:obj:`str`): Unique identifier for this user.
        account_name (:obj:`str`): Name of the account.
        account_type (:obj:`str`): Type of the account.
        can_join_groups (:obj:`str`, optional): :obj:`True`, if the bot can be invited to groups.
            Returned only in :meth:`zalo_bot.Bot.get_me`.
        display_name (:obj:`str`, optional): Display name of the user.
        is_bot (:obj:`bool`, optional): :obj:`True`, if the user is a bot.

    Attributes:
        id (:obj:`str`): Unique identifier for this user.
        account_name (:obj:`str`): Name of the account.
        account_type (:obj:`str`): Type of the account.
        can_join_groups (:obj:`str`, optional): :obj:`True`, if the bot can be invited to groups.
            Returned only in :meth:`zalo_bot.Bot.get_me`.
        display_name (:obj:`str`, optional): Display name of the user.
        is_bot (:obj:`bool`, optional): :obj:`True`, if the user is a bot.
    """

    __slots__ = (
        'id',
        'account_name',
        'account_type',
        'can_join_groups',
        'display_name',
        'is_bot',
    )

    def __init__(
        self,
        id: str,
        display_name: Optional[str] = None,
        account_name: Optional[str] = None,
        account_type: Optional[str] = None,
        is_bot: Optional[bool] = None,
        can_join_groups: Optional[bool] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        # Required
        self.id: str = id
        # Optional
        self.display_name: Optional[str] = display_name
        self.account_name: Optional[str] = account_name
        self.account_type: Optional[str] = account_type
        self.is_bot: Optional[bool] = is_bot
        self.can_join_groups: Optional[bool] = can_join_groups

        self._id_attrs = (self.id,)

        self._freeze()

    

