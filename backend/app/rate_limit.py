from __future__ import annotations
"""
ClinNote AI — Rate Limiter
============================
Defines the shared slowapi ``Limiter`` instance.

Lives in its own module so both ``app.main`` and route modules
(e.g. ``app.api.v1.auth``) can import it without creating a circular
dependency on ``app.main``.
"""


from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()

# Shared limiter instance — import this from anywhere that needs to
# attach @limiter.limit(...) decorators.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{_settings.RATE_LIMIT_PER_MINUTE}/minute"],
)
