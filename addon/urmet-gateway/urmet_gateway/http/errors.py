"""What a failure looks like on the wire, and which status carries it.

One table, read most specific first, because the SDK's errors are a hierarchy:
``OpenNotAcknowledgedError`` and ``NoVideoOfferedError`` are both ``CallError``,
and that one and its siblings are all ``SipError``. A failure the table does not
list is one this layer did not foresee: it answers 500 and its traceback goes to
the log, never onto the wire. What crosses the wire is the error's type name and
its message, which is what a caller can act on. Nothing is swallowed.
"""

from __future__ import annotations

import logging

from aiohttp import web
from aiohttp.typedefs import Handler
from pydantic import ValidationError

from urmet_gateway.domain.errors import (
    CallError,
    MalformedBodyError,
    MediaUnavailableError,
    NoStreamingCallError,
    NotRegisteredError,
    NoVideoOfferedError,
    OpenNotAcknowledgedError,
    RegistrationError,
    UnknownCallError,
)

logger = logging.getLogger(__name__)

# Order is the whole point: the first entry that matches wins, so a subclass has
# to be listed before the class it extends (DESIGN 5.2).
STATUS_TABLE: tuple[tuple[type[Exception], int], ...] = (
    (OpenNotAcknowledgedError, 502),
    (NoVideoOfferedError, 409),
    (NotRegisteredError, 409),
    (RegistrationError, 502),
    (CallError, 502),
    (UnknownCallError, 404),
    (NoStreamingCallError, 409),
    (MediaUnavailableError, 503),
    (MalformedBodyError, 400),
)

UNFORESEEN_STATUS = 500

# An open that went unanswered is the one failure whose meaning cannot be read off
# its message: the INFO left and nothing acknowledged it, so the actuator may have
# moved and may not have. A caller reading "not acknowledged" as "not opened"
# would be wrong in the direction that matters, so this is said if the SDK did not.
UNKNOWN_STATE = "the door state is unknown"


def status_for(error: BaseException) -> int:
    """The status the table gives this failure, or 500 when it lists none."""
    for error_type, status in STATUS_TABLE:
        if isinstance(error, error_type):
            return status
    return UNFORESEEN_STATUS


def detail_of(error: BaseException) -> str:
    """The message a caller acts on. Never a traceback, never empty of meaning."""
    message = str(error)
    if isinstance(error, OpenNotAcknowledgedError) and UNKNOWN_STATE not in message:
        return f"{message}; {UNKNOWN_STATE}"
    return message


def describe_validation(error: ValidationError) -> str:
    """A pydantic failure as one line: which field, and what is wrong with it."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'body'}: {item['msg']}"
        for item in error.errors()
    )


def error_response(error: BaseException, status: int) -> web.Response:
    """The one body every failure wears: its type name and its message."""
    return web.json_response(
        {"error": type(error).__name__, "detail": detail_of(error)}, status=status
    )


@web.middleware
async def error_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Turn what a handler raised into a status and a body, and log it.

    ``web.HTTPException`` passes through untouched: it is aiohttp's own answer and
    already carries a status. Everything else is looked up in the table. What the
    table knows is logged as a warning; what it does not is logged with its
    traceback before answering 500.
    """
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as error:
        status = status_for(error)
        if status == UNFORESEEN_STATUS:
            logger.exception("%s %s failed", request.method, request.rel_url)
        else:
            logger.warning(
                "%s %s answered %d: %s: %s",
                request.method,
                request.rel_url,
                status,
                type(error).__name__,
                detail_of(error),
            )
        return error_response(error, status)
