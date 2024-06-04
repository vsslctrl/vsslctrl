import traceback


class VsslCtrlException(Exception):
    """VSSL Exception"""

    def __init__(self, message):
        super().__init__(message)
        self.traceback = traceback.format_exc()


class ZoneError(VsslCtrlException):
    """Zone Exception"""


class ZoneConnectionError(ZoneError):
    """Zone Connection Exception Exception"""


class ZeroConfNotInstalled(VsslCtrlException):
    """Zone Exception"""
