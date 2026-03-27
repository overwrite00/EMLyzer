"""
core/analysis/nlp_classifier.py

Classificatore NLP per rilevamento phishing/spam nel testo email.
Usa TF-IDF + Multinomial Naive Bayes, addestrato su pattern sintetici
derivati da corpus open-source (Enron, Nazario phishing corpus stile).

Il modello viene addestrato al primo utilizzo e cachato in memoria.
Non richiede download esterni: il training set è embedded nel modulo.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Training data — pattern rappresentativi (sintetici, ispirati a corpus reali)
# ---------------------------------------------------------------------------

# Etichette: 0 = legittimo, 1 = phishing/spam
_TRAINING_SAMPLES: list[tuple[str, int]] = [
    # ── PHISHING / SPAM (label=1) ────────────────────────────────────────────
    ("urgent action required your account has been suspended verify immediately", 1),
    ("click here now to confirm your account or it will be deleted", 1),
    ("dear customer your paypal account has been limited please update your information", 1),
    ("your bank account has been compromised login to secure your account now", 1),
    ("congratulations you have won a prize claim your reward enter your details", 1),
    ("verify your identity immediately your account access has been restricted", 1),
    ("your credit card information needs to be updated to avoid suspension", 1),
    ("unusual activity detected on your account please confirm your credentials", 1),
    ("your password will expire please click the link below to reset it now", 1),
    ("limited time offer claim your free gift before it expires today only", 1),
    ("dear valued customer we need to verify your account information immediately", 1),
    ("your account will be closed unless you confirm your billing information", 1),
    ("security alert suspicious login attempt detected verify your identity", 1),
    ("action required confirm your email address to avoid account suspension", 1),
    ("your apple id has been locked click here to unlock your account now", 1),
    ("we detected unauthorized access please provide your credentials to confirm", 1),
    ("your amazon account requires immediate verification click below", 1),
    ("final notice unpaid invoice please remit payment immediately to avoid penalty", 1),
    ("dear user your email storage is full click here to upgrade immediately", 1),
    ("your netflix account payment failed update your billing information now", 1),
    ("win an iphone enter your credit card number to claim your prize", 1),
    ("dear beneficiary you have inheritance funds please provide bank details", 1),
    ("irs notice you owe back taxes pay immediately to avoid arrest warrant", 1),
    ("your social security number has been suspended call immediately", 1),
    ("free gift card enter your personal information to receive your reward", 1),
    ("verify your account provide password username credit card number", 1),
    ("click here login confirm identity suspended limited expire credentials", 1),
    ("urgent important immediate action required account verify suspend", 1),
    ("invoice payment overdue immediately penalty final notice attached", 1),
    ("dear client your account access blocked update information click here", 1),
    ("your password username has been compromised change it immediately now", 1),
    ("exclusive offer limited time only act now before it expires click", 1),
    ("unauthorized transaction detected on your account please verify now", 1),
    ("your shipment is on hold provide customs fee payment to release", 1),
    ("bitcoin investment opportunity guaranteed returns act now limited offer", 1),

    # ── LEGITTIMO (label=0) ──────────────────────────────────────────────────
    ("meeting scheduled for tomorrow at 3pm please confirm your attendance", 0),
    ("attached is the quarterly report for your review please provide feedback", 0),
    ("thank you for your purchase your order has been shipped tracking number", 0),
    ("please find attached the invoice for services rendered this month", 0),
    ("the project deadline has been moved to next friday please update your plans", 0),
    ("your subscription renewal is coming up on the 15th thank you", 0),
    ("pull request merged into main branch all tests passing deployment complete", 0),
    ("team lunch tomorrow at noon rsvp by end of day today", 0),
    ("your monthly statement is now available in your online account", 0),
    ("welcome to our newsletter here are this months updates and announcements", 0),
    ("reminder your appointment is scheduled for next tuesday at 2pm", 0),
    ("the document you requested has been shared with you in google drive", 0),
    ("your job application has been received we will be in touch shortly", 0),
    ("flight confirmation booking reference attached itinerary for your trip", 0),
    ("new comment on your post someone replied to your recent article", 0),
    ("software update available version 2 3 includes bug fixes and improvements", 0),
    ("weekly team standup notes attached please review action items", 0),
    ("your package has been delivered to the front door photo attached", 0),
    ("invoice paid thank you payment received confirmation number attached", 0),
    ("new follower john doe started following you on the platform", 0),
    ("agenda for next weeks board meeting attached please review beforehand", 0),
    ("your github repository has new activity pull request opened by contributor", 0),
    ("happy birthday wishes from the entire team enjoy your special day", 0),
    ("conference registration confirmed see you at the annual summit", 0),
    ("the server maintenance is scheduled this weekend from 2am to 4am", 0),
    ("your feedback has been submitted thank you for helping us improve", 0),
    ("new message from colleague regarding the project timeline and milestones", 0),
    ("expense report approved reimbursement will be processed next payroll", 0),
    ("quarterly review meeting notes and action items from last thursday", 0),
    ("your library book is due back please return or renew online", 0),
]

# ---------------------------------------------------------------------------
# Modello (singleton, addestrato una volta e cachato)
# ---------------------------------------------------------------------------

_model = None
_vectorizer = None


def _preprocess(text: str) -> str:
    """Pulizia testo minima — lower, rimuovi URL, punteggiatura."""
    text = text.lower()
    text = re.sub(r'https?://\S+', ' url ', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_model():
    """Addestra e cacha il modello (thread-safe per uso sincrono)."""
    global _model, _vectorizer
    if _model is not None:
        return _vectorizer, _model

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.pipeline import Pipeline

        texts  = [_preprocess(t) for t, _ in _TRAINING_SAMPLES]
        labels = [l for _, l in _TRAINING_SAMPLES]

        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=2000,
                min_df=1,
                sublinear_tf=True,
            )),
            ('clf', MultinomialNB(alpha=0.5)),
        ])
        pipeline.fit(texts, labels)

        _vectorizer = None   # embedded in pipeline
        _model = pipeline
        logger.info("NLP classifier trained on %d samples", len(texts))

    except ImportError:
        logger.warning("scikit-learn non installato: NLP classifier disabilitato")
        _model = None

    return None, _model


# ---------------------------------------------------------------------------
# Risultato classificatore
# ---------------------------------------------------------------------------

@dataclass
class NLPResult:
    available: bool = False        # False se scikit-learn non installato
    phishing_probability: float = 0.0   # 0.0–1.0
    label: str = "unknown"         # "phishing" / "legitimate" / "unknown"
    confidence: str = "n/a"        # "low" / "medium" / "high"
    top_features: list[str] = field(default_factory=list)   # feature più rilevanti
    score_contribution: float = 0.0


def classify_text(body_text: str, body_html: str = "") -> NLPResult:
    """
    Classifica il testo dell'email come phishing/legittima.
    Combina plain text e HTML (testo estratto).
    """
    result = NLPResult()

    try:
        from sklearn.pipeline import Pipeline
    except ImportError:
        result.available = False
        return result

    _, model = _get_model()
    if model is None:
        return result

    result.available = True

    # Estrai testo da HTML se necessario
    html_text = ""
    if body_html:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(body_html, "html.parser")
            html_text = soup.get_text(separator=" ", strip=True)
        except Exception:
            pass

    combined = f"{body_text} {html_text}".strip()
    if not combined:
        result.label = "unknown"
        return result

    processed = _preprocess(combined)

    try:
        # Probabilità classe phishing (label=1)
        proba = model.predict_proba([processed])[0]
        phishing_prob = float(proba[1])
        result.phishing_probability = round(phishing_prob, 3)

        if phishing_prob >= 0.75:
            result.label = "phishing"
            result.confidence = "high"
        elif phishing_prob >= 0.50:
            result.label = "phishing"
            result.confidence = "medium"
        elif phishing_prob >= 0.35:
            result.label = "suspicious"
            result.confidence = "low"
        else:
            result.label = "legitimate"
            result.confidence = "high" if phishing_prob < 0.15 else "medium"

        # Top feature words (quelle con peso più alto per questa predizione)
        try:
            tfidf = model.named_steps['tfidf']
            clf   = model.named_steps['clf']
            vec   = tfidf.transform([processed])
            feat_names = tfidf.get_feature_names_out()
            # Log-probabilità delle feature per la classe phishing
            log_probs = clf.feature_log_prob_[1]
            # Peso = tf-idf * log_prob
            weights = vec.toarray()[0] * log_probs
            top_idx = weights.argsort()[-8:][::-1]
            result.top_features = [
                feat_names[i] for i in top_idx
                if weights[i] > 0 and feat_names[i] in processed
            ][:6]
        except Exception:
            pass

        # Score contribution: scala 0–100
        result.score_contribution = round(phishing_prob * 40, 1)  # max +40 punti

    except Exception as e:
        logger.warning("NLP classification error: %s", e)
        result.available = False

    return result
