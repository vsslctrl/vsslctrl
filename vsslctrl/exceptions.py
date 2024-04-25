

class VsslException(Exception):
    """VSSL Exception
    """

class ZoneError(VsslException):
    """Zone Exception
    """

class ZoneInitialisationError(ZoneError):
    """ Zone Initialisation Exception
    """
