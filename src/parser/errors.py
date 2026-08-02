"""Custom exceptions for parsing and conversion errors.

Every parse failure halts the program with the line number and cause,
as required by the map format specification.
"""

from __future__ import annotations


class ParseError(Exception):
    """A fatal error encountered during map-file processing.

    Carries the offending line number and a human-readable message
    so the caller can emit a clear diagnostic before exiting.
    """

    def __init__(self, line_number: int, message: str) -> None:
        super().__init__(message)
        self.line_number = line_number
        self.message = message

    def __str__(self) -> str:
        return f"line {self.line_number}: {self.message}"
