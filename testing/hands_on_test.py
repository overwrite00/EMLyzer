#!/usr/bin/env python3
"""
Hands-on testing of EMLyzer with real email samples.
Analyzes 15 diverse emails, compares results with expert expectations,
and identifies improvement areas.
"""

import os
import json
import requests
import time
from pathlib import Path
from collections import defaultdict

# Configuration
API_BASE = "http://localhost:8000/api"
EMAIL_DIR = r"D:\Documenti\Email per test analisi"
OUTPUT_DIR = r"D:\GitHub\EMLyzer\testing"
SAMPLE_SIZE = 15

# Helper function to select diverse samples
def select_diverse_samples(email_dir, count=15):
    """Select diverse samples by size: small (phishing), medium (balanced), large (attachments)"""
    files = sorted(
        [f for f in os.listdir(email_dir) if f.endswith('.eml')],
        key=lambda x: os.path.getsize(os.path.join(email_dir, x))
    )

    if len(files) < count:
        return files

    # Divide into terciles
    tercile = len(files) // 3
    small = files[:tercile:tercile//5][:5]  # 5 small
    medium = files[tercile:2*tercile:tercile//5][:5]  # 5 medium
    large = files[2*tercile::tercile//5][:5]  # 5 large

    selected = small + medium + large
    return [os.path.join(email_dir, f) for f in selected[:count]]

# Test execution
def run_tests():
    print("=" * 80)
    print("EMLYZER HANDS-ON TESTING - Practical Analysis of Real Email Samples")
    print("=" * 80)

    # Select samples
    print(f"\n📧 Selecting {SAMPLE_SIZE} diverse email samples...")
    samples = select_diverse_samples(EMAIL_DIR, SAMPLE_SIZE)

    if not samples:
        print("❌ No email files found!")
        return

    print(f"✓ Selected {len(samples)} samples")

    results = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_samples": len(samples),
            "api_base": API_BASE
        },
        "analyses": [],
        "statistics": defaultdict(int),
        "issues": []
    }

    # Analyze each email
    for idx, email_path in enumerate(samples, 1):
        filename = os.path.basename(email_path)
        file_size = os.path.getsize(email_path) / 1024  # KB

        print(f"\n[{idx}/{len(samples)}] Analyzing {filename} ({file_size:.1f} KB)...")

        try:
            # 1. Upload email
            with open(email_path, 'rb') as f:
                files = {'file': (filename, f)}
                upload_resp = requests.post(f"{API_BASE}/upload/", files=files, timeout=30)

            if upload_resp.status_code != 200:
                print(f"  ❌ Upload failed: {upload_resp.status_code}")
                results["issues"].append({
                    "file": filename,
                    "stage": "upload",
                    "error": upload_resp.text[:200]
                })
                continue

            job_id = upload_resp.json()["job_id"]
            print(f"  ✓ Uploaded (job_id: {job_id[:8]}...)")

            # 2. Analyze email
            analysis_resp = requests.post(
                f"{API_BASE}/analysis/{job_id}",
                timeout=120
            )

            if analysis_resp.status_code != 200:
                print(f"  ❌ Analysis failed: {analysis_resp.status_code}")
                results["issues"].append({
                    "file": filename,
                    "stage": "analysis",
                    "error": analysis_resp.text[:200]
                })
                continue

            analysis = analysis_resp.json()
            print(f"  ✓ Analysis complete")

            # 3. Fetch full results (with reputation)
            time.sleep(1)
            get_resp = requests.get(f"{API_BASE}/analysis/{job_id}", timeout=30)

            if get_resp.status_code == 200:
                full_result = get_resp.json()
                analysis = full_result

            # Extract key metrics
            risk_score = analysis.get("risk_score", 0)
            risk_label = analysis.get("risk_label", "unknown")

            header_ind = analysis.get("header_indicators", {})
            body_ind = analysis.get("body_indicators", {})
            url_ind = analysis.get("url_indicators", {})
            att_ind = analysis.get("attachment_indicators", {})

            # Count findings
            header_findings = len(header_ind.get("findings", []))
            body_findings = len(body_ind.get("findings", []))
            url_findings = len(url_ind.get("findings", []))
            att_findings = len(att_ind.get("findings", []))

            # Reputation phase
            rep_phase = "unknown"
            if analysis.get("reputation_results"):
                rep_phase = analysis["reputation_results"].get("reputation_phase", "unknown")

            # Record result
            record = {
                "filename": filename,
                "file_size_kb": round(file_size, 1),
                "job_id": job_id,
                "risk_score": risk_score,
                "risk_label": risk_label,
                "indicators": {
                    "header": header_findings,
                    "body": body_findings,
                    "url": url_findings,
                    "attachment": att_findings,
                    "total": header_findings + body_findings + url_findings + att_findings
                },
                "reputation_phase": rep_phase,
                "key_findings": {
                    "header": [f["description"][:60] for f in header_ind.get("findings", [])[:3]],
                    "body": [f["description"][:60] for f in body_ind.get("findings", [])[:3]],
                    "url": [f["description"][:60] for f in url_ind.get("findings", [])[:3]],
                    "attachment": [f["description"][:60] for f in att_ind.get("findings", [])[:3]]
                }
            }

            results["analyses"].append(record)
            results["statistics"][risk_label] += 1

            # Print summary
            print(f"  Risk: {risk_label.upper()} ({risk_score}/100)")
            print(f"  Indicators: H:{header_findings} B:{body_findings} U:{url_findings} A:{att_findings}")
            if header_findings > 0:
                print(f"    → {record['key_findings']['header'][0]}")
            if body_findings > 0:
                print(f"    → {record['key_findings']['body'][0]}")

        except requests.exceptions.Timeout:
            print(f"  ⏱️  Timeout")
            results["issues"].append({"file": filename, "error": "Timeout (>120s)"})
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            results["issues"].append({"file": filename, "error": str(e)[:200]})

    # Save results
    output_file = os.path.join(OUTPUT_DIR, "hands_on_test_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nAnalyzed: {len(results['analyses'])} emails")
    print(f"Failed: {len(results['issues'])}")
    print(f"\nRisk Distribution:")
    for label, count in sorted(results["statistics"].items()):
        pct = 100 * count / len(results['analyses']) if results['analyses'] else 0
        print(f"  {label.upper()}: {count} ({pct:.0f}%)")

    print(f"\nIndicator Statistics:")
    if results["analyses"]:
        total_indicators = sum(a["indicators"]["total"] for a in results["analyses"])
        avg_indicators = total_indicators / len(results["analyses"])
        print(f"  Average indicators per email: {avg_indicators:.1f}")
        print(f"  Total indicators found: {total_indicators}")

    print(f"\nResults saved to: {output_file}")

    return results

if __name__ == "__main__":
    results = run_tests()
