#!/usr/bin/env python3
"""
Direct Email Analysis Test - Uses EMLyzer modules directly without server
Analyzes emails using the core analysis pipeline
"""

import sys
import json
import time
import asyncio
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


async def main():
    """Main analysis workflow."""
    print("=" * 80)
    print("EMLyzer Email Threat Detection Accuracy Testing")
    print("Direct Module Analysis (No Server Required)")
    print("=" * 80)

    try:
        # Import EMLyzer modules
        print("\nImporting EMLyzer modules...")
        from core.analysis.email_parser import parse_email_file
        from core.analysis.header_analyzer import analyze_headers
        from core.analysis.body_analyzer import analyze_body
        from core.analysis.url_analyzer import analyze_urls
        from core.analysis.attachment_analyzer import analyze_attachments
        from core.analysis.scorer import compute_risk_score
        from utils.config import settings

        print(f"  EMLyzer v{settings.VERSION}")
        print(f"  DEBUG: {settings.DEBUG}")

        # Get email files
        print("\nDiscovering email files...")
        all_emails = sorted(
            [(f, f.stat().st_size) for f in EMAIL_DIR.glob("*.eml")],
            key=lambda x: x[1],
        )
        print(f"Found {len(all_emails)} .eml files")

        if len(all_emails) == 0:
            print(f"ERROR: No .eml files found in {EMAIL_DIR}")
            return 1

        # Categorize by size
        print("\nCategorizing by size...")
        small = [f for f, size in all_emails if size < 10240]
        medium = [f for f, size in all_emails if 10240 <= size < 102400]
        large = [f for f, size in all_emails if size >= 102400]

        print(f"  Small (<10KB):       {len(small):3d} emails")
        print(f"  Medium (10-100KB):   {len(medium):3d} emails")
        print(f"  Large (>100KB):      {len(large):3d} emails")

        # Select diverse sample
        print(f"\nSelecting diverse sample of {SAMPLE_SIZE} emails...")
        selected = []

        # Distribute: 30% small, 40% medium, 30% large
        small_target = int(SAMPLE_SIZE * 0.30)
        medium_target = int(SAMPLE_SIZE * 0.40)
        large_target = SAMPLE_SIZE - small_target - medium_target

        if len(small) > 0:
            step = max(1, len(small) // small_target) if small_target > 0 else 1
            selected.extend(small[::step][:small_target])

        if len(medium) > 0:
            step = max(1, len(medium) // medium_target) if medium_target > 0 else 1
            selected.extend(medium[::step][:medium_target])

        if len(large) > 0:
            step = max(1, len(large) // large_target) if large_target > 0 else 1
            selected.extend(large[::step][:large_target])

        selected = selected[:SAMPLE_SIZE]
        print(f"Selected {len(selected)} emails for analysis")

        # Analyze emails
        results = []
        start_time = time.time()

        print(f"\nStarting analysis...")
        print("-" * 80)

        for i, email_path in enumerate(selected, 1):
            filename = email_path.name
            file_size = email_path.stat().st_size

            print(f"[{i:2d}/{len(selected)}] {filename:45s} ({file_size:8d} bytes) ", end="", flush=True)

            try:
                # Parse email
                parsed = parse_email_file(str(email_path))

                # Run analysis modules
                header_result = analyze_headers(parsed)
                body_result = analyze_body(parsed)
                url_result = analyze_urls(parsed)
                attachment_result = analyze_attachments(parsed)

                # Compute risk score
                risk_data = compute_risk_score(
                    header_result=header_result,
                    body_result=body_result,
                    url_result=url_result,
                    attachment_result=attachment_result,
                )

                result = {
                    "filename": filename,
                    "file_size_bytes": file_size,
                    "success": True,
                    "risk_score": risk_data.score,
                    "risk_label": risk_data.label,
                    "risk_explanation": risk_data.explanation,
                    "detected_indicators": {
                        "header_findings": len(header_result.findings),
                        "body_findings": len(body_result.findings),
                        "url_findings": sum(len(u.findings) for u in url_result.urls),
                        "attachment_findings": sum(len(a.findings) for a in attachment_result.attachments),
                    },
                    "mail_from": parsed.mail_from,
                    "mail_to": parsed.mail_to,
                    "subject": parsed.mail_subject,
                }

                print(f"✓ {result['risk_label'].upper():8s} ({result['risk_score']:5.1f})")
                results.append(result)

            except Exception as e:
                error_msg = str(e)[:100]
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

        print(f"\nTotal samples analyzed: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        if results:
            print(f"Success rate: {len(successful) / len(results) * 100:.1f}%")
        print(f"Total time: {elapsed:.1f}s")
        if results:
            print(f"Average time per email: {elapsed / len(results):.1f}s")

        if successful:
            # Risk distribution
            print("\nRisk Level Distribution:")
            risk_counts = {}
            for r in successful:
                label = r.get("risk_label", "unknown")
                risk_counts[label] = risk_counts.get(label, 0) + 1

            for label in ["low", "medium", "high", "critical"]:
                count = risk_counts.get(label, 0)
                pct = count / len(successful) * 100 if successful else 0
                print(f"  {label.upper():8s}: {count:3d} ({pct:5.1f}%)")

            # Indicator detection
            print("\nDetected Indicators (successful analyses):")
            header_total = sum(r["detected_indicators"]["header_findings"] for r in successful)
            body_total = sum(r["detected_indicators"]["body_findings"] for r in successful)
            url_total = sum(r["detected_indicators"]["url_findings"] for r in successful)
            attach_total = sum(r["detected_indicators"]["attachment_findings"] for r in successful)

            print(f"  Header findings: {header_total:4d} (avg {header_total / len(successful):.2f})")
            print(f"  Body findings:   {body_total:4d} (avg {body_total / len(successful):.2f})")
            print(f"  URL findings:    {url_total:4d} (avg {url_total / len(successful):.2f})")
            print(f"  Attachment findings: {attach_total:4d} (avg {attach_total / len(successful):.2f})")

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
                        "total_time_seconds": elapsed,
                        "average_time_per_email": elapsed / len(results) if results else 0,
                    },
                    "results": results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print(f"Results saved: {RESULTS_FILE}")
        print("\n" + "=" * 80)
        return 0

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
