"""This module contains helper functions related to parsing arguments for classes and methods.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""
from typing import Optional, Sequence, Tuple, TypeVar

from zalo_bot._link_preview_options import LinkPreviewOptions
from zalo_bot._utils.types import ODVInput

T = TypeVar("T")


def parse_sequence_arg(arg: Optional[Sequence[T]]) -> Tuple[T, ...]:
    """Parses an optional sequence into a tuple

    Args:
        arg (:obj:`Sequence`): The sequence to parse.

    Returns:
        :obj:`Tuple`: The sequence converted to a tuple or an empty tuple.
    """
    return tuple(arg) if arg else ()


def parse_lpo_and_dwpp(
    disable_web_page_preview: Optional[bool], link_preview_options: ODVInput[LinkPreviewOptions]
) -> ODVInput[LinkPreviewOptions]:
    """Wrapper around warn_about_deprecated_arg_return_new_arg. Takes care of converting
    disable_web_page_preview to LinkPreviewOptions.
    """
    if disable_web_page_preview and link_preview_options:
        raise ValueError(
            "Parameters `disable_web_page_preview` and `link_preview_options` are mutually "
            "exclusive."
        )

    if disable_web_page_preview is not None:
        link_preview_options = LinkPreviewOptions(is_disabled=disable_web_page_preview)

    return link_preview_options
