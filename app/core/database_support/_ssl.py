"""شريحة سياق SSL (D-261 — تفكيك hotspot `app/core/database.py` — CodeScene X-Ray).
دالةٌ نقيةٌ واحدةٌ تبني `connect_args["ssl"]` لكل نمطٍ من أنماط SSL،
بدون أي منطقٍ خاصٍ بقاعدةٍ معينةٍ.
"""

from __future__ import annotations

import logging
import ssl

logger = logging.getLogger(__name__)

_VALID_SSL_MODES = ("require", "verify-ca", "verify-full")


def build_ssl_connect_args(ssl_mode: str | None) -> dict[str, ssl.SSLContext]:
    """Build asyncpg `connect_args` for the given SSL mode (D-261).

    - ``require``: TLS on the wire, no certificate verification.
    - ``verify-ca`` / ``verify-full``: full default verification.
    - ``None`` (or any unrecognized value): no SSL context is added.
    """
    if ssl_mode not in _VALID_SSL_MODES:
        return {}
    context = ssl.create_default_context()
    if ssl_mode == "require":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    logger.info(f"SSL enabled (mode: {ssl_mode})")
    return {"ssl": context}
