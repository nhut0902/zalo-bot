from typing import Final, NamedTuple

__all__ = ("__version__", "__version_info__")


class Version(NamedTuple):
    """Copies the behavior of sys.version_info.
    serial is always 0 for stable releases.
    """

    major: int
    minor: int
    micro: int
    releaselevel: str  # Literal['alpha', 'beta', 'candidate', 'final']
    serial: int

    def _rl_shorthand(self) -> str:
        return {
            "alpha": "a",
            "beta": "b",
            "candidate": "rc",
        }[self.releaselevel]

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}"
        if self.micro != 0:
            version = f"{version}.{self.micro}"
        if self.releaselevel != "final":
            version = f"{version}{self._rl_shorthand()}{self.serial}"

        return version


__version_info__: Final[Version] = Version(
    major=21, minor=6, micro=0, releaselevel="final", serial=0
)
__version__: Final[str] = str(__version_info__)
