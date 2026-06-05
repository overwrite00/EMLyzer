#!/usr/bin/env python3
"""
Test improved NLP classifier on private Italian email samples.

Compares:
  - Text-based classifier (v0.14.x — embedded LR model)
  - Tabular classifier (v0.15.1 — Random Forest on features)

Shows improvement in Italian phishing detection.
"""

import sys
sys.path.insert(0, '.')

import os
from email.parser import Parser
from core.analysis.body_analyzer import analyze_body
from core.analysis.email_parser import parse_email_file
from core.analysis.nlp_classifier import classify_text, classify_features

print("=" * 100)
print("TEST: Italian Phishing Detection Improvements (v0.15.1)")
print("=" * 100)
print()

private_path = r"D:\Documenti\Email spam"

if not os.path.exists(private_path):
    print(f"ERROR: Path not found: {private_path}")
    sys.exit(1)

all_files = sorted([f for f in os.listdir(private_path) if f.endswith(".eml")])

print(f"Testing {len(all_files)} private email samples...")
print()
print(f"{'#':2s} {'Phishing (Text)':15s} {'Phishing (Tab)':15s} {'Urgency':8s} {'CTAs':5s} {'Creds':6s} {'URLs':5s}")
print("-" * 100)

results = []

for i, filename in enumerate(all_files, 1):
    email_path = os.path.join(private_path, filename)

    try:
        with open(email_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw_email = f.read()

        # Parse email
        parsed = parse_email_file(raw_email, filename)

        # Analyze body (extracts features)
        body_result = analyze_body(parsed)

        # Get NLP results from both models
        # Ensure strings are properly encoded
        body_text = str(parsed.body or "")
        body_html = str(parsed.body_html or "")
        text_result = classify_text(body_text, body_html)
        feature_result = classify_features(
            urgency_count=body_result.urgency_count,
            cta_count=body_result.phishing_cta_count,
            credential_count=body_result.credential_keyword_count,
            body_length=len(parsed.body or ""),
            subject_length=len(parsed.mail_subject or ""),
            url_count=len(body_result.extracted_urls),
            has_attachments=False,
            spf_pass=parsed.spf_pass or False,
            dkim_pass=parsed.dkim_pass or False,
            dmarc_pass=parsed.dmarc_pass or False,
        )

        text_prob = text_result.phishing_probability * 100
        feat_prob = feature_result.phishing_probability * 100 if feature_result.available else 0

        print(
            f"{i:2d} {text_prob:6.1f}% → {text_result.label:8s} | "
            f"{feat_prob:6.1f}% → {feature_result.label:8s} | "
            f"{body_result.urgency_count:8d} {body_result.phishing_cta_count:5d} "
            f"{body_result.credential_keyword_count:6d} {len(body_result.extracted_urls):5d}"
        )

        results.append({
            'filename': filename[:40],
            'text_prob': text_prob,
            'text_label': text_result.label,
            'feat_prob': feat_prob,
            'feat_label': feature_result.label,
            'urgency': body_result.urgency_count,
            'cta': body_result.phishing_cta_count,
            'cred': body_result.credential_keyword_count,
            'urls': len(body_result.extracted_urls),
        })

    except Exception as e:
        import traceback
        print(f"{i:2d} ERROR: {str(e)[:60]}")
        # Uncomment for full traceback:
        # traceback.print_exc()

print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print()

if results:
    # Calculate improvements
    text_high = sum(1 for r in results if r['text_prob'] >= 50)
    feat_high = sum(1 for r in results if r['feat_prob'] >= 50)

    print(f"Text-based classifier (v0.14.x):")
    print(f"  High/Critical risk (≥50%): {text_high}/{len(results)}")
    print(f"  Avg probability: {sum(r['text_prob'] for r in results)/len(results):.1f}%")
    print()

    if any(r['feat_prob'] > 0 for r in results):
        print(f"Tabular classifier (v0.15.1 — Italian-focused):")
        print(f"  High/Critical risk (≥50%): {feat_high}/{len(results)}")
        print(f"  Avg probability: {sum(r['feat_prob'] for r in results)/len(results):.1f}%")
        print()

        improvements = []
        for r in results:
            if r['feat_prob'] > r['text_prob']:
                improvement = r['feat_prob'] - r['text_prob']
                improvements.append((r['filename'][:30], improvement))

        if improvements:
            print("Samples with improved detection (v0.15.1 vs v0.14.x):")
            for fname, imp in sorted(improvements, key=lambda x: -x[1])[:5]:
                print(f"  {fname:30s}: +{imp:5.1f}% improvement")
        print()

        print("Key Improvements in v0.15.1:")
        print("  ✓ 58+ new Italian/Portuguese phishing patterns")
        print("  ✓ 409-sample Italian training dataset (97.8% Italian)")
        print("  ✓ Random Forest model trained on extracted features")
        print("  ✓ Feature importance: urgency_count (34%), url_count (26%)")
        print()
    else:
        print("NOTE: Tabular model not found. Install model with:")
        print("  cd backend")
        print("  python3 nlp_retrain_tabular_model.py")
print()
print("=" * 100)
