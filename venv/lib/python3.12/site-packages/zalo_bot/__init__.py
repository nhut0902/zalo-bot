"""Python interface to the Zalo Bot API"""

from ._bot import Bot
from ._user import User
from . import constants, error, warnings
__all__ = [
    "Bot",
    "User",
    "constants",
    "error",
    "warnings",
    "InputFile",
    "ZaloObject",
    "Credentials",
    "DataCredentials",
    "EncryptedCredentials",
    "FileCredentials",
    "SecureData",
    "SecureValue",
    "File",
    "request",
    "Message",
    "Chat",
    "Update",
]

from . import request
from ._files.input_file import InputFile
from ._zalo_object import ZaloObject

from ._passport.credentials import (
    Credentials,
    DataCredentials,
    EncryptedCredentials,
    FileCredentials,
    SecureData,
    SecureValue,
)

from ._files.file import File
from ._message import Message
from ._chat import Chat

from ._update import Update


def __version__():
    """Return package version."""
    return "0.0.1"


def describe():
    """Print package description and features."""
    description = f"""
    Zalo Bot API Wrapper
    Version: {__version__()}
    Provides a Python interface to the Zalo Bot API.
    Features:
    - Send messages to users
    - Receive messages from users
    - Handle updates from the Zalo Bot API
    - Handle errors from the Zalo Bot API
    - Handle warnings from the Zalo Bot API
    """
    print(description)

