"""
core/intel/fetch.py

Download difensivo per feed/bollettini esterni. Sostituisce l'uso diretto di
`resp.text` sui download di feed in core/reputation/connectors.py, che oggi
carica l'intero corpo in RAM senza alcun limite.

Protezioni:
- stream=True + cap esplicito sui byte (max_bytes), abort a chunk.
- Per contenuti gzip il cap si applica ai byte DECOMPRESSI (difesa da zip-bomb).
- verify TLS mai disabilitato; redirect limitati; rifiuto di downgrade
  https->http; rifiuto di redirect verso IP privati/loopback/link-local
  (SSRF residuo — un endpoint di refresh che segue redirect arbitrari verso
  169.254.169.254 o 127.0.0.1 sarebbe comunque SSRF anche con URL whitelisted).
- Timeout (connect, read) dedicato, diverso da REQUEST_TIMEOUT (8s, tarato
  per le API di reputazione per-singolo-IOC, non per download di decine di MB).
- Deadline assoluta sull'intero fetch, indipendente dal timeout di rete:
  un server che invia 1 byte ogni pochi secondi non farebbe scattare il
  read-timeout ma terrebbe un thread (e un lock) impegnati indefinitamente.
- Errori sempre mappati su categorie note, mai un `str(exc)` grezzo esposto
  in un campo user-facing (può contenere l'URL completo con query string).

Gli URL dei feed sono sempre costanti nel codice chiamante (FeedSpec.url),
mai accettati da environment/API — questo modulo non introduce un modo di
scaricare un URL arbitrario.
"""

from __future__ import annotations

import gzip
import ipaddress
import socket
import time
import urllib.parse
from dataclasses import dataclass

import requests

from utils.config import settings


class FetchError(Exception):
    """Errore di fetch categorizzato — mai il messaggio grezzo dell'eccezione originale."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass
class FetchResult:
    content: bytes
    final_url: str
    status_code: int


def _is_unsafe_host(hostname: str) -> bool:
    """True se l'host risolve (o è già) un IP privato/loopback/link-local/riservato."""
    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False  # non risolvibile: lasciamo che sia requests a fallire più avanti
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return True
        except ValueError:
            continue
    return False


def _check_url_safety(url: str, *, previous_scheme: str | None = None) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        if previous_scheme == "https" and parsed.scheme == "http":
            raise FetchError("insecure_redirect", "Redirect da https a http rifiutato")
        if parsed.scheme != "http":
            raise FetchError("invalid_scheme", f"Schema non supportato: {parsed.scheme}")
    if _is_unsafe_host(parsed.hostname or ""):
        raise FetchError("ssrf_blocked", "Host risolve a un indirizzo privato/loopback/riservato")


def fetch_bytes(
    url: str,
    *,
    max_bytes: int,
    user_agent: str,
    allow_gzip: bool = False,
    max_redirects: int = 5,
    timeout: tuple[float, float] | None = None,
    deadline: float | None = None,
) -> FetchResult:
    """
    Scarica url in streaming con cap di dimensione, deadline assoluta e
    guardie anti-SSRF sui redirect. Solleva FetchError su qualunque anomalia,
    mai un'eccezione requests grezza (che potrebbe contenere l'URL con query
    string in un messaggio poi esposto all'utente).
    """
    timeout = timeout or (settings.INTEL_DOWNLOAD_TIMEOUT_CONNECT, settings.INTEL_DOWNLOAD_TIMEOUT_READ)
    deadline = deadline if deadline is not None else settings.INTEL_DOWNLOAD_DEADLINE
    started = time.monotonic()

    _check_url_safety(url)

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": user_agent},
            stream=True,
            timeout=timeout,
            verify=True,                 # mai disabilitare TLS verification
            allow_redirects=False,       # i redirect si seguono a mano per validare ogni hop
        )
    except requests.exceptions.Timeout as e:
        raise FetchError("timeout", "Timeout durante la connessione") from e
    except requests.exceptions.ConnectionError as e:
        raise FetchError("connection_error", "Impossibile raggiungere l'host") from e
    except requests.exceptions.RequestException as e:
        raise FetchError("unknown_error", "Errore di rete") from e

    hops = 0
    current_scheme = urllib.parse.urlparse(url).scheme
    while resp.is_redirect and hops < max_redirects:
        if time.monotonic() - started > deadline:
            raise FetchError("deadline_exceeded", "Deadline superata durante i redirect")
        location = resp.headers.get("Location", "")
        if not location:
            break
        next_url = urllib.parse.urljoin(resp.url, location)
        _check_url_safety(next_url, previous_scheme=current_scheme)
        current_scheme = urllib.parse.urlparse(next_url).scheme
        try:
            resp = requests.get(
                next_url, headers={"User-Agent": user_agent}, stream=True,
                timeout=timeout, verify=True, allow_redirects=False,
            )
        except requests.exceptions.RequestException as e:
            raise FetchError("connection_error", "Errore di rete durante il redirect") from e
        hops += 1

    if resp.is_redirect:
        raise FetchError("too_many_redirects", "Troppi redirect")

    if resp.status_code >= 400:
        raise FetchError("http_error", f"HTTP {resp.status_code}")

    content_length = resp.headers.get("Content-Length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise FetchError("too_large", f"Content-Length {content_length} supera il limite {max_bytes}")
        except ValueError:
            pass

    chunks = bytearray()
    try:
        for chunk in resp.iter_content(chunk_size=65536):
            if time.monotonic() - started > deadline:
                raise FetchError("deadline_exceeded", "Deadline superata durante il download")
            chunks.extend(chunk)
            if len(chunks) > max_bytes:
                raise FetchError("too_large", f"Corpo oltre il limite di {max_bytes} byte")
    except requests.exceptions.RequestException as e:
        raise FetchError("connection_error", "Connessione interrotta durante il download") from e
    finally:
        resp.close()

    body = bytes(chunks)

    if allow_gzip:
        try:
            decompressed = gzip.decompress(body)
        except OSError as e:
            raise FetchError("malformed_response", "Corpo gzip non valido") from e
        if len(decompressed) > max_bytes:
            raise FetchError("too_large", "Corpo decompresso oltre il limite (possibile zip-bomb)")
        body = decompressed

    return FetchResult(content=body, final_url=resp.url, status_code=resp.status_code)
