from __future__ import annotations


class CustomerPortalError(Exception):
    pass


class CustomerPortalAccessError(CustomerPortalError):
    pass


class CustomerPortalNotFoundError(CustomerPortalError):
    pass
