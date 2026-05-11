"""Load Supabase credentials from environment (e.g. repo-root `.env`)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


def _normalize_supabase_url(url: str) -> str:
    """`supabase-py` expects `https://<ref>.supabase.co`, not the REST base URL."""
    u = (url or "").strip().rstrip("/")
    if u.endswith("/rest/v1"):
        u = u[: -len("/rest/v1")].rstrip("/")
    return u


SUPABASE_URL = _normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or ""
