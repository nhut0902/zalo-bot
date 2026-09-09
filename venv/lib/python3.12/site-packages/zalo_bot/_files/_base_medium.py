"""Common base class for media objects"""
from typing import TYPE_CHECKING, Optional

from zalo_bot._zalo_object import ZaloObject
from zalo_bot._utils.default_value import DEFAULT_NONE
from zalo_bot._utils.types import JSONDict, ODVInput

if TYPE_CHECKING:
    from zalo_bot import File


class _BaseMedium(ZaloObject):
    """Base class for objects representing the various media file types.
    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if their :attr:`file_unique_id` is equal.

    Args:
        file_id (:obj:`str`): Identifier for this file, which can be used to download
            or reuse the file.
        file_unique_id (:obj:`str`): Unique identifier for this file, which
            is supposed to be the same over time and for different bots.
            Can't be used to download or reuse the file.
        file_size (:obj:`int`, optional): File size.

    Attributes:
        file_id (:obj:`str`): File identifier.
        file_unique_id (:obj:`str`): Unique identifier for this file, which
            is supposed to be the same over time and for different bots.
            Can't be used to download or reuse the file.
        file_size (:obj:`int`): Optional. File size.


    """

    __slots__ = ("file_id", "file_size", "file_unique_id")

    def __init__(
        self,
        file_id: str,
        file_unique_id: str,
        file_size: Optional[int] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)

        # Required
        self.file_id: str = str(file_id)
        self.file_unique_id: str = str(file_unique_id)
        # Optionals
        self.file_size: Optional[int] = file_size

        self._id_attrs = (self.file_unique_id,)

    async def get_file(
        self,
        *,
        read_timeout: ODVInput[float] = DEFAULT_NONE,
        write_timeout: ODVInput[float] = DEFAULT_NONE,
        connect_timeout: ODVInput[float] = DEFAULT_NONE,
        pool_timeout: ODVInput[float] = DEFAULT_NONE,
        api_kwargs: Optional[JSONDict] = None,
    ) -> "File":
        """Convenience wrapper over :meth:`zalo_bot.Bot.get_file`

        For the documentation of the arguments, please see :meth:`zalo_bot.Bot.get_file`.

        Returns:
            :class:`zalo_bot.File`

        Raises:
            :class:`zalo_bot.error.ZaloError`

        """
        return await self.get_bot().get_file(
            file_id=self.file_id,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            connect_timeout=connect_timeout,
            pool_timeout=pool_timeout,
            api_kwargs=api_kwargs,
        )
