"""
core/analysis/scorer.py

Motore di scoring: aggrega i risultati di tutti i moduli di analisi
in un punteggio di rischio finale spiegabile (0–100).
"""

from dataclasses import dataclass, field
from typing import Optional

from utils.i18n import t
from core.analysis.header_analyzer import HeaderAnalysisResult
from core.analysis.body_analyzer import BodyAnalysisResult
from core.analysis.url_analyzer import URLAnalysisResult
from core.analysis.attachment_analyzer import AttachmentAnalysisResult


RISK_LABELS = {
    (0, 20): ("low", t("risk.low")),
    (20, 45): ("medium", t("risk.medium")),
    (45, 70): ("high", t("risk.high")),
    (70, 101): ("critical", t("risk.critical")),
}

# Pesi relativi dei moduli (somma = 1.0)
MODULE_WEIGHTS = {
    "header": 0.25,
    "body": 0.25,
    "url": 0.25,
    "attachment": 0.25,
}


@dataclass
class ScoreContribution:
    module: str
    raw_score: float
    weighted_score: float
    top_reasons: list[str] = field(default_factory=list)


@dataclass
class RiskScore:
    score: float                          # 0–100
    label: str                            # low / medium / high / critical
    label_text: str                       # testo leggibile
    contributions: list[ScoreContribution] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    reputation_boost: float = 0.0        # bonus da reputazione


def _label_for_score(score: float) -> tuple[str, str]:
    for (lo, hi), (label, text) in RISK_LABELS.items():
        if lo <= score < hi:
            return label, text
    return "critical", "Rischio critico"


def _top_reasons_header(result: HeaderAnalysisResult) -> list[str]:
    reasons = []
    for f in sorted(result.findings, key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x.severity, 4)):
        if len(reasons) >= 3:
            break
        reasons.append(f"[Header/{f.severity.upper()}] {f.description}")
    return reasons


def _top_reasons_body(result: BodyAnalysisResult) -> list[str]:
    reasons = []
    for f in sorted(result.findings, key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x.severity, 4)):
        if len(reasons) >= 3:
            break
        reasons.append(f"[Body/{f.severity.upper()}] {f.description}")
    return reasons


def _top_reasons_url(result: URLAnalysisResult) -> list[str]:
    reasons = []
    for url_analysis in sorted(result.urls, key=lambda x: -x.risk_score)[:3]:
        for f in url_analysis.findings[:1]:
            reasons.append(f"[URL/{f['severity'].upper()}] {f['description']}: {url_analysis.host}")
    return reasons


def _top_reasons_attachment(result: AttachmentAnalysisResult) -> list[str]:
    reasons = []
    for att in sorted(result.attachments, key=lambda x: -x.risk_score)[:3]:
        for f in sorted(att.findings, key=lambda x: {"critical": 0, "high": 1}.get(x.severity, 2))[:1]:
            reasons.append(f"[Allegato/{f.severity.upper()}] {f.description}: {att.filename}")
    return reasons


def compute_risk_score(
    header_result: Optional[HeaderAnalysisResult],
    body_result: Optional[BodyAnalysisResult],
    url_result: Optional[URLAnalysisResult],
    attachment_result: Optional[AttachmentAnalysisResult],
    reputation_boost: float = 0.0,
) -> RiskScore:
    """
    Calcola il punteggio di rischio finale aggregando tutti i moduli.
    reputation_boost: punteggio aggiuntivo da fonti di reputazione (0–100).
    """
    contributions = []
    all_reasons = []

    modules = [
        ("header", header_result, _top_reasons_header if header_result else None),
        ("body", body_result, _top_reasons_body if body_result else None),
        ("url", url_result, _top_reasons_url if url_result else None),
        ("attachment", attachment_result, _top_reasons_attachment if attachment_result else None),
    ]

    weighted_sum = 0.0

    for module_name, result, reason_fn in modules:
        raw = 0.0
        if result is not None:
            raw = result.score_contribution
        weight = MODULE_WEIGHTS[module_name]
        weighted = raw * weight
        weighted_sum += weighted

        reasons = reason_fn(result) if reason_fn and result else []
        contributions.append(ScoreContribution(
            module=module_name,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            top_reasons=reasons,
        ))
        all_reasons.extend(reasons)

    # Normalizza a 100 (i pesi sommano a 1, quindi weighted_sum è già in scala 0–100)
    base_score = min(weighted_sum, 100.0)

    # Boost reputazione (max +30 punti)
    rep_boost = min(reputation_boost * 0.3, 30.0)
    final_score = min(base_score + rep_boost, 100.0)

    label, label_text = _label_for_score(final_score)

    # Costruisci spiegazione ordinata per severità
    explanation = []
    seen = set()
    for reason in all_reasons:
        if reason not in seen:
            explanation.append(reason)
            seen.add(reason)

    return RiskScore(
        score=round(final_score, 1),
        label=label,
        label_text=label_text,
        contributions=contributions,
        explanation=explanation,
        reputation_boost=round(rep_boost, 1),
    )
