"""
core/intel/bulletins.py

Wave 7 — CERT-AGID come bacheca di spunti, MAI estrazione automatica di
keyword. Go/no-go quantitativo verificato in Wave 0 (docs/threat-intel-sources.md):
10 item/mese, brand riconoscibile in >80% dei titoli individuali — sopra la
soglia di 6/mese e 50%, la Wave procede come pianificata.

Riusa integralmente l'infrastruttura Wave 1-5: fetch difensivo, cache TTL su
disco, Snapshot, runner/scheduler (job registrato con auto=False: è una
bacheca per un umano, non serve refresh in background).

Il bottone "Crea campagna da questo bollettino" (frontend) apre il form di
Wave 6 precompilato SOLO con nome/fonte/link/data — le keyword non vengono
MAI generate qui: un titolo come "Phishing a tema SPID in corso" produrrebbe
al massimo 2 keyword generiche con soglia 1, una campagna che matcherebbe
qualunque email che nomini SPID.

Parsing sicuro con defusedxml (RSS è input non fidato); solo titolo, data,
link ed estratto breve sono mostrati — mai il testo integrale del bollettino
(attribuzione, non ripubblicazione).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import bleach
from defusedxml import ElementTree as DefusedET

from core.intel import cache as intel_cache
from core.intel import fetch as intel_fetch
from utils.config import settings

logger = logging.getLogger(__name__)

FEED_URL = "https://cert-agid.gov.it/feed/"
CACHE_KEY = "certagid_bulletins"
CACHE_SCHEMA = 1
TTL_HOURS = 12
MAX_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 50
_USER_AGENT = f"EMLyzer/{settings.VERSION} (email analysis tool)"

_PHISHING_KEYWORDS = ("phishing", "smishing", "campagna", "campagne", "malevol")


@dataclass
class Bulletin:
    title: str
    link: str
    published_at: str  # ISO, stringa vuota se non parsabile
    excerpt: str


def _parse_rss(raw: bytes) -> list[dict]:
    root = DefusedET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item")[:MAX_ITEMS]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        description_raw = (item.findtext("description") or "").strip()

        published_at = ""
        if pub_date_raw:
            try:
                published_at = parsedate_to_datetime(pub_date_raw).astimezone(timezone.utc).isoformat()
            except Exception:
                pass

        # Sanitizzazione: la description RSS può contenere HTML — bleach già
        # presente nel progetto per la sanitizzazione del body email.
        excerpt = bleach.clean(description_raw, tags=[], strip=True)
        excerpt = re.sub(r"\s+", " ", excerpt).strip()[:280]

        if not re.search("|".join(_PHISHING_KEYWORDS), f"{title} {excerpt}", re.IGNORECASE):
            continue  # filtro sui post a tema phishing/campagna, come da piano

        items.append({"title": title, "link": link, "published_at": published_at, "excerpt": excerpt})
    return items


def refresh(*, force: bool = False) -> bool:
    ttl = None if force else TTL_HOURS
    if not force:
        cached = intel_cache.load(CACHE_KEY, ttl_hours=ttl, expected_schema=CACHE_SCHEMA)
        if cached is not None:
            return True

    try:
        result = intel_fetch.fetch_bytes(FEED_URL, max_bytes=MAX_BYTES, user_agent=_USER_AGENT)
        items = _parse_rss(result.content)
    except Exception as e:
        logger.warning("[intel.bulletins] Fetch/parsing RSS CERT-AGID fallito: %s", type(e).__name__)
        stale = intel_cache.load(CACHE_KEY, ttl_hours=None, expected_schema=CACHE_SCHEMA)
        return stale is not None

    intel_cache.save(CACHE_KEY, items, source_url=FEED_URL, schema=CACHE_SCHEMA)
    return True


def list_bulletins() -> list[dict]:
    entry = intel_cache.load(CACHE_KEY, ttl_hours=None, expected_schema=CACHE_SCHEMA)
    return entry.data if entry is not None else []


def status() -> dict:
    stat = intel_cache.stat(CACHE_KEY)
    if not stat.exists:
        return {"state": "never_fetched", "age_hours": None, "item_count": None}
    state = "ok" if (stat.age_hours or 0) <= TTL_HOURS else "stale"
    return {"state": state, "age_hours": stat.age_hours, "item_count": stat.entry_count}


def register_job() -> None:
    from core.intel import runner as intel_runner
    intel_runner.register(intel_runner.IntelJob(
        name="bulletins", run=lambda: refresh(force=False),
        interval_minutes=None, auto=False,
    ))
