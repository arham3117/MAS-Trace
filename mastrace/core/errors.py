"""Exception types shared across the testbed."""


class MastraceError(Exception):
    """Base class for all testbed errors."""


class ConfigError(MastraceError):
    """A config file is missing, malformed or inconsistent."""


class UnknownModelKey(ConfigError):
    """A model key is not defined in `configs/models.yaml`."""

    def __init__(self, key: str, known: list[str]) -> None:
        self.key = key
        self.known = known
        super().__init__(
            f"unknown model key {key!r}; known keys in models.yaml: {', '.join(known) or '(none)'}"
        )


class PayloadMissing(MastraceError):
    """A payload reference points to a file that does not exist."""


class InvalidPayloadRef(MastraceError):
    """A string is not of the form `sha256:<64 hex chars>`."""
