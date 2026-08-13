"""Sanityops CLI Error Definitions"""


class SanityopsError(Exception):
    """Sanityops CLI Base Exception Class"""
    exit_code: int = 2

class ValidationError(SanityopsError):
    """Validation Error Exception Class"""
    exit_code: int = 2
