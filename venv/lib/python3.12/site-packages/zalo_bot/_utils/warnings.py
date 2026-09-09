"""This module contains helper functions related to warnings issued by the library.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""
import warnings
from typing import Type, Union

from zalo_bot.warnings import PTBUserWarning


def warn(
    message: Union[str, PTBUserWarning],
    category: Type[Warning] = PTBUserWarning,
    stacklevel: int = 0,
) -> None:
    """
    Helper function used as a shortcut for warning with default values.

    Args:
        message (:obj:`str` | :obj:`PTBUserWarning`): Specify the warnings message to pass to
            ``warnings.warn()``.

                Now also accepts a :obj:`PTBUserWarning` instance.

        category (:obj:`Type[Warning]`, optional): Specify the Warning class to pass to
            ``warnings.warn()``. Defaults to :class:`zalo_bot.warnings.PTBUserWarning`.
        stacklevel (:obj:`int`, optional): Specify the stacklevel to pass to ``warnings.warn()``.
            Pass the same value as you'd pass directly to ``warnings.warn()``. Defaults to ``0``.
    """
    warnings.warn(message, category=category, stacklevel=stacklevel + 1)