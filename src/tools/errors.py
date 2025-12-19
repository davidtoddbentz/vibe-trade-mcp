"""Structured error handling for MCP tools.

This module provides structured error types that agents can parse to make
better decisions about error recovery.
"""

from enum import Enum
from typing import Any

from mcp.server.fastmcp.exceptions import ToolError


class ErrorCode(str, Enum):
    """Error codes for structured error responses.

    These codes help agents distinguish between different error types
    and make appropriate recovery decisions.
    """

    # Resource not found errors
    NOT_FOUND = "NOT_FOUND"
    ARCHETYPE_NOT_FOUND = "ARCHETYPE_NOT_FOUND"
    CARD_NOT_FOUND = "CARD_NOT_FOUND"
    STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
    SCHEMA_NOT_FOUND = "SCHEMA_NOT_FOUND"

    # Validation errors (requires user action)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    SCHEMA_ETAG_MISMATCH = "SCHEMA_ETAG_MISMATCH"
    INVALID_ROLE = "INVALID_ROLE"
    INVALID_STATUS = "INVALID_STATUS"
    DUPLICATE_ATTACHMENT = "DUPLICATE_ATTACHMENT"
    ATTACHMENT_NOT_FOUND = "ATTACHMENT_NOT_FOUND"

    # Transient errors (should indicate retry in message)
    DATABASE_ERROR = "DATABASE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"

    # Internal errors (requires investigation)
    INTERNAL_ERROR = "INTERNAL_ERROR"


class StructuredToolError(ToolError):
    """Structured error for MCP tools with error codes and recovery hints.

    This extends FastMCP's ToolError to provide structured information
    that agents can parse to make better recovery decisions.

    Attributes:
        error_code: Machine-readable error code
        recovery_hint: Optional hint for how to recover from this error
        details: Optional additional error details
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        recovery_hint: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize structured tool error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            recovery_hint: Optional hint for recovery
            details: Optional additional error details
        """
        super().__init__(message)
        self.error_code = error_code
        self.recovery_hint = recovery_hint
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for structured response.

        Returns:
            Dictionary with error structure
        """
        return {
            "error_code": self.error_code.value,
            "message": str(self),
            "recovery_hint": self.recovery_hint,
            "details": self.details,
        }

    def __str__(self) -> str:
        """Return error message with structured information."""
        msg = super().__str__()
        # Include structured error information in the message
        # This ensures agents can see error_code and recovery_hint
        msg += f"\nError code: {self.error_code.value}"
        if self.recovery_hint:
            msg += f"\nRecovery hint: {self.recovery_hint}"
        if self.details:
            # Include key details that might be helpful
            if "validation_errors" in self.details:
                # Validation errors are already in the main message, skip
                pass
            elif "type_id" in self.details:
                msg += f"\nType ID: {self.details['type_id']}"
        return msg


# Convenience functions for common error types


def not_found_error(
    resource_type: str, resource_id: str, recovery_hint: str
) -> StructuredToolError:
    """Create a NOT_FOUND error.

    Args:
        resource_type: Type of resource (e.g., "Card", "Strategy", "Archetype", "Schema")
        resource_id: Identifier of the resource
        recovery_hint: Recovery hint provided by the calling tool

    Returns:
        StructuredToolError with appropriate NOT_FOUND error code
    """
    message = f"{resource_type} not found: {resource_id}"

    # Map resource types to specific error codes
    error_code_map = {
        "Card": ErrorCode.CARD_NOT_FOUND,
        "Strategy": ErrorCode.STRATEGY_NOT_FOUND,
        "Archetype": ErrorCode.ARCHETYPE_NOT_FOUND,
        "Schema": ErrorCode.SCHEMA_NOT_FOUND,
    }
    error_code = error_code_map.get(resource_type, ErrorCode.NOT_FOUND)

    return StructuredToolError(
        message=message,
        error_code=error_code,
        recovery_hint=recovery_hint,
        details={"resource_type": resource_type, "resource_id": resource_id},
    )


def validation_error(
    message: str, recovery_hint: str | None = None, details: dict[str, Any] | None = None
) -> StructuredToolError:
    """Create a VALIDATION_ERROR.

    Args:
        message: Error message
        recovery_hint: Optional recovery hint
        details: Optional additional details

    Returns:
        StructuredToolError with VALIDATION_ERROR code
    """
    return StructuredToolError(
        message=message,
        error_code=ErrorCode.VALIDATION_ERROR,
        recovery_hint=recovery_hint,
        details=details or {},
    )


def schema_validation_error(
    type_id: str, errors: list[str], recovery_hint: str | None = None
) -> StructuredToolError:
    """Create a SCHEMA_VALIDATION_ERROR.

    Args:
        type_id: Archetype identifier
        errors: List of validation error messages
        recovery_hint: Optional recovery hint

    Returns:
        StructuredToolError with SCHEMA_VALIDATION_ERROR code
    """
    if not recovery_hint:
        recovery_hint = f"Browse archetype-schemas://{type_id.split('.', 1)[0]} resource to see valid values, constraints, and examples."

    error_details = "\n".join(f"  - {err}" for err in errors)
    message = f"Slot validation failed for archetype '{type_id}':\n{error_details}"

    return StructuredToolError(
        message=message,
        error_code=ErrorCode.SCHEMA_VALIDATION_ERROR,
        recovery_hint=recovery_hint,
        details={"type_id": type_id, "validation_errors": errors},
    )


def schema_etag_mismatch_error(
    provided_etag: str, current_etag: str, recovery_hint: str | None = None
) -> StructuredToolError:
    """Create a SCHEMA_ETAG_MISMATCH error.

    Args:
        provided_etag: ETag provided by client
        current_etag: Current schema ETag
        recovery_hint: Optional recovery hint

    Returns:
        StructuredToolError with SCHEMA_ETAG_MISMATCH code
    """
    if not recovery_hint:
        recovery_hint = (
            "Please browse the archetype-schemas://all resource to fetch the latest schema."
        )

    message = f"Schema ETag mismatch. Provided: {provided_etag}, Current: {current_etag}."

    return StructuredToolError(
        message=message,
        error_code=ErrorCode.SCHEMA_ETAG_MISMATCH,
        recovery_hint=recovery_hint,
        details={"provided_etag": provided_etag, "current_etag": current_etag},
    )


def transient_error(
    message: str, recovery_hint: str | None = None, details: dict[str, Any] | None = None
) -> StructuredToolError:
    """Create a transient error that should be retried.

    Args:
        message: Error message (should indicate that retry is appropriate)
        recovery_hint: Optional recovery hint (defaults to retry instruction)
        details: Optional additional details

    Returns:
        StructuredToolError with appropriate transient error code
    """
    if not recovery_hint:
        recovery_hint = "This error may be transient. Please try again."

    # Ensure the message also indicates retry is appropriate
    if "try again" not in message.lower() and "retry" not in message.lower():
        message = f"{message} Please try again."

    return StructuredToolError(
        message=message,
        error_code=ErrorCode.DATABASE_ERROR,
        recovery_hint=recovery_hint,
        details=details or {},
    )
