"""Warning classes used by this library."""

__all__ = ["PTBDeprecationWarning", "PTBRuntimeWarning", "PTBUserWarning"]


class PTBUserWarning(UserWarning):
    """Custom user warning class for this library.

    .. seealso:: :wiki:`Exceptions, Warnings and Logging <Exceptions%2C-Warnings-and-Logging>`
    """

    __slots__ = ()


class PTBRuntimeWarning(PTBUserWarning, RuntimeWarning):
    """Custom runtime warning class for this library."""

    __slots__ = ()


class PTBDeprecationWarning(PTBUserWarning, DeprecationWarning):
    """Custom warning class for deprecations in this library.

    Args:
        version: The version in which the feature was deprecated.
        message: The message to display.

    Attributes:
        version: The version in which the feature was deprecated.
        message: The message to display.
    """

    __slots__ = ("message", "version")

    def __init__(self, version: str, message: str) -> None:
        self.version: str = version
        self.message: str = message

    def __str__(self) -> str:
        """Return string representation using message and version."""
        return f"Deprecated since version {self.version}: {self.message}"