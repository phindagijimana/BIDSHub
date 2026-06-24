"""Phase 5 — lightweight "is there a newer release?" check.

A packaged app can't ``git pull`` like ``./hub update``, so it instead asks the
GitHub Releases API whether a newer tag exists and surfaces a link. This is a
*notification*, not an auto-installer (in-place self-update needs Sparkle /
Squirrel and code-signing infrastructure — out of scope here).

Best-effort and fully non-fatal: any network/parse error yields "no update".
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Optional, Tuple

logger = logging.getLogger("bidshub.desktop")

REPO = "phindagijimana/BIDSHub"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def parse_version(text: str) -> Tuple[int, ...]:
    """'v3.2.10' / '3.2.10' -> (3, 2, 10). Non-numeric tails are ignored."""
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums) or (0,)


def is_newer(latest: str, current: str) -> bool:
    """True if ``latest`` is a strictly higher version than ``current``."""
    a, b = parse_version(latest), parse_version(current)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return a > b


def fetch_latest_release(timeout: float = 4.0) -> Optional[dict]:
    """Return the GitHub 'latest release' JSON, or None on any failure.

    Split out from :func:`check_for_update` so tests can stub the network.
    """
    req = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "BIDSHub"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # offline, rate-limited, DNS, etc.
        logger.debug("update check failed: %s", exc)
        return None


def current_version() -> str:
    try:
        from src.bidshub_version import __version__
        return __version__
    except Exception:
        return "0"


def check_for_update(current: Optional[str] = None) -> Optional[dict]:
    """Return ``{'version','url','name'}`` if a newer release exists, else None."""
    current = current or current_version()
    data = fetch_latest_release()
    if not data:
        return None
    tag = data.get("tag_name") or data.get("name") or ""
    if tag and is_newer(tag, current):
        return {
            "version": tag,
            "url": data.get("html_url", f"https://github.com/{REPO}/releases"),
            "name": data.get("name") or tag,
        }
    return None
