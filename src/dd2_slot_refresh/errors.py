"""Shared errors and validation helpers."""


class ValidationError(ValueError):
    """The input does not satisfy the supported format or preservation rules."""


def require(condition, message):
    """Do not use assert for checks that must survive Python optimization."""
    if not condition:
        raise ValidationError(str(message))
