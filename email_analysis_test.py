#!/usr/bin/env python3
"""
EMLyzer Email Threat Detection Accuracy Testing Script
Analyzes a diverse sample of emails to test detection capabilities
"""

import json
import os
import sys
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple
import httpx

# Configuration
EMAIL_DIR = Path(r"D:\Documenti\Email per test analisi")
OUTPUT_DIR = Path(r"D:\GitHub\EMLyzer\testing")
RESULTS_FILE = OUTPUT_DIR / "analysis_results.json"
API_BASE_URL = "http://localhost:8000/api"
SAMPLE_SIZE = 60
ANALYSIS_TIMEOUT = 120  # seconds
RATE_LIMIT_DELAY = 1.0  # seconds between requests

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_email_files() -> List[Tuple[Path, int]]:
    """List all .eml files with their sizes."""
    emails = []
    for file_path in EMAIL_DIR.glob("*.eml"):
        size = file_path.stat().st_size
        emails.append((file_path, size))
    return sorted(emails, key=lambda x: x[1])


def categorize_emails(emails: List[Tuple[Path, int]]) -> Dict[str, List[Tuple[Path, int]]]:
    """Categorize emails by size characteristics."""
    small = []  # < 10KB - likely spam/phishing
    medium = []  # 10KB - 100KB - mixed
    large = []  # > 100KB - likely attachments/complex

    for email, size in emails:
        if size < 10240:
            small.append((email, size))
        elif size < 102400:
            medium.append((email, size))
        else:
            large.append((email, size))

    return {
        "small": small,
        "medium": medium,
        "large": large,
    }


def select_diverse_sample(
    categories: Dict[str, List[Tuple[Path, int]]], target_count: int = 60
) -> List[Path]:
    """Select a diverse sample of emails across size categories."""
    selected = []

    # Try to distribute across categories: 30% small, 40% medium, 30% large
    small_count = int(target_count * 0.30)
    medium_count = int(target_count * 0.40)
    large_count = target_count - small_count - medium_count

    # Adjust if we don't have enough in each category
    small_available = len(categories["small"])
    medium_available = len(categories["medium"])
    large_available = len(categories["large"])

    # Select from small
    step_small = max(1, small_available // small_count) if small_count > 0 else 1
    selected.extend([f for f, _ in categories["small"][::step_small][:small_count]])

    # Select from medium
    step_medium = max(1, medium_available // medium_count) if medium_count > 0 else 1
    selected.extend([f for f, _ in categories["medium"][::step_medium][:medium_count]])

    # Select from large
    step_large = max(1, large_available // large_count) if large_count > 0 else 1
    selected.extend([f for f, _ in categories["large"][::step_large][:large_count]])

    return selected[: target_count]


async def upload_email(client: httpx.AsyncClient, file_path: Path) -> Dict[str, Any]:
    """Upload an email file to EMLyzer."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "message/rfc822")}
            response = await client.post(
                f"{API_BASE_URL}/upload/",
                files=files,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return {"success": True, "job_id": data.get("job_id"), "error": None}
    except Exception as e:
        return {"success": False, "job_id": None, "error": str(e)}


async def run_analysis(client: httpx.AsyncClient, job_id: str) -> Dict[str, Any]:
    """Run analysis for an uploaded email."""
    try:
        response = await client.post(
            f"{API_BASE_URL}/analysis/{job_id}",
            timeout=ANALYSIS_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "success": False}


async def get_analysis_status(client: httpx.AsyncClient, job_id: str) -> Dict[str, Any]:
    """Get current analysis status."""
    try:
        response = await client.get(
            f"{API_BASE_URL}/analysis/{job_id}",
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


async def analyze_email(
    client: httpx.AsyncClient, file_path: Path, retry_count: int = 3
) -> Dict[str, Any]:
    """Complete workflow: upload, analyze, and collect results."""
    filename = file_path.name

    print(f"[{time.strftime('%H:%M:%S')}] Processing {filename}...", end=" ")
    sys.stdout.flush()

    # Upload
    upload_result = await upload_email(client, file_path)
    if not upload_result["success"]:
        print(f"UPLOAD FAILED: {upload_result['error']}")
        return {
            "filename": filename,
            "file_size_bytes": file_path.stat().st_size,
            "success": False,
            "error": f"Upload failed: {upload_result['error']}",
        }

    job_id = upload_result["job_id"]
    await asyncio.sleep(RATE_LIMIT_DELAY)

    # Run analysis
    print(f"job={job_id} analyzing...", end=" ")
    sys.stdout.flush()

    analysis_result = await run_analysis(client, job_id)
    if "error" in analysis_result:
        print(f"ANALYSIS FAILED: {analysis_result['error']}")
        return {
            "filename": filename,
            "file_size_bytes": file_path.stat().st_size,
            "job_id": job_id,
            "success": False,
            "error": f"Analysis failed: {analysis_result['error']}",
        }

    await asyncio.sleep(RATE_LIMIT_DELAY)

    # Extract key results
    result = {
        "filename": filename,
        "file_size_bytes": file_path.stat().st_size,
        "job_id": job_id,
        "success": True,
        "risk_score": analysis_result.get("risk_score"),
        "risk_label": analysis_result.get("risk_label"),
        "risk_explanation": analysis_result.get("risk_explanation"),
        "detected_indicators": {
            "header_findings": len(analysis_result.get("header_indicators", {}).get("findings", [])),
            "body_findings": len(analysis_result.get("body_indicators", {}).get("findings", [])),
            "url_findings": len(analysis_result.get("url_indicators", {}).get("findings", [])),
            "attachment_findings": len(
                analysis_result.get("attachment_indicators", {}).get("findings", [])
            ),
        },
        "mail_from": analysis_result.get("mail_from"),
        "mail_to": analysis_result.get("mail_to"),
        "subject": analysis_result.get("subject"),
    }

    # Check reputation status
    reputation_results = analysis_result.get("reputation_results", {})
    if reputation_results:
        result["reputation_phase"] = reputation_results.get("reputation_phase", "unknown")
        result["reputation_ready"] = reputation_results.get("reputation_phase") == "complete"
    else:
        result["reputation_phase"] = "none"
        result["reputation_ready"] = False

    print(f"risk={result['risk_label']} ({result['risk_score']:.1f}) rep={result['reputation_phase']}")
    return result


async def main():
    """Main analysis workflow."""
    print("=" * 80)
    print("EMLyzer Email Threat Detection Accuracy Testing")
    print("=" * 80)

    # Get email files
    print("\nDiscovering email files...")
    all_emails = get_email_files()
    print(f"Found {len(all_emails)} .eml files")

    # Categorize
    print("\nCategorizing by size...")
    categories = categorize_emails(all_emails)
    print(f"  Small (<10KB): {len(categories['small'])} emails")
    print(f"  Medium (10KB-100KB): {len(categories['medium'])} emails")
    print(f"  Large (>100KB): {len(categories['large'])} emails")

    # Select diverse sample
    print(f"\nSelecting diverse sample of {SAMPLE_SIZE} emails...")
    selected_emails = select_diverse_sample(categories, SAMPLE_SIZE)
    print(f"Selected {len(selected_emails)} emails for analysis")

    # Analyze with httpx
    results = []
    start_time = time.time()

    print(f"\nStarting analysis (timeout: {ANALYSIS_TIMEOUT}s, rate limit: {RATE_LIMIT_DELAY}s)...")
    print("-" * 80)

    async with httpx.AsyncClient() as client:
        for i, email_path in enumerate(selected_emails, 1):
            print(f"[{i:2d}/{len(selected_emails)}] ", end="")
            result = await analyze_email(client, email_path)
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
    print(f"Success rate: {len(successful) / len(results) * 100:.1f}%")
    print(f"Total time: {elapsed:.1f}s")
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

        # Reputation status
        print("\nReputation Service Status:")
        rep_complete = sum(1 for r in successful if r.get("reputation_ready"))
        rep_pending = sum(1 for r in successful if r.get("reputation_phase") == "pending")
        rep_none = sum(1 for r in successful if r.get("reputation_phase") == "none")

        print(f"  Complete: {rep_complete:3d} ({rep_complete / len(successful) * 100:.1f}%)")
        print(f"  Pending:  {rep_pending:3d} ({rep_pending / len(successful) * 100:.1f}%)")
        print(f"  None:     {rep_none:3d} ({rep_none / len(successful) * 100:.1f}%)")

    if failed:
        print("\nFailed Analyses:")
        for r in failed[:10]:  # Show first 10 failures
            print(f"  {r['filename']:40s}: {r['error']}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more failures")

    # Save results
    print(f"\nSaving results to {RESULTS_FILE}...")
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_samples": len(results),
                    "successful": len(successful),
                    "failed": len(failed),
                    "total_time_seconds": elapsed,
                    "average_time_per_email": elapsed / len(results),
                },
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Results saved: {RESULTS_FILE}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
