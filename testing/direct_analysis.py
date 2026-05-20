#!/usr/bin/env python3
import os
import json
import subprocess
import time

EMAIL_DIR = r"D:\Documenti\Email per test analisi"
OUTPUT_DIR = r"D:\GitHub\EMLyzer\testing"
API_BASE = "http://localhost:8000/api"

def select_diverse_samples(email_dir, count=15):
    files = []
    for f in os.listdir(email_dir):
        if f.endswith('.eml'):
            path = os.path.join(email_dir, f)
            files.append((path, os.path.getsize(path)))

    if not files:
        return []

    files.sort(key=lambda x: x[1])
    tercile = len(files) // 3
    selected = []

    # Small, medium, large samples
    for i in range(0, tercile, max(1, tercile // 5)):
        if len(selected) < 5:
            selected.append(files[i][0])

    for i in range(tercile, 2*tercile, max(1, tercile // 5)):
        if len(selected) < 10:
            selected.append(files[i][0])

    for i in range(2*tercile, len(files), max(1, (len(files)-2*tercile) // 5)):
        if len(selected) < count:
            selected.append(files[i][0])

    return selected[:count]

def curl_upload(file_path):
    try:
        cmd = ['curl', '-s', '-X', 'POST', '-F', f'file=@{file_path}', f'{API_BASE}/upload/']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('job_id')
    except:
        pass
    return None

def curl_analyze(job_id):
    try:
        cmd = ['curl', '-s', '-X', 'POST', f'{API_BASE}/analysis/{job_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return None

def curl_get(job_id):
    try:
        cmd = ['curl', '-s', f'{API_BASE}/analysis/{job_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return None

print("="*80)
print("EMLYZER HANDS-ON TESTING - Real Email Analysis")
print("="*80)

print("\n[*] Selecting 15 diverse email samples...")
samples = select_diverse_samples(EMAIL_DIR, 15)
print(f"[OK] Selected {len(samples)} samples\n")

results = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "api_base": API_BASE,
    "total_samples": len(samples),
    "analyses": [],
    "statistics": {},
    "issues": []
}

success_count = 0

for idx, file_path in enumerate(samples, 1):
    filename = os.path.basename(file_path)
    file_size = round(os.path.getsize(file_path) / 1024, 1)

    print(f"[{idx}/{len(samples)}] {filename} ({file_size} KB)")

    # Upload
    print(f"    Uploading...", end=" ", flush=True)
    job_id = curl_upload(file_path)

    if not job_id:
        print("[FAIL]")
        results["issues"].append({"file": filename, "error": "Upload failed"})
        continue

    print(f"[OK] {job_id[:8]}...")

    # Analyze
    print(f"    Analyzing...", end=" ", flush=True)
    analysis = curl_analyze(job_id)

    if not analysis:
        print("[FAIL]")
        results["issues"].append({"file": filename, "error": "Analysis failed"})
        continue

    print("[OK]")

    # Fetch full results
    time.sleep(2)
    print(f"    Fetching...", end=" ", flush=True)
    full_result = curl_get(job_id)

    if full_result:
        analysis = full_result

    print("[OK]\n")

    # Extract metrics
    if not analysis or not isinstance(analysis, dict):
        results["issues"].append({"file": filename, "error": "Analysis returned invalid data"})
        continue

    risk_score = analysis.get("risk_score", 0)
    risk_label = analysis.get("risk_label", "unknown")

    header_ind = analysis.get("header_indicators", {})
    body_ind = analysis.get("body_indicators", {})
    url_ind = analysis.get("url_indicators", {})
    att_ind = analysis.get("attachment_indicators", {})

    h = len(header_ind.get("findings", []))
    b = len(body_ind.get("findings", []))
    u = len(url_ind.get("findings", []))
    a = len(att_ind.get("findings", []))

    rep_results = analysis.get("reputation_results") or {}
    rep_phase = rep_results.get("reputation_phase", "unknown") if rep_results else "unknown"

    record = {
        "filename": filename,
        "file_size_kb": file_size,
        "risk_score": risk_score,
        "risk_label": risk_label,
        "indicators": {"header": h, "body": b, "url": u, "attachment": a, "total": h+b+u+a},
        "reputation_phase": rep_phase,
        "findings": {
            "header": [f["description"][:60] for f in header_ind.get("findings", [])[:2]],
            "body": [f["description"][:60] for f in body_ind.get("findings", [])[:2]],
            "url": [f["description"][:60] for f in url_ind.get("findings", [])[:2]],
            "attachment": [f["description"][:60] for f in att_ind.get("findings", [])[:2]]
        }
    }

    results["analyses"].append(record)
    results["statistics"][risk_label] = results["statistics"].get(risk_label, 0) + 1
    success_count += 1

    # Print summary
    print(f"    Risk: {risk_label.upper()} ({risk_score}/100)")
    print(f"    Indicators: H:{h} B:{b} U:{u} A:{a}")

    for module in ["header", "body", "url", "attachment"]:
        if record["findings"][module]:
            print(f"      {module}: {record['findings'][module][0]}")

# Save results
output_file = os.path.join(OUTPUT_DIR, "hands_on_test_results.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Print summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\nAnalyzed: {success_count}/{len(samples)} emails")
print(f"Failed: {len(results['issues'])}")
print(f"\nRisk Distribution:")

for label in sorted(results["statistics"].keys()):
    count = results["statistics"][label]
    pct = 100 * count / success_count if success_count > 0 else 0
    print(f"  {label.upper()}: {count} ({pct:.0f}%)")

if results["analyses"]:
    total_ind = sum(a["indicators"]["total"] for a in results["analyses"])
    avg_ind = total_ind / len(results["analyses"])
    print(f"\nIndicator Statistics:")
    print(f"  Average per email: {avg_ind:.1f}")
    print(f"  Total found: {total_ind}")

print(f"\n[OK] Results saved to: {output_file}")
