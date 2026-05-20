#!/usr/bin/env python3
"""
Accuracy Validation Runner — EMLyzer Detection Testing Framework

This script loads the test sample emails, runs them through EMLyzer's analyzers,
and populates the accuracy_validation.json report with actual results.

Usage:
    python testing/run_accuracy_validation.py
"""

import sys
import json
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from core.analysis.email_parser import parse_email_file
from core.analysis.header_analyzer import analyze_headers
from core.analysis.body_analyzer import analyze_body
from core.analysis.url_analyzer import analyze_urls
from core.analysis.attachment_analyzer import analyze_attachments
from core.analysis.scorer import compute_risk_score


SAMPLES_DIR = Path(__file__).parent.parent / "samples"
VALIDATION_FILE = Path(__file__).parent / "accuracy_validation.json"


def dataclass_to_dict(obj: Any) -> Any:
    """Convert dataclass to dict recursively."""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field in obj.__dataclass_fields__:
            val = getattr(obj, field)
            result[field] = dataclass_to_dict(val)
        return result
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    else:
        return obj


def run_analysis(sample_filename: str, test_id: str) -> dict[str, Any]:
    """Run full analysis pipeline on a sample email."""
    sample_path = SAMPLES_DIR / sample_filename

    if not sample_path.exists():
        return {
            "status": "error",
            "error": f"Sample not found: {sample_path}"
        }

    print(f"\n{'='*60}")
    print(f"Analyzing: {sample_filename} (Test ID: {test_id})")
    print(f"{'='*60}")

    try:
        # 1. Parse email
        raw = sample_path.read_bytes()
        parsed = parse_email_file(raw, sample_filename)
        print(f"✓ Email parsed: {parsed.mail_from} → {parsed.mail_to}")

        # 2. Analyze headers
        header_result = analyze_headers(parsed)
        header_findings_count = len(header_result.findings)
        header_high = sum(1 for f in header_result.findings if f.severity == "high")
        print(f"✓ Header analysis: {header_findings_count} findings ({header_high} HIGH)")

        # 3. Analyze body
        body_result = analyze_body(parsed)
        body_findings_count = len(body_result.findings)
        body_high = sum(1 for f in body_result.findings if f.severity == "high")
        print(f"✓ Body analysis: {body_findings_count} findings ({body_high} HIGH)")
        print(f"  - Urgency count: {body_result.urgency_count}")
        print(f"  - Phishing CTA count: {body_result.phishing_cta_count}")
        print(f"  - Credential keywords: {body_result.credential_keyword_count}")
        print(f"  - Forms found: {body_result.forms_found}")
        print(f"  - Obfuscated links: {len(body_result.obfuscated_links)}")

        # 4. Analyze URLs
        url_result = analyze_urls(parsed)
        url_findings_count = sum(len(u.findings) for u in url_result.urls)
        url_high = sum(1 for u in url_result.urls
                       for f in u.findings if f.get("severity") == "high")
        print(f"✓ URL analysis: {len(url_result.urls)} URLs, {url_findings_count} findings ({url_high} HIGH)")

        # 5. Analyze attachments
        attachment_result = analyze_attachments(parsed)
        att_findings_count = sum(len(a.findings) for a in attachment_result.attachments)
        print(f"✓ Attachment analysis: {len(attachment_result.attachments)} attachments, {att_findings_count} findings")

        # 6. Compute risk score
        risk_score = compute_risk_score(header_result, body_result, url_result, attachment_result)
        print(f"✓ Risk score computed: {risk_score.score:.1f} ({risk_score.label.upper()})")

        # Compile result
        result = {
            "status": "success",
            "test_id": test_id,
            "filename": sample_filename,
            "parsed_email": {
                "mail_from": parsed.mail_from,
                "mail_to": parsed.mail_to,
                "mail_subject": parsed.mail_subject,
                "mail_date": parsed.mail_date,
                "spf_result": parsed.spf_result,
                "dkim_result": parsed.dkim_result,
                "dmarc_result": parsed.dmarc_result,
                "x_originating_ip": parsed.x_originating_ip,
                "x_campaign_id": parsed.x_campaign_id,
                "file_hash_sha256": parsed.file_hash_sha256,
            },
            "analysis_results": {
                "header": {
                    "findings_count": header_findings_count,
                    "high_count": header_high,
                    "medium_count": sum(1 for f in header_result.findings if f.severity == "medium"),
                    "low_count": sum(1 for f in header_result.findings if f.severity == "low"),
                    "findings": [dataclass_to_dict(f) for f in header_result.findings[:10]],  # Top 10
                },
                "body": {
                    "findings_count": body_findings_count,
                    "high_count": body_high,
                    "medium_count": sum(1 for f in body_result.findings if f.severity == "medium"),
                    "low_count": sum(1 for f in body_result.findings if f.severity == "low"),
                    "urgency_count": body_result.urgency_count,
                    "phishing_cta_count": body_result.phishing_cta_count,
                    "credential_keyword_count": body_result.credential_keyword_count,
                    "forms_found": body_result.forms_found,
                    "js_found": body_result.js_found,
                    "invisible_elements": body_result.invisible_elements,
                    "base64_inline_count": body_result.base64_inline_count,
                    "obfuscated_links": body_result.obfuscated_links,
                    "findings": [dataclass_to_dict(f) for f in body_result.findings[:10]],
                },
                "url": {
                    "urls_count": len(url_result.urls),
                    "findings_count": url_findings_count,
                    "high_count": url_high,
                    "urls": [
                        {
                            "original_url": u.original_url[:200],
                            "host": u.host,
                            "is_ip_address": u.is_ip_address,
                            "is_shortener": u.is_shortener,
                            "is_new_domain": u.is_new_domain,
                            "is_punycode": u.is_punycode,
                            "risk_score": u.risk_score,
                            "findings": u.findings[:3],
                        }
                        for u in url_result.urls[:5]
                    ]
                },
                "attachment": {
                    "attachments_count": len(attachment_result.attachments),
                    "findings_count": att_findings_count,
                    "attachments": [
                        {
                            "filename": a.filename,
                            "mime_type": a.mime_type,
                            "size_bytes": a.size_bytes,
                            "has_macro": a.has_macro,
                            "findings": [dataclass_to_dict(f) for f in a.findings[:3]],
                        }
                        for a in attachment_result.attachments
                    ]
                },
            },
            "risk_score": {
                "score": risk_score.score,
                "label": risk_score.label,
                "label_text": risk_score.label_text,
                "explanation": risk_score.explanation[:3],  # Top 3 reasons
                "contributions": [
                    {
                        "module": c.module,
                        "raw_score": c.raw_score,
                        "weighted_score": c.weighted_score,
                        "top_reasons": c.top_reasons[:2],
                    }
                    for c in risk_score.contributions
                ],
            },
        }

        return result

    except Exception as e:
        print(f"✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "test_id": test_id,
            "filename": sample_filename,
            "error": str(e),
        }


def main():
    """Run validation on all test samples."""
    print("\n" + "="*60)
    print("EMLyzer — Accuracy Validation Framework")
    print("="*60)

    # Load template validation file
    with open(VALIDATION_FILE, "r", encoding="utf-8") as f:
        validation = json.load(f)

    # Get test cases from template
    test_cases = validation.get("test_cases", [])

    # Run analysis for each test case
    analysis_results = {}
    for test_case in test_cases:
        test_id = test_case.get("id")
        filename = test_case.get("filename")

        result = run_analysis(filename, test_id)
        analysis_results[test_id] = result

    # Update validation file with results
    validation["actual_results"] = analysis_results

    # Calculate accuracy metrics
    phishing_results = analysis_results.get("TC_001", {})
    clean_results = analysis_results.get("TC_002", {})

    if phishing_results.get("status") == "success":
        phishing_score = phishing_results["risk_score"]["score"]
        phishing_label = phishing_results["risk_score"]["label"]
        validation["accuracy_assessment"] = {
            "phishing_detection": {
                "expected_label": "HIGH or CRITICAL",
                "actual_label": phishing_label.upper(),
                "actual_score": phishing_score,
                "test_passed": phishing_label in ["high", "critical"],
                "reasoning": f"Phishing sample scored {phishing_score:.1f} ({phishing_label})"
            }
        }

        if clean_results.get("status") == "success":
            clean_score = clean_results["risk_score"]["score"]
            clean_label = clean_results["risk_score"]["label"]
            validation["accuracy_assessment"]["clean_detection"] = {
                "expected_label": "LOW",
                "actual_label": clean_label.upper(),
                "actual_score": clean_score,
                "test_passed": clean_label == "low",
                "reasoning": f"Clean sample scored {clean_score:.1f} ({clean_label})"
            }

    # Save updated validation file
    with open(VALIDATION_FILE, "w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("Validation Results Saved")
    print(f"{'='*60}")
    print(f"Output: {VALIDATION_FILE}")
    print(f"Phishing test (TC_001): {phishing_results.get('status', 'unknown')}")
    if phishing_results.get("status") == "success":
        print(f"  Score: {phishing_results['risk_score']['score']:.1f} ({phishing_results['risk_score']['label']})")

    print(f"Clean test (TC_002): {clean_results.get('status', 'unknown')}")
    if clean_results.get("status") == "success":
        print(f"  Score: {clean_results['risk_score']['score']:.1f} ({clean_results['risk_score']['label']})")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
