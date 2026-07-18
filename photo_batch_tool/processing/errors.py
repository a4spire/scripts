class ProcessingError(Exception):
    """Base class for expected, user-facing processing failures."""


class BackgroundRemovalError(ProcessingError):
    pass


class NoObjectDetectedError(BackgroundRemovalError):
    pass


class InvalidRadiusError(ProcessingError):
    pass
