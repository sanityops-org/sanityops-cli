"""sanityops CLI Error Definitions"""


class sanityopsError(Exception):
    """sanityops CLI Base Exception Class"""

    exit_code: int = 2


class ValidationError(sanityopsError):
    """Validation Error Exception Class"""

    exit_code: int = 2
