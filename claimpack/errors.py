"""Typed errors surfaced by the trusted ClaimPack consumer."""


class ClaimPackError(Exception):
    """Base class for expected ClaimPack failures."""


class ParseError(ClaimPackError):
    """Input is not unambiguous restricted-profile JSON."""


class LimitError(ClaimPackError):
    """A bounded-consumption limit was exceeded."""


class ValidationError(ClaimPackError):
    """A package or record violates the v0.1 contract."""


class PolicyError(ClaimPackError):
    """A trust policy is malformed or cannot be applied."""
