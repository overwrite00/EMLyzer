#!/usr/bin/env python3
"""
EMLyzer Email Analysis Test - Direct Analysis
Tests EMLyzer's threat detection on a diverse sample of 60 emails
"""

import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Configuration
EMAIL_DIR = Path(r"D:\Documenti\Email per test analisi")
OUTPUT_DIR = Path(__file__).parent / "testing"
RESULTS_FILE = OUTPUT_DIR / "analysis_results.json"
SAMPLE_SIZE = 60

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_email_files() -> List[Tuple[Path, int]]:
    """List all .eml files with sizes."""
    emails = []
    for file_path in EMAIL_DIR.glob("*.eml"):
        size = file_path.stat().st_size
        emails.append((file_path, size))
    return sorted(emails, key=lambda x: x[1])


def categorize_emails(emails: List[Tuple[Path, int]]) -> Dict[str, List[Path]]:
    """Categorize emails by size."""
    small = []      # < 10KB
    medium = []     # 10KB - 100KB
    large = []      # > 100KB

    for email, size in emails:
        if size < 10240:
            small.append(email)
        elif size < 102400:
            medium.append(email)
        else:
            large.append(email)

    return {
        "small": small,
        "medium": medium,
        "large": large,
    }


def select_diverse_sample(categories: Dict[str, List[Path]], target: int = 60) -> List[Path]:
    """Select diverse sample across categories."""
    selected = []

    # Distribution: 30% small, 40% medium, 30% large
    small_target = int(target * 0.30)
    medium_target = int(target * 0.40)
    large_target = target - small_target - medium_target

    # Select from each category with even spacing
    for category, count in [
        ("small", small_target),
        ("medium", medium_target),
        ("large", large_target),
    ]:
        files = categories[category]
        if files and count > 0:
            step = max(1, len(files) // count)
            selected.extend(files[::step][:count])

    return selected[:target]


def main():
    """Main analysis workflow."""
    print("=" * 80)
    print("EMLyzer Email Threat Detection Analysis")
    print("=" * 80)

    # Import EMLyzer modules
    print("\nImporting EMLyzer modules...")
    try:
        from core.analysis.email_parser import parse_email_file
        from core.analysis.header_analyzer import analyze_headers
        from core.analysis.body_analyzer import analyze_body
        from core.analysis.url_analyzer import analyze_urls
        from core.analysis.attachment_analyzer import analyze_attachments
        from core.analysis.scorer import compute_risk_score
        from utils.config import settings

        print(f"  EMLyzer v{settings.VERSION}")
    except ImportError as e:
        print(f"ERROR: Failed to import EMLyzer modules: {e}")
        return 1

    # Get email files
    print("\nDiscovering email files...")
    all_emails = get_email_files()
    print(f"Found {len(all_emails)} .eml files")

    if not all_emails:
        print(f"ERROR: No .eml files found in {EMAIL_DIR}")
        return 1

    # Categorize
    print("\nCategorizing by size...")
    categories = categorize_emails(all_emails)
    print(f"  Small (<10KB):     {len(categories['small']):3d}")
    print(f"  Medium (10-100KB): {len(categories['medium']):3d}")
    print(f"  Large (>100KB):    {len(categories['large']):3d}")

    # Select sample
    print(f"\nSelecting {SAMPLE_SIZE} diverse samples...")
    selected = select_diverse_sample(categories, SAMPLE_SIZE)
    print(f"Selected {len(selected)} emails for analysis")

    # Analyze
    results = []
    start_time = time.time()
    print(f"\nAnalyzing {len(selected)} emails...")
    print("-" * 80)

    for i, email_path in enumerate(selected, 1):
        filename = email_path.name
        file_size = email_path.stat().st_size
        print(f"[{i:2d}/{len(selected)}] {filename:45s} ({file_size:8d} B) ", end="", flush=True)

        try:
            # Parse and analyze
            parsed = parse_email_file(str(email_path))
            header_result = analyze_headers(parsed)
            body_result = analyze_body(parsed)
            url_result = analyze_urls(body_result.extracted_urls)
            attachment_result = analyze_attachments(parsed.attachments)
            risk_data = compute_risk_score(header_result, body_result, url_result, attachment_result)

            # Collect results
            result = {
                "filename": filename,
                "file_size_bytes": file_size,
                "success": True,
                "risk_score": float(risk_data.score),
                "risk_label": risk_data.label,
                "risk_explanation": [str(e) for e in risk_data.explanation],
                "detected_indicators": {
                    "header_findings": len(header_result.findings),
                    "body_findings": len(body_result.findings),
                    "url_findings": sum(len(u.findings) for u in url_result.urls),
                    "attachment_findings": sum(len(a.findings) for a in attachment_result.attachments),
                    "total_urls": url_result.total_urls,
                    "total_attachments": attachment_result.total_attachments,
                },
                "email_metadata": {
                    "from": parsed.mail_from,
                    "to": parsed.mail_to,
                    "subject": parsed.mail_subject,
                },
            }
            results.append(result)
            print(f"✓ {risk_data.label.upper():8s} ({risk_data.score:5.1f})")

        except Exception as e:
            error_msg = str(e)[:80]
            print(f"✗ ERROR: {error_msg}")
            result = {
                "filename": filename,
                "file_size_bytes": file_size,
                "success": False,
                "error": str(e),
            }
            results.append(result)

    elapsed = time.time() - start_time
    print("-" * 80)

    # Statistics
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"\nTotal samples: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    if results:
        print(f"Success rate: {len(successful) / len(results) * 100:.1f}%")
    print(f"Total time: {elapsed:.1f}s")
    if results:
        print(f"Average time per email: {elapsed / len(results):.2f}s")

    if successful:
        # Risk distribution
        print("\nRisk Level Distribution:")
        risk_counts = {}
        for r in successful:
            label = r.get("risk_label", "unknown")
            risk_counts[label] = risk_counts.get(label, 0) + 1

        total_successful = len(successful)
        for label in ["low", "medium", "high", "critical"]:
            count = risk_counts.get(label, 0)
            pct = count / total_successful * 100 if total_successful else 0
            print(f"  {label.upper():8s}: {count:3d} ({pct:5.1f}%)")

        # Indicators detected
        print("\nDetected Indicators Summary:")
        header_total = sum(r["detected_indicators"]["header_findings"] for r in successful)
        body_total = sum(r["detected_indicators"]["body_findings"] for r in successful)
        url_total = sum(r["detected_indicators"]["url_findings"] for r in successful)
        attach_total = sum(r["detected_indicators"]["attachment_findings"] for r in successful)
        urls_total = sum(r["detected_indicators"]["total_urls"] for r in successful)
        attachments_total = sum(r["detected_indicators"]["total_attachments"] for r in successful)

        print(f"  Header findings:      {header_total:4d} (avg {header_total / total_successful:.2f})")
        print(f"  Body findings:        {body_total:4d} (avg {body_total / total_successful:.2f})")
        print(f"  URL findings:         {url_total:4d} (in {urls_total} total URLs)")
        print(f"  Attachment findings:  {attach_total:4d} (in {attachments_total} total files)")

        # Risk score stats
        scores = [r["risk_score"] for r in successful]
        print(f"\nRisk Score Statistics:")
        print(f"  Min: {min(scores):.1f}")
        print(f"  Max: {max(scores):.1f}")
        print(f"  Avg: {sum(scores) / len(scores):.1f}")
        print(f"  Med: {sorted(scores)[len(scores)//2]:.1f}")

    if failed:
        print("\nFailed Analyses (first 10):")
        for r in failed[:10]:
            print(f"  {r['filename']:40s}: {r['error'][:60]}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more failures")

    # Save results
    print(f"\nSaving results to {RESULTS_FILE}...")
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "emlyzer_version": settings.VERSION,
                    "total_samples": len(results),
                    "successful": len(successful),
                    "failed": len(failed),
                    "success_rate": len(successful) / len(results) if results else 0,
                    "total_time_seconds": round(elapsed, 2),
                    "average_time_per_email": round(elapsed / len(results), 2) if results else 0,
                },
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Results saved successfully!")
    print(f"  File: {RESULTS_FILE}")
    print(f"  Size: {RESULTS_FILE.stat().st_size:,} bytes")
    print("\n" + "=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
