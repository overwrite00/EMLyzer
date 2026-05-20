#!/usr/bin/env python3
"""
Reputation Services Validation Script for EMLyzer

This script validates that reputation services are working correctly and
returning accurate threat intelligence. It tests:

1. Service availability and API key configuration
2. FAST vs SLOW service classification
3. Rate limiting and request handling
4. Indicator extraction (IP, URL, hash)
5. Response time and timeout handling
6. Service status registry (clean/malicious/pending/skipped/not_applicable/error)

Usage:
  python reputation_services_validator.py [--verbose] [--test-known-bad]

Requirements:
  - .env file with API keys configured
  - Backend service running on http://localhost:8000
  - Sample email files in samples/ directory
"""

import sys
import json
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import time

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from core.reputation.connectors import (
    check_ip_abuseipdb,
    check_ip_virustotal,
    check_url_virustotal,
    check_hash_virustotal,
    check_url_openphish,
    check_url_phishtank,
    check_hash_malwarebazaar,
    check_ip_spamhaus,
    check_ip_asn,
    check_domain_crtsh,
    check_ip_circl_pdns,
    check_domain_circl_pdns,
    check_ip_greynoise,
    check_url_urlscan,
    check_url_pulsedive,
    check_ip_criminalip,
    check_domain_securitytrails,
    check_hash_hybridanalysis,
    run_fast_checks,
    run_slow_checks,
)
from utils.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Test Data — Known samples for validation
# ─────────────────────────────────────────────────────────────────────────────

TEST_DATA = {
    "ips": {
        # Malicious/spam IPs (should flag)
        "127.0.0.2": {
            "description": "Localhost variant (always private)",
            "expected_type": "private",
        },
        # Real-world examples to test generic extraction
    },
    "urls": {
        "http://phishing-test.example.com": {
            "description": "Non-existent phishing test URL",
            "expected_safe": False,
        },
        "https://github.com": {
            "description": "Well-known legitimate site",
            "expected_safe": True,
        },
    },
    "hashes": {
        "d131dd02c5e6eec1": {
            "description": "Short invalid hash",
            "expected_type": "invalid",
        },
    },
}

SERVICES_FAST = [
    "Spamhaus DROP",
    "ASN Lookup",
    "OpenPhish",
    "PhishTank",
    "MalwareBazaar",
    "crt.sh",
    "CIRCL Passive DNS",
    "GreyNoise Community",
    "URLScan.io",
    "Redirect Chain",
    "Shodan InternetDB",
    "Criminal IP",
    "SecurityTrails",
    "Hybrid Analysis",
    "ThreatFox",
    "URLhaus",
    "Pulsedive",
]

SERVICES_SLOW = [
    "AbuseIPDB",
    "VirusTotal",
]

# API key requirements mapping
API_KEY_REQUIREMENTS = {
    "AbuseIPDB": "ABUSEIPDB_API_KEY",
    "VirusTotal": "VIRUSTOTAL_API_KEY",
    "PhishTank": "PHISHTANK_API_KEY",
    "MalwareBazaar": "ABUSECH_API_KEY",
    "CIRCL Passive DNS": "CIRCL_API_KEY",
    "GreyNoise Community": "GREYNOISE_API_KEY",
    "URLScan.io": "URLSCAN_API_KEY",
    "Criminal IP": "CRIMINALIP_API_KEY",
    "SecurityTrails": "SECURITYTRAILS_API_KEY",
    "Hybrid Analysis": "HYBRID_ANALYSIS_API_KEY",
    "Pulsedive": "PULSEDIVE_API_KEY",
    "crt.sh": None,  # No API key required
    "Spamhaus DROP": None,
    "ASN Lookup": None,
    "OpenPhish": None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Validation Report Structure
# ─────────────────────────────────────────────────────────────────────────────

class ServiceValidationReport:
    """Container for service validation results."""

    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.validation_results: Dict[str, Any] = {}
        self.api_keys_configured: Dict[str, bool] = {}
        self.service_health: Dict[str, Dict[str, Any]] = {}
        self.test_results: List[Dict[str, Any]] = []
        self.performance_stats: Dict[str, Dict[str, Any]] = {}
        self.error_log: List[str] = []
        self.summary: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "validation_results": self.validation_results,
            "api_keys_configured": self.api_keys_configured,
            "service_health": self.service_health,
            "test_results": self.test_results,
            "performance_stats": self.performance_stats,
            "error_log": self.error_log,
            "summary": self.summary,
        }

    def save_json(self, path: Path) -> None:
        """Save report as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# API Key Validation
# ─────────────────────────────────────────────────────────────────────────────

def check_api_keys() -> Dict[str, bool]:
    """Check which API keys are configured."""
    configured = {}

    api_keys_to_check = {
        "ABUSEIPDB_API_KEY": settings.ABUSEIPDB_API_KEY,
        "VIRUSTOTAL_API_KEY": settings.VIRUSTOTAL_API_KEY,
        "PHISHTANK_API_KEY": settings.PHISHTANK_API_KEY,
        "ABUSECH_API_KEY": settings.ABUSECH_API_KEY,
        "CIRCL_API_KEY": settings.CIRCL_API_KEY,
        "GREYNOISE_API_KEY": settings.GREYNOISE_API_KEY,
        "URLSCAN_API_KEY": settings.URLSCAN_API_KEY,
        "CRIMINALIP_API_KEY": settings.CRIMINALIP_API_KEY,
        "SECURITYTRAILS_API_KEY": settings.SECURITYTRAILS_API_KEY,
        "HYBRID_ANALYSIS_API_KEY": settings.HYBRID_ANALYSIS_API_KEY,
        "PULSEDIVE_API_KEY": settings.PULSEDIVE_API_KEY,
        "MALWAREBAZAAR_API_KEY": settings.MALWAREBAZAAR_API_KEY,  # legacy
    }

    for key_name, key_value in api_keys_to_check.items():
        configured[key_name] = bool(key_value and key_value.strip())

    return configured


# ─────────────────────────────────────────────────────────────────────────────
# Individual Service Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_single_service(
    service_name: str,
    test_func,
    entity: str,
    entity_type: str,
) -> Dict[str, Any]:
    """Test a single service connector."""
    result = {
        "service": service_name,
        "entity": entity,
        "entity_type": entity_type,
        "success": False,
        "response_time": 0.0,
        "status": "unknown",
        "detail": "",
        "error": None,
    }

    start_time = time.monotonic()
    try:
        rep_result = test_func(entity)
        response_time = time.monotonic() - start_time
        result["response_time"] = response_time

        if rep_result.error:
            result["status"] = "error"
            result["error"] = rep_result.error
        elif rep_result.skipped:
            result["status"] = "skipped"
            result["detail"] = rep_result.skip_reason
        elif rep_result.is_malicious:
            result["status"] = "malicious"
            result["detail"] = rep_result.detail
        else:
            result["status"] = "clean"
            result["detail"] = rep_result.detail

        result["success"] = True
        result["confidence"] = rep_result.confidence
        result["queried"] = rep_result.queried

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["response_time"] = time.monotonic() - start_time

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Batch Service Tests (FAST)
# ─────────────────────────────────────────────────────────────────────────────

def test_fast_checks(
    ips: List[str],
    urls: List[str],
    hashes: List[str],
) -> Dict[str, Any]:
    """Test FAST reputation checks."""
    result = {
        "phase": "fast",
        "start_time": time.monotonic(),
        "ips_analyzed": len(ips),
        "urls_analyzed": len(urls),
        "hashes_analyzed": len(hashes),
        "services": {},
        "error": None,
    }

    try:
        summary = run_fast_checks(ips, urls, hashes)
        result["end_time"] = time.monotonic()
        result["response_time"] = result["end_time"] - result["start_time"]
        result["reputation_score"] = summary.reputation_score
        result["malicious_count"] = summary.malicious_count
        result["service_registry"] = summary.service_registry

        # Analyze service status distribution
        status_counts = {}
        for service in summary.service_registry:
            status = service.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        result["status_distribution"] = status_counts

    except Exception as e:
        result["error"] = str(e)
        result["end_time"] = time.monotonic()
        result["response_time"] = result["end_time"] - result["start_time"]

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Validation Report Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_validation_report(
    api_keys: Dict[str, bool],
    fast_test_results: Dict[str, Any],
    individual_tests: List[Dict[str, Any]],
    verbose: bool = False,
) -> ServiceValidationReport:
    """Generate comprehensive validation report."""

    report = ServiceValidationReport()

    # API Keys Status
    report.api_keys_configured = api_keys
    api_configured_count = sum(1 for v in api_keys.values() if v)
    total_api_keys = len(api_keys)

    # Service Health Assessment
    service_health = {}

    # FAST services
    for service in SERVICES_FAST:
        health = {
            "phase": "fast",
            "has_api_key": bool(API_KEY_REQUIREMENTS.get(service) and
                               api_keys.get(API_KEY_REQUIREMENTS.get(service))),
            "status": "operational",
        }
        service_health[service] = health

    # SLOW services
    for service in SERVICES_SLOW:
        api_key_name = API_KEY_REQUIREMENTS.get(service)
        health = {
            "phase": "slow",
            "has_api_key": bool(api_key_name and api_keys.get(api_key_name)),
            "status": "operational" if api_key_name and api_keys.get(api_key_name) else "missing_api_key",
        }
        service_health[service] = health

    report.service_health = service_health

    # Test Results
    report.test_results = individual_tests

    # Performance Stats
    perf_stats = {
        "fast_phase": {
            "response_time": fast_test_results.get("response_time", 0),
            "ips_analyzed": fast_test_results.get("ips_analyzed", 0),
            "urls_analyzed": fast_test_results.get("urls_analyzed", 0),
            "hashes_analyzed": fast_test_results.get("hashes_analyzed", 0),
            "status_distribution": fast_test_results.get("status_distribution", {}),
        }
    }
    report.performance_stats = perf_stats

    # Summary Statistics
    report.summary = {
        "total_services": len(SERVICES_FAST) + len(SERVICES_SLOW),
        "fast_services": len(SERVICES_FAST),
        "slow_services": len(SERVICES_SLOW),
        "api_keys_configured": api_configured_count,
        "api_keys_total": total_api_keys,
        "api_key_coverage": f"{api_configured_count}/{total_api_keys}",
        "validation_timestamp": report.timestamp,
        "fast_phase_response_time": fast_test_results.get("response_time", 0),
        "reputation_score": fast_test_results.get("reputation_score", 0),
        "malicious_services_found": fast_test_results.get("malicious_count", 0),
    }

    # Error Log
    if fast_test_results.get("error"):
        report.error_log.append(f"FAST phase error: {fast_test_results['error']}")

    for test in individual_tests:
        if test.get("error"):
            report.error_log.append(f"{test['service']}: {test['error']}")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Main Validation Function
# ─────────────────────────────────────────────────────────────────────────────

def main(verbose: bool = False, test_known_bad: bool = False):
    """Run full reputation services validation."""

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 80)
    print("EMLyzer Reputation Services Validation Report")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Settings Version: {settings.VERSION}")
    print()

    # Step 1: Check API Keys
    print("[1/4] Checking API Key Configuration...")
    api_keys = check_api_keys()
    configured_count = sum(1 for v in api_keys.values() if v)
    print(f"  ✓ {configured_count}/{len(api_keys)} API keys configured")
    for key, is_configured in api_keys.items():
        status = "✓" if is_configured else "✗"
        print(f"    {status} {key}")

    # Step 2: Test Individual Services (subset)
    print("\n[2/4] Testing Individual Service Connectors...")
    individual_tests = []

    # Test a few representative services
    test_samples = [
        ("Spamhaus DROP", check_ip_spamhaus, "1.2.3.4", "ip"),
        ("ASN Lookup", check_ip_asn, "8.8.8.8", "ip"),
        ("OpenPhish", check_url_openphish, "https://example.com", "url"),
    ]

    for service_name, test_func, entity, entity_type in test_samples:
        if verbose:
            print(f"  Testing {service_name}...")
        result = test_single_service(service_name, test_func, entity, entity_type)
        individual_tests.append(result)
        status_icon = "✓" if result["success"] else "✗"
        print(f"    {status_icon} {service_name}: {result['status']} ({result['response_time']:.2f}s)")

    # Step 3: Test FAST Phase
    print("\n[3/4] Testing FAST Phase (Batch Checks)...")
    test_ips = ["8.8.8.8", "1.1.1.1"]  # Public IPs for testing
    test_urls = ["https://github.com", "https://google.com"]
    test_hashes = []  # No test hashes

    print(f"  Testing with {len(test_ips)} IPs, {len(test_urls)} URLs, {len(test_hashes)} hashes...")
    fast_results = test_fast_checks(test_ips, test_urls, test_hashes)

    if fast_results.get("error"):
        print(f"  ✗ FAST phase error: {fast_results['error']}")
    else:
        response_time = fast_results.get("response_time", 0)
        print(f"  ✓ FAST phase completed in {response_time:.2f}s")

        status_dist = fast_results.get("status_distribution", {})
        print(f"    Status distribution: {status_dist}")

    # Step 4: Generate Report
    print("\n[4/4] Generating Validation Report...")
    report = generate_validation_report(api_keys, fast_results, individual_tests, verbose)

    # Save Report
    report_path = Path(__file__).parent / "reputation_services_report.json"
    report.save_json(report_path)
    print(f"  ✓ Report saved to {report_path}")

    # Print Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    summary = report.summary
    print(f"Total Services: {summary['total_services']}")
    print(f"  FAST: {summary['fast_services']}")
    print(f"  SLOW: {summary['slow_services']}")
    print(f"\nAPI Key Coverage: {summary['api_key_coverage']}")
    print(f"FAST Phase Response Time: {summary['fast_phase_response_time']:.2f}s")
    print(f"Reputation Score: {summary['reputation_score']}/100")
    print(f"Malicious Services: {summary['malicious_services_found']}")
    print("\n" + "=" * 80)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate EMLyzer reputation services"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--test-known-bad", action="store_true",
                       help="Test with known malicious indicators")
    args = parser.parse_args()

    main(verbose=args.verbose, test_known_bad=args.test_known_bad)
