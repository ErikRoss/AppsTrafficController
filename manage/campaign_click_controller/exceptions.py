from abc import ABC

from flask import Response


class BaseError(Exception, ABC):
    """
    Used to return a json response
    with a message and code of error.
    """

    STATUS_CODE: int


class NoValidError(BaseError):
    STATUS_CODE = 400


class NotFoundError(BaseError):
    STATUS_CODE = 404


class SafeAbort(Exception):
    """
    Used to stop method execution
    without throwing an exception.
    """
    pass


class SafeAbortAndResponse(Exception):
    """
    Used to stop method execution
    and return the response immediately.
    """

    response: "Response"

    def __init__(self, response: "Response", *args):
        self.response = response
        super().__init__(*args)