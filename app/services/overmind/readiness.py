"""
Readiness Gate for Overmind Services.
Ensures that critical providers are available before starting a mission.
"""

import asyncio
import logging
import os

import httpx

from app.services.overmind.domain.types import (
    EgressCheckDetails,
    MissionReadinessStatus,
    ProviderReadinessDetails,
)

logger = logging.getLogger(__name__)


class ProviderReadinessGate:
    """
    Checks if the necessary external providers (Search, Scraping, LLM) are configured and reachable.
    """

    @staticmethod
    async def check_search_providers() -> ProviderReadinessDetails:
        """
        Checks availability of search providers.
        Returns a status dict: {"status": "ready" | "degraded" | "failed", "details": ...}
        """
        tavily_key = os.environ.get("TAVILY_API_KEY")

        # Auto-sanitize if user accidentally pasted the MCP URL
        if tavily_key and "tavilyApiKey=" in tavily_key:
            try:
                tavily_key = tavily_key.split("tavilyApiKey=")[1].split("&")[0]
                # Log without exposing the full key
                logger.info("Auto-sanitized Tavily API Key from URL format.")
            except IndexError:
                pass

        has_tavily = bool(tavily_key and tavily_key.startswith("tvly-"))

        # Check internet egress (using a reliable endpoint like Google or Cloudflare)
        internet_status = await ProviderReadinessGate._check_egress_detailed()

        if internet_status["status"] == "NO_EGRESS":
            return {
                "status": "failed",
                "reason": "No internet access (Egress blocked)",
                "details": f"Cannot reach external network. Failed probes: {internet_status['failed_probes']}",
            }

        # If specific protocols failed but others worked, we might still proceed
        # For now, if status is OK or PARTIAL, we proceed.

        if has_tavily:
            return {
                "status": "ready",
                "details": "Tavily API Key present.",
            }

        # Fallback to DuckDuckGo (Implicitly available via langchain community if internet works)
        # We consider this "degraded" because DDG is less reliable/powerful than Tavily for deep research.
        logger.warning(
            "Running in Degraded Mode: No Tavily API Key found. Using DuckDuckGo fallback."
        )
        return {
            "status": "degraded",
            "reason": "missing_tavily_key",
            "details": "Using DuckDuckGo fallback.",
        }

    @staticmethod
    async def _check_egress_detailed() -> EgressCheckDetails:
        """
        Robust check for network connectivity using multiple endpoints.
        Handles proxies, redirects, and intermittent failures.
        Returns detailed diagnostic info.
        """
        endpoints = [
            ("https://1.1.1.1", "Cloudflare DNS"),
            ("https://8.8.8.8", "Google DNS"),
            ("https://www.google.com", "Google Search"),
            ("https://www.github.com", "GitHub"),
            ("http://example.com", "HTTP Fallback"),
        ]

        success_count = 0
        failed_probes = []

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, trust_env=True) as client:
            # Run checks concurrently for speed
            tasks = []
            for url, name in endpoints:
                tasks.append(ProviderReadinessGate._probe_url(client, url, name))

            results = await asyncio.gather(*tasks)

            for is_success, name, error in results:
                if is_success:
                    success_count += 1
                else:
                    failed_probes.append(f"{name}: {error}")

        if success_count > 0:
            return {
                "status": "OK" if len(failed_probes) == 0 else "PARTIAL",
                "success_count": success_count,
                "failed_probes": failed_probes,
            }

        return {
            "status": "NO_EGRESS",
            "success_count": 0,
            "failed_probes": failed_probes,
        }

    @staticmethod
    async def _probe_url(client, url, name) -> tuple[bool, str, str | None]:
        try:
            resp = await client.get(url)
            if 200 <= resp.status_code < 400:
                return True, name, None
            logger.warning(f"Egress check warning: {url} returned {resp.status_code}")
            return False, name, f"Status {resp.status_code}"
        except Exception as e:
            logger.debug(f"Egress check failed for {url}: {e}")
            return False, name, str(e)


async def check_mission_readiness() -> MissionReadinessStatus:
    """
    Master readiness check called before mission start.
    """
    search_status = await ProviderReadinessGate.check_search_providers()

    if search_status["status"] == "failed":
        logger.error(f"Mission Readiness Failed: {search_status}")
        # 'reason' and 'details' are NotRequired, but logic guarantees them if failed.
        # We use .get() for safety or direct access if we trust logic.
        return {
            "ready": False,
            "error": search_status.get("reason", "Unknown Error"),
            "details": search_status.get("details"),
        }

    if search_status["status"] == "degraded":
        logger.warning(f"Mission starting in Degraded Mode: {search_status.get('details')}")

    return {
        "ready": True,
        "mode": search_status["status"],
    }
