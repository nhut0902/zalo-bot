from __future__ import annotations

from typing import List, Optional


class CallbackContext:
    """Simple context passed to handler callbacks."""

    def __init__(self, application: 'Application', args: Optional[List[str]] = None) -> None:
        self.application = application
        self.bot = application.bot
        self.args = args or []


class ContextTypes:
    """Namespace for context related classes."""

    DEFAULT_TYPE = CallbackContext
