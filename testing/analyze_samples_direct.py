#!/usr/bin/env python3
"""
Direct hands-on testing of EMLyzer with curl-based API calls.
"""

import os
import json
import subprocess
import time
import sys
from pathlib import Path
from collections import defaultdict

EMAIL_DIR = r"D:\Documenti\Email per test analisi"
OUTPUT_DIR = r"D:\GitHub\EMLyzer\testing"
API_BASE = "http://localhost:8000/api"

def select_diverse_samples(email_dir, count=15):
    """Select diverse samples: small (phishing), medium (balanced), large (attachments)"""
    files = []
    for f in os.listdir(email_dir):
        if f.endswith('.eml'):
            path = os.path.join(email_dir, f)
            files.append((path, os.path.getsize(path)))

    if not files:
        return []

    files.sort(key=lambda x: x[1])

    # Tercile selection
    tercile = len(files) // 3
    small_step = max(1, tercile // 5)
    medium_step = max(1, (len(files) - tercile) // 5)

    selected = []

    # Small files (first tercile)
    for i in range(0, tercile, small_step):
        if len(selected) < 5:
            selected.append(files[i][0])

    # Medium files (second tercile)
    for i in range(tercile, 2*tercile, medium_step):
        if len(selected) < 10:
            selected.append(files[i][0])

    # Large files (third tercile)
    large_step = max(1, (len(files) - 2*tercile) // 5)
    for i in range(2*tercile, len(files), large_step):
        if len(selected) < count:
            selected.append(files[i][0])

    return selected[:count]

def curl_upload(file_path):
    """Upload file using curl"""
    try:
        cmd = [
            'curl', '-s', '-X', 'POST',
            '-F', f'file=@{file_path}',
            f'{API_BASE}/upload/'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('job_id')
        return None
    except Exception as e:
        print(f"      Error: {e}")
        return None

def curl_analyze(job_id):
    """Run analysis using curl"""
    try:
        cmd = ['curl', '-s', '-X', 'POST', f'{API_BASE}/analysis/{job_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"      Error: {e}")
        return None

def curl_get(job_id):
    """Get analysis result using curl"""
    try:
        cmd = ['curl', '-s', f'{API_BASE}/analysis/{job_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"      Error: {e}")
        return None

def main():
    print("=" * 80)
    print("EMLYZER HANDS-ON TESTING - Direct API Analysis of Real Email Samples")
    print("=" * 80)

    # Select samples
    print(f"\n[*] Selecting 15 diverse email samples from {EMAIL_DIR}...")
    samples = select_diverse_samples(EMAIL_DIR, 15)

    if not samples:
        print("âŒ No email files found!")
        return

    print(f"âœ“ Selected {len(samples)} samples\n")

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "api_base": API_BASE,
        "total_samples": len(samples),
        "analyses": [],
        "statistics": defaultdict(int),
        "issues": []
    }

    success_count = 0

    for idx, file_path in enumerate(samples, 1):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024

        print(f"[{idx}/{len(samples)}] {filename} ({file_size:.1f} KB)")

        # Upload
        print(f"    Uploading...", end=" ", flush=True)
        job_id = curl_upload(file_path)

        if not job_id:
            print("âŒ FAILED")
            results["issues"].append({
                "file": filename,
                "stage": "upload",
                "error": "Failed to upload"
            })
            continue

        print(f"âœ“ (job: {job_id[:8]}...)")

        # Analyze
        print(f"    Analyzing...", end=" ", flush=True)
        analysis = curl_analyze(job_id)

        if not analysis:
            print("âŒ FAILED")
            results["issues"].append({
                "file": filename,
                "stage": "analysis",
                "error": "Analysis returned empty"
            })
            continue

        print("âœ“")

        # Wait and get full results
        time.sleep(2)
        print(f"    Fetching results...", end=" ", flush=True)
        full_result = curl_get(job_id)

        if full_result:
            analysis = full_result
            print("âœ“")
        else:
            print("âš ï¸")

        # Extract metrics
        risk_score = analysis.get("risk_score", 0)
        risk_label = analysis.get("risk_label", "unknown")

        header_ind = analysis.get("header_indicators", {})
        body_ind = analysis.get("body_indicators", {})
        url_ind = analysis.get("url_indicators", {})
        att_ind = analysis.get("attachment_indicators", {})

        header_findings = len(header_ind.get("findings", []))
        body_findings = len(body_ind.get("findings", []))
        url_findings = len(url_ind.get("findings", []))
        att_findings = len(att_ind.get("findings", []))
        total_findings = header_findings + body_findings + url_findings + att_findings

        rep_phase = "unknown"
        if analysis.get("reputation_results"):
            rep_phase = analysis["reputation_results"].get("reputation_phase", "unknown")

        # Record
        record = {
            "filename": filename,
            "file_size_kb": round(file_size, 1),
            "risk_score": risk_score,
            "risk_label": risk_label,
            "indicators": {
                "header": header_findings,
                "body": body_findings,
                "url": url_findings,
                "attachment": att_findings,
                "total": total_findings
            },
            "reputation_phase": rep_phase,
            "sample_findings": {
                "header": [f["description"][:50] for f in header_ind.get("findings", [])[:2]],
                "body": [f["description"][:50] for f in body_ind.get("findings", [])[:2]],
                "url": [f["description"][:50] for f in url_ind.get("findings", [])[:2]],
                "attachment": [f["description"][:50] for f in att_ind.get("findings", [])[:2]]
            }
        }

        results["analyses"].append(record)
        results["statistics"][risk_label] += 1
        success_count += 1

        # Print summary
        color_risk = "[*]´" if risk_label == "critical" else "[*] " if risk_label == "high" else "[*]¡" if risk_label == "medium" else "[*]¢"
        print(f"    {color_risk} Risk: {risk_label.upper()} ({risk_score}/100)")
        print(f"    [*]Š Indicators: H:{header_findings} B:{body_findings} U:{url_findings} A:{att_findings}")

        if header_findings > 0 and record["sample_findings"]["header"]:
            print(f"       Header: {record['sample_findings']['header'][0]}")
        if body_findings > 0 and record["sample_findings"]["body"]:
            print(f"       Body: {record['sample_findings']['body'][0]}")

        print()

    # Save results
    output_file = os.path.join(OUTPUT_DIR, "hands_on_test_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nAnalyzed: {success_count}/{len(samples)} emails")
    print(f"Failed: {len(results['issues'])}")
    print(f"\nRisk Distribution:")

    for label in sorted(results["statistics"].keys()):
        count = results["statistics"][label]
        pct = 100 * count / success_count if success_count > 0 else 0
        emoji = "[*]´" if label == "critical" else "[*] " if label == "high" else "[*]¡" if label == "medium" else "[*]¢"
        print(f"  {emoji} {label.upper()}: {count} ({pct:.0f}%)")

    if results["analyses"]:
        total_indicators = sum(a["indicators"]["total"] for a in results["analyses"])
        avg_indicators = total_indicators / len(results["analyses"])
        print(f"\nIndicator Statistics:")
        print(f"  Average per email: {avg_indicators:.1f}")
        print(f"  Total found: {total_indicators}")

    print(f"\nâœ“ Results saved to: {output_file}")

if __name__ == "__main__":
    main()
