"""This module contains auxiliary functionality for building strings for __repr__ method.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""
from typing import Any


def build_repr_with_selected_attrs(obj: object, **kwargs: Any) -> str:
    """Create ``__repr__`` string in the style ``Classname[arg1=1, arg2=2]``.

    The square brackets emphasize the fact that an object cannot be instantiated
    from this string.

    Attributes that are to be used in the representation, are passed as kwargs.
    """
    return (
        f"{obj.__class__.__name__}"
        # square brackets emphasize that an object cannot be instantiated with these params
        f"[{', '.join(_stringify(name, value) for name, value in kwargs.items())}]"
    )


def _stringify(key: str, val: Any) -> str:
    return f"{key}={val.__qualname__ if callable(val) else val}"
