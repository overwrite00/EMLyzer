#!/usr/bin/env python3
"""Quick test to verify EMLyzer module imports work"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

try:
    from utils.config import settings
    print(f"✓ Config imported: EMLyzer v{settings.VERSION}")

    from core.analysis.email_parser import parse_email_file
    print(f"✓ Email parser imported")

    from core.analysis.header_analyzer import analyze_headers
    print(f"✓ Header analyzer imported")

    from core.analysis.body_analyzer import analyze_body
    print(f"✓ Body analyzer imported")

    from core.analysis.url_analyzer import analyze_urls
    print(f"✓ URL analyzer imported")

    from core.analysis.attachment_analyzer import analyze_attachments
    print(f"✓ Attachment analyzer imported")

    from core.analysis.scorer import compute_risk_score
    print(f"✓ Scorer imported")

    print("\n✓ All imports successful!")

except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
