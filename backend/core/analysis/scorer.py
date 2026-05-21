"""
core/analysis/scorer.py

Motore di scoring: aggrega i risultati di tutti i moduli di analisi
in un punteggio di rischio finale spiegabile (0–100).

Algoritmo (v2):
  1. Normalizzazione adattiva: il peso è distribuito solo sui moduli
     con contenuto rilevante per l'email (header e body sempre attivi;
     url solo se l'email ha URL; attachment solo se ha allegati).
     Questo evita che moduli assenti "diluiscano" il punteggio.

  2. Pesi base: header=0.35, body=0.35, url=0.20, attachment=0.10.
     Header e body pesano di più perché sono sempre presenti e i loro
     indicatori (mismatch, NLP) sono i più affidabili per il phishing.

  3. Floor deterministico: soglie minime garantite in presenza di
     indicatori critici ad alta confidenza:
       - 1 finding HIGH header  → score >= 20 (MEDIUM)
       - 1 finding HIGH header + NLP >= 50%  → score >= 35 (MEDIUM)
       - 2+ finding HIGH header → score >= 35 (MEDIUM)
       - 3+ finding HIGH header → score >= 45 (HIGH)
       - URL con risk_score >= 75 → score >= 20 (MEDIUM)
"""

from dataclasses import dataclass, field
from typing import Optional

from utils.i18n import t
from core.analysis.header_analyzer import HeaderAnalysisResult
from core.analysis.body_analyzer import BodyAnalysisResult
from core.analysis.url_analyzer import URLAnalysisResult
from core.analysis.attachment_analyzer import AttachmentAnalysisResult


RISK_LABELS = {
    (0, 20):   ("low",      t("risk.low")),
    (20, 45):  ("medium",   t("risk.medium")),
    (45, 70):  ("high",     t("risk.high")),
    (70, 101): ("critical", t("risk.critical")),
}

# Pesi base per modulo — ridistribuiti adattativamente sui moduli attivi
_BASE_WEIGHTS = {
    "header":     0.35,
    "body":       0.35,
    "url":        0.20,
    "attachment": 0.10,
}


@dataclass
class ScoreContribution:
    module: str
    raw_score: float
    weighted_score: float
    top_reasons: list[str] = field(default_factory=list)


@dataclass
class RiskScore:
    score: float
    label: str
    label_text: str
    contributions: list[ScoreContribution] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    reputation_boost: float = 0.0


def _label_for_score(score: float) -> tuple[str, str]:
    """
    Mappa risk score (0-100) a label e spiegazione tradotta.

    Returns: (label, label_text) dove label in ('low', 'medium', 'high', 'critical')
    """
    for (lo, hi), (label, text) in RISK_LABELS.items():
        if lo <= score < hi:
            return label, text
    return "critical", t("risk.critical")


def _top_reasons_header(result: HeaderAnalysisResult) -> list[str]:
    """
    Estrae i 3 top finding dal header analysis, ordinati per severity (high > medium > low).

    Formato: "[Header/HIGH] description"
    """
    reasons = []
    for f in sorted(result.findings,
                    key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x.severity, 4)):
        if len(reasons) >= 3:
            break
        reasons.append(f"[Header/{f.severity.upper()}] {f.description}")
    return reasons


def _top_reasons_body(result: BodyAnalysisResult) -> list[str]:
    """
    Estrae i 3 top finding dal body analysis, ordinati per severity.

    Formato: "[Body/HIGH] description"
    """
    reasons = []
    for f in sorted(result.findings,
                    key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x.severity, 4)):
        if len(reasons) >= 3:
            break
        reasons.append(f"[Body/{f.severity.upper()}] {f.description}")
    return reasons


def _top_reasons_url(result: URLAnalysisResult) -> list[str]:
    """
    Estrae i 3 top URL per risk_score, con il loro principale finding.

    Formato: "[URL/HIGH] description: hostname"
    """
    reasons = []
    for url_analysis in sorted(result.urls, key=lambda x: -x.risk_score)[:3]:
        for f in url_analysis.findings[:1]:
            reasons.append(f"[URL/{f['severity'].upper()}] {f['description']}: {url_analysis.host}")
    return reasons


def _top_reasons_attachment(result: AttachmentAnalysisResult) -> list[str]:
    """
    Estrae i 3 top allegati per risk_score, con il loro principale finding.

    Formato: "[Allegato/CRITICAL] description: filename"
    """
    reasons = []
    for att in sorted(result.attachments, key=lambda x: -x.risk_score)[:3]:
        for f in sorted(att.findings,
                        key=lambda x: {"critical": 0, "high": 1}.get(x.severity, 2))[:1]:
            reasons.append(f"[Allegato/{f.severity.upper()}] {f.description}: {att.filename}")
    return reasons


def _compute_floors(
    header_result: Optional[HeaderAnalysisResult],
    body_result: Optional[BodyAnalysisResult],
    url_result: Optional[URLAnalysisResult],
    attachment_result: Optional[AttachmentAnalysisResult] = None,
) -> float:
    """
    Applica floor deterministici basati su indicatori critici.

    Garantisce punteggi minimi quando ci sono indicatori ad alta confidenza:
    - Multipli header findings ad alta severità
    - NLP confidence alta (≥50% phishing probability)
    - URL con risk score molto alto (≥75)
    - Allegati pericolosi (macro, JS, double extension)

    Returns:
        Punteggio minimo garantito (0-100) basato su floor rules
    """
    """
    Calcola il floor deterministico basato su indicatori ad alta confidenza.
    Garantisce che email con segnali critici non vengano sotto-classificate
    indipendentemente dalla presenza o assenza degli altri moduli.

    Regole header:
      1 HIGH → ≥20 (MEDIUM)
      1 HIGH + NLP≥50% → ≥35
      2+ HIGH → ≥35
      3+ HIGH → ≥45 (quasi HIGH)

    Regole URL:
      URL risk_score ≥75 → ≥20 (MEDIUM)

    Regole allegati:
      1 finding HIGH (macro, MIME mismatch) → ≥25 (MEDIUM)
      1 finding CRITICAL (eseguibile, macro in PDF) → ≥40

    Regole body:
      2+ finding HIGH (HTML+NLP combinati) → ≥30
    """
    floor = 0.0

    # ── Header ──────────────────────────────────────────────────────────────
    high_header = 0
    if header_result:
        high_header = sum(1 for f in header_result.findings if f.severity == "high")

    nlp_suspicious = False
    if body_result:
        nlp_suspicious = any(
            f.category == "nlp" and f.severity in ("medium", "high")
            for f in body_result.findings
        )

    if high_header >= 1:
        floor = max(floor, 20.0)
    if high_header >= 1 and nlp_suspicious:
        floor = max(floor, 35.0)
    if high_header >= 2:
        floor = max(floor, 35.0)
    if high_header >= 3:
        floor = max(floor, 45.0)

    # ── URL ─────────────────────────────────────────────────────────────────
    if url_result:
        max_url_score = max((u.risk_score for u in url_result.urls), default=0.0)
        if max_url_score >= 75:
            floor = max(floor, 20.0)

    # ── Allegati ─────────────────────────────────────────────────────────────
    # Un allegato con macro VBA o MIME mismatch è un vettore di attacco diretto,
    # indipendentemente da quanto appaiano puliti header e body.
    if attachment_result:
        for att in attachment_result.attachments:
            has_critical = any(f.severity == "critical" for f in att.findings)
            has_high     = any(f.severity == "high"     for f in att.findings)
            if has_critical:
                floor = max(floor, 40.0)   # eseguibile camuffato, macro in PDF
            elif has_high:
                floor = max(floor, 25.0)   # macro VBA, MIME mismatch

    # ── Body ─────────────────────────────────────────────────────────────────
    # 2+ finding HIGH indipendenti nel body (es. form + JS + NLP alto)
    if body_result:
        high_body = sum(1 for f in body_result.findings if f.severity == "high")
        if high_body >= 2:
            floor = max(floor, 30.0)

    return floor


def compute_risk_score(
    header_result: Optional[HeaderAnalysisResult],
    body_result: Optional[BodyAnalysisResult],
    url_result: Optional[URLAnalysisResult],
    attachment_result: Optional[AttachmentAnalysisResult],
    reputation_boost: float = 0.0,
) -> RiskScore:
    """
    Calcola il punteggio di rischio finale (0-100) con normalizzazione adattiva.

    Algoritmo (v2):
    1. Normalizzazione adattiva: pesi distribuiti solo su moduli con contenuto rilevante
       - Header e body sempre attivi (sempre presenti)
       - URL attivo solo se email ha URL
       - Attachment attivo solo se email ha allegati

    2. Pesi base (ridistribuiti proporzionalmente sui moduli attivi):
       - header: 35% (mismatch, auth, injection sono molto affidabili)
       - body: 35% (NLP + pattern = forti indicatori phishing)
       - url: 20% (IP diretto, shortener, nuovi domini = sospetti)
       - attachment: 10% (macro, macro JS, doppia estensione)

    3. Floor deterministico (soglie minime garantite):
       - 1 header HIGH → score ≥ 20 (MEDIUM)
       - 1 header HIGH + NLP ≥50% → score ≥ 35
       - 3+ header HIGH → score ≥ 45 (HIGH)
       - URL risk_score ≥75 → score ≥ 20
       - Allegato HIGH → score ≥ 25
       - Allegato CRITICAL → score ≥ 40

    4. Risk label mapping:
       - 0-20: LOW (safe)
       - 20-45: MEDIUM (suspicious)
       - 45-70: HIGH (likely phishing)
       - 70-100: CRITICAL (definitely phishing)

    Args:
        header_result: Risultati analisi header
        body_result: Risultati analisi body (incluso NLP)
        url_result: Risultati analisi URL
        attachment_result: Risultati analisi allegati
        reputation_boost: Bonus/penalità da reputation checks (0.0 = no boost)

    Returns:
        RiskScore con score finale, label, spiegazione, contributi per modulo, top reasons
    """
    # Determina quali moduli hanno contenuto rilevante
    has_urls        = bool(url_result and url_result.total_urls > 0)
    has_attachments = bool(attachment_result and attachment_result.total_attachments > 0)

    active = {
        "header":     True,
        "body":       True,
        "url":        has_urls,
        "attachment": has_attachments,
    }

    # Calcola il denominatore con i soli moduli attivi
    denominator = sum(_BASE_WEIGHTS[k] for k in active if active[k])

    raw_scores = {
        "header":     header_result.score_contribution     if header_result     else 0.0,
        "body":       body_result.score_contribution       if body_result       else 0.0,
        "url":        url_result.score_contribution        if url_result        else 0.0,
        "attachment": attachment_result.score_contribution if attachment_result else 0.0,
    }

    reason_fns = {
        "header":     _top_reasons_header     if header_result     else None,
        "body":       _top_reasons_body       if body_result       else None,
        "url":        _top_reasons_url        if url_result        else None,
        "attachment": _top_reasons_attachment if attachment_result else None,
    }
    results = {
        "header": header_result, "body": body_result,
        "url": url_result, "attachment": attachment_result,
    }

    contributions = []
    all_reasons = []
    numerator = 0.0

    for module_name in ("header", "body", "url", "attachment"):
        raw = raw_scores[module_name]
        w   = _BASE_WEIGHTS[module_name]

        # Weighted score normalizzato: contribuisce solo se il modulo è attivo
        if active[module_name] and denominator > 0:
            weighted = raw * w / denominator
        else:
            weighted = 0.0

        numerator += raw * w if active[module_name] else 0.0

        reason_fn = reason_fns[module_name]
        result    = results[module_name]
        reasons   = reason_fn(result) if reason_fn and result else []

        contributions.append(ScoreContribution(
            module=module_name,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            top_reasons=reasons,
        ))
        all_reasons.extend(reasons)

    base_score = min(numerator / denominator, 100.0) if denominator > 0 else 0.0

    # Applica floor deterministico
    floor = _compute_floors(header_result, body_result, url_result, attachment_result)
    scored = max(base_score, floor)

    # Boost reputazione (max +30 punti)
    rep_boost   = min(reputation_boost * 0.3, 30.0)
    final_score = min(scored + rep_boost, 100.0)

    label, label_text = _label_for_score(final_score)

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