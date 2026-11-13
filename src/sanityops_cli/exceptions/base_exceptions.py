"""deeplogic CLI Error Definitions"""


class deeplogicError(Exception):
    """deeplogic CLI Base Exception Class"""

    exit_code: int = 2


class ValidationError(deeplogicError):
    """Validation Error Exception Class"""

    exit_code: int = 2
