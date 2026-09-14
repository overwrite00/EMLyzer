"""
core/intel — infrastruttura condivisa di Threat Intelligence.

Due domini, una meccanica:
- Reputation Feeds (feeds.py, Wave 2): IOC esterni nel percorso critico
  dell'analisi, refresh automatico.
- Known Campaigns / Bulletins (bulletins.py, Wave 7): dati curati dall'utente
  o bacheca di spunti, refresh su richiesta.

Moduli:
- cache.py:     TTL disk cache versionata, scrittura atomica.
- fetch.py:     download difensivo (size cap, timeout, redirect/SSRF guard).
- snapshot.py:  pattern build-then-swap per strutture in-memory ricaricabili.
- runs.py:      tracciamento delle esecuzioni recenti di un job (per /status).
"""
