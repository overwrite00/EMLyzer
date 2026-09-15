"""
core/intel/feeds.py

Registry dei feed IOC locali (OpenPhish, Spamhaus DROP, ...). Sostituisce lo
stato globale ad-hoc che viveva in core/reputation/connectors.py
(_openphish_cache/_loaded/_error, _spamhaus_cache/_loaded/_error) con uno
Snapshot per feed, costruito con lo stesso meccanismo per tutti.

Non è un plugin system generico: con 4 feed l'astrazione serve solo perché
lo scheduler (Wave 5) e /api/intel/status (Wave 3) devono iterare su FEEDS e
leggerne i metadati, non per estendibilità futura.

parse() e build() sono separati perché i due feed esistenti cacheano forme
diverse: OpenPhish cachea un set di stringhe URL, Spamhaus cachea stringhe
CIDR e ricostruisce ipaddress.ip_network al load — un solo "parser" non
modella entrambi. parse(): bytes grezzi -> struttura JSON-serializzabile
(quella che finisce su disco). build(): struttura serializzabile -> struttura
di lookup ottimizzata in memoria.

cache_key resta invariato rispetto ai nomi file già presenti sul disco degli
utenti (openphish_feed, spamhaus_drop) anche se il nome logico del feed
cambiasse: rinominarli forzerebbe un download per tutti al primo avvio dopo
l'update. Se il FORMATO della fonte cambia, si incrementa cache_schema — un
mismatch di schema è un cache-miss pulito (gestito da core.intel.cache),
mai un errore.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from core.intel import cache as intel_cache
from core.intel import fetch as intel_fetch
from core.intel.snapshot import (
    Snapshot, SnapshotMeta,
    STATE_OK, STATE_STALE, STATE_UNAVAILABLE, STATE_NEVER_FETCHED,
)
from utils.config import settings

logger = logging.getLogger(__name__)

_USER_AGENT = f"EMLyzer/{settings.VERSION} (email analysis tool; +https://github.com/)"


# ---------------------------------------------------------------------------
# Parser/builder OpenPhish
# ---------------------------------------------------------------------------

def _parse_openphish(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) > 2048:
            continue  # riga anomala, probabile corruzione/injection — scartata
        if not (line.startswith("http://") or line.startswith("https://")):
            continue  # validazione per-riga: prima assente per OpenPhish
        urls.append(line.lower())
        if len(urls) >= 500_000:
            break  # cap difensivo sul numero di voci
    return urls


def _build_openphish(data: list[str]) -> set[str]:
    return set(data)


# ---------------------------------------------------------------------------
# Parser/builder Spamhaus DROP
# ---------------------------------------------------------------------------

def _parse_spamhaus(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    cidrs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if len(line) > 2048:
            continue
        cidr = line.split(";")[0].strip()
        try:
            ipaddress.ip_network(cidr, strict=False)  # valida, ma cachiamo la stringa
        except ValueError:
            continue
        cidrs.append(cidr)
        if len(cidrs) >= 100_000:
            break
    return cidrs


def _build_spamhaus(data: list[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = []
    for cidr in data:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue
    return networks


# ---------------------------------------------------------------------------
# Parser/builder URLhaus bulk (Wave 8 — go confermato in Wave 0: il download
# CSV non richiede Auth-Key, a differenza delle API live check_url_urlhaus/
# _query_threatfox che restano connettori separati per-singolo-IOC)
# ---------------------------------------------------------------------------

def _parse_urlhaus(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    urls = []
    reader = csv.reader(line for line in text.splitlines() if line and not line.startswith("#"))
    for row in reader:
        if len(row) < 3:
            continue
        url = row[2].strip().lower()
        if not (url.startswith("http://") or url.startswith("https://")) or len(url) > 2048:
            continue
        urls.append(url)
        if len(urls) >= 200_000:
            break
    return urls


def _build_urlhaus(data: list[str]) -> set[str]:
    return set(data)


# ---------------------------------------------------------------------------
# Sanity check pre-swap
# ---------------------------------------------------------------------------

_HTML_ERROR_MARKERS = (b"<!doctype", b"<html", b"<HTML", b"<!DOCTYPE")


def _looks_like_error_page(raw: bytes) -> bool:
    head = raw[:512].lstrip()
    return any(head.lower().startswith(marker.lower()) for marker in _HTML_ERROR_MARKERS)


@dataclass(frozen=True)
class FeedSpec:
    name: str
    cache_key: str          # nome file cache su disco — NON cambiare senza incrementare cache_schema
    cache_schema: int
    url: str
    parse: Callable[[bytes], list]
    build: Callable[[list], Any]
    ttl_hours: float
    max_bytes: int
    min_entries: int
    requires_key: str | None = None


FEEDS: dict[str, FeedSpec] = {
    "openphish": FeedSpec(
        name="openphish", cache_key="openphish_feed", cache_schema=1,
        url="https://openphish.com/feed.txt",
        parse=_parse_openphish, build=_build_openphish,
        ttl_hours=12, max_bytes=8 * 1024 * 1024, min_entries=50,
    ),
    "spamhaus": FeedSpec(
        name="spamhaus", cache_key="spamhaus_drop", cache_schema=1,
        url="https://www.spamhaus.org/drop/drop.txt",
        parse=_parse_spamhaus, build=_build_spamhaus,
        ttl_hours=24, max_bytes=8 * 1024 * 1024, min_entries=20,
    ),
    "urlhaus": FeedSpec(
        name="urlhaus", cache_key="urlhaus_recent", cache_schema=1,
        url="https://urlhaus.abuse.ch/downloads/csv_recent/",
        parse=_parse_urlhaus, build=_build_urlhaus,
        ttl_hours=6, max_bytes=32 * 1024 * 1024, min_entries=100,
    ),
}

_snapshots: dict[str, Snapshot] = {name: Snapshot() for name in FEEDS}

# Backoff esponenziale per-feed sui fallimenti (Wave 5 la userà per lo
# scheduling; qui vive lo stato grezzo perché è il refresh stesso a
# aggiornarlo su ogni esito).
_failure_streak: dict[str, int] = {name: 0 for name in FEEDS}
_next_allowed_attempt: dict[str, float] = {name: 0.0 for name in FEEDS}

_BACKOFF_STEPS_MIN = [5, 10, 20]
_BACKOFF_CAP_MIN = 120


def _effective_ttl_hours(spec: FeedSpec) -> float:
    return spec.ttl_hours * max(settings.INTEL_TTL_MULTIPLIER, 0.01)


def snapshot(name: str) -> Snapshot:
    return _snapshots[name]


def is_backed_off(name: str) -> bool:
    return time.monotonic() < _next_allowed_attempt.get(name, 0.0)


def _record_failure(name: str) -> None:
    _failure_streak[name] = _failure_streak.get(name, 0) + 1
    step = min(_failure_streak[name] - 1, len(_BACKOFF_STEPS_MIN) - 1)
    delay_min = _BACKOFF_STEPS_MIN[step] if step >= 0 else _BACKOFF_STEPS_MIN[0]
    delay_min = min(delay_min * (2 ** max(0, _failure_streak[name] - len(_BACKOFF_STEPS_MIN))), _BACKOFF_CAP_MIN)
    _next_allowed_attempt[name] = time.monotonic() + delay_min * 60


def _record_success(name: str) -> None:
    _failure_streak[name] = 0
    _next_allowed_attempt[name] = 0.0


def refresh(name: str, *, force: bool = False) -> bool:
    """
    Aggiorna il feed `name`. Ritorna True se lo snapshot in memoria è
    utilizzabile al termine (anche se il fetch è fallito e si è ricaduti su
    cache stale), False se non c'è alcun dato disponibile.

    force=True bypassa sia il flag "refresh in corso" (comunque protetto da
    try_begin_refresh) sia il TTL su disco — necessario per il refresh
    manuale (Wave 4) e per i loader "ri-eseguibili" richiesti dal fix del
    fallback stale.
    """
    spec = FEEDS[name]
    snap = _snapshots[name]

    if not force and not snap.try_begin_refresh():
        return snap.get() is not None

    if force:
        # force bypassa anche il flag di "refresh in corso": un endpoint di
        # refresh manuale deve poter forzare anche se lo scheduler sta già
        # tentando in background con backoff attivo.
        snap.end_refresh()
        snap.try_begin_refresh()

    try:
        return _do_refresh(spec, snap, force=force)
    finally:
        snap.end_refresh()


def _do_refresh(spec: FeedSpec, snap: Snapshot, *, force: bool) -> bool:
    # force=True bypassa del tutto la cache-first shortcut e va diretto alla
    # rete: è il comportamento richiesto da un refresh manuale (Wave 4) e
    # da un loader "ri-eseguibile" — con ttl_hours=None la entry su disco
    # sarebbe sempre considerata fresca, il contrario di ciò che force chiede.
    if not force:
        # 1) prova prima la cache su disco entro TTL — evita un fetch di rete
        #    se un'altra istanza/processo ha già aggiornato di recente.
        cached = intel_cache.load(spec.cache_key, ttl_hours=_effective_ttl_hours(spec), expected_schema=spec.cache_schema)
        if cached is not None:
            _install(snap, spec, cached.data, cached.source_url or spec.url, cached.saved_at, state=STATE_OK)
            _record_success(spec.name)
            return True

    try:
        result = intel_fetch.fetch_bytes(
            spec.url, max_bytes=spec.max_bytes, user_agent=_USER_AGENT,
        )
    except intel_fetch.FetchError as e:
        return _fallback_to_stale(spec, snap, category=e.category, message=e.message)
    except Exception as e:
        return _fallback_to_stale(spec, snap, category="unknown_error", message=type(e).__name__)

    if _looks_like_error_page(result.content):
        return _fallback_to_stale(spec, snap, category="malformed_response",
                                   message="Risposta simile a una pagina HTML di errore, non al feed atteso")

    try:
        parsed = spec.parse(result.content)
    except Exception as e:
        return _fallback_to_stale(spec, snap, category="malformed_response", message=f"Parsing fallito: {type(e).__name__}")

    if len(parsed) < spec.min_entries:
        return _fallback_to_stale(
            spec, snap, category="malformed_response",
            message=f"Solo {len(parsed)} voci (attese >= {spec.min_entries}) — fetch probabilmente degradato, cache precedente NON sovrascritta",
        )

    intel_cache.save(spec.cache_key, parsed, source_url=spec.url, schema=spec.cache_schema)
    _install(snap, spec, parsed, spec.url, datetime.now(timezone.utc), state=STATE_OK)
    _record_success(spec.name)
    return True


def _fallback_to_stale(spec: FeedSpec, snap: Snapshot, *, category: str, message: str) -> bool:
    """
    Fetch fallito: prova la cache stale (TTL ignorato) prima di arrendersi.
    FIX del bug storico: qui il verdetto resta VALIDO se la cache stale ha
    voci — l'errore non deve mai impedire il lookup quando i dati esistono,
    solo essere riportato nel detail come età del feed.
    """
    _record_failure(spec.name)
    stale = intel_cache.load(spec.cache_key, ttl_hours=None, expected_schema=spec.cache_schema)
    if stale is not None and stale.data:
        age_hours = (datetime.now(timezone.utc) - stale.saved_at).total_seconds() / 3600
        state = STATE_STALE if age_hours <= settings.INTEL_STALE_HARD_HOURS else STATE_UNAVAILABLE
        _install(snap, spec, stale.data, stale.source_url or spec.url, stale.saved_at, state=state,
                 error_category=category, error_message=message)
        return state != STATE_UNAVAILABLE
    # nessun dato disponibile, nemmeno stale
    snap.mark_error(category, message, state=STATE_UNAVAILABLE)
    return False


def _install(snap: Snapshot, spec: FeedSpec, parsed_data: list, source_url: str,
             saved_at: datetime, *, state: str, error_category: str = "", error_message: str = "") -> None:
    built = spec.build(parsed_data)
    meta = SnapshotMeta(
        state=state, loaded_at=saved_at, entry_count=len(parsed_data),
        source=source_url, last_error_category=error_category, last_error_message=error_message,
    )
    snap.swap(built, meta=meta)


def register_jobs() -> None:
    """Registra un IntelJob auto=True per ciascun feed — chiamato una volta all'avvio."""
    from core.intel import runner as intel_runner
    from utils.config import settings as _settings
    for name in FEEDS:
        intel_runner.register(intel_runner.IntelJob(
            name=name,
            run=lambda n=name: refresh(n, force=False),
            interval_minutes=_settings.INTEL_TICK_MINUTES,
            auto=True,
        ))


def ensure_loaded(name: str) -> None:
    """Lazy-load: se il feed non è mai stato caricato in questo processo, lo carica ora (comportamento pre-scheduler)."""
    snap = _snapshots[name]
    if snap.get() is None and not is_backed_off(name):
        refresh(name, force=False)


def data_freshness() -> list[dict]:
    """Blocco 'data_freshness' da includere nel risultato di un'analisi (badge di degrado, Wave 3)."""
    out = []
    for name, snap in _snapshots.items():
        meta = snap.meta
        age = None
        if meta.loaded_at:
            age = (datetime.now(timezone.utc) - meta.loaded_at).total_seconds() / 3600
        out.append({
            "name": name,
            "state": meta.state,
            "age_hours": round(age, 1) if age is not None else None,
            "entry_count": meta.entry_count,
        })
    return out
