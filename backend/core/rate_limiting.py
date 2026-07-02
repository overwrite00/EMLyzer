"""
Rate limiting configuration for EMLyzer.

Protegge contro DoS e abusi: upload massiccio, analisi spam, bulk delete.
Usa in-memory limiter (slowapi) con chiave per IP remoto.

Limiti per endpoint:
- upload (25MB): 10/min per IP (prevenire upload massiccio)
- analysis: 10/min per IP (analisi CPU-intensiva)
- manual: 10/min per IP
- bulk-delete: 5/min per IP (operazione distruttiva)
- list/read: 30/min per IP (default)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Singleton limiter condiviso tra main.py e endpoint modules
limiter = Limiter(key_func=get_remote_address)
