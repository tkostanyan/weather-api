"""Rate limiting configuration.

This module exists to avoid circular imports between `app.main` and routers.
Routers import `limiter` from here.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)
