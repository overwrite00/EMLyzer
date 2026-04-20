"""
core/analysis/nlp_classifier.py

Classificatore NLP per rilevamento phishing/spam nel testo email.
Usa TF-IDF + Logistic Regression (v0.14.0: sostituisce Naive Bayes),
addestrato su pattern sintetici ispirati a corpus open-source (Enron, Nazario).

Il modello viene addestrato al primo utilizzo e cachato in memoria.
Non richiede download esterni: il training set è embedded nel modulo.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Training data — pattern rappresentativi (sintetici, ispirati a corpus reali)
# Bilanciamento ~50/50: label 1 = phishing/spam, label 0 = legittimo
# ---------------------------------------------------------------------------

_TRAINING_SAMPLES: list[tuple[str, int]] = [

    # ══ PHISHING / SPAM (label=1) ═══════════════════════════════════════════

    # --- Urgenza account / credential harvesting (EN) ---
    ("urgent action required your account has been suspended verify immediately", 1),
    ("click here now to confirm your account or it will be deleted", 1),
    ("dear customer your paypal account has been limited please update your information", 1),
    ("your bank account has been compromised login to secure your account now", 1),
    ("verify your identity immediately your account access has been restricted", 1),
    ("your credit card information needs to be updated to avoid suspension", 1),
    ("unusual activity detected on your account please confirm your credentials", 1),
    ("your password will expire please click the link below to reset it now", 1),
    ("dear valued customer we need to verify your account information immediately", 1),
    ("your account will be closed unless you confirm your billing information", 1),
    ("security alert suspicious login attempt detected verify your identity", 1),
    ("action required confirm your email address to avoid account suspension", 1),
    ("your apple id has been locked click here to unlock your account now", 1),
    ("we detected unauthorized access please provide your credentials to confirm", 1),
    ("your amazon account requires immediate verification click below", 1),
    ("verify your account provide password username credit card number", 1),
    ("click here login confirm identity suspended limited expire credentials", 1),
    ("urgent important immediate action required account verify suspend", 1),
    ("dear client your account access blocked update information click here", 1),
    ("your password username has been compromised change it immediately now", 1),
    ("unauthorized transaction detected on your account please verify now", 1),

    # --- Prize / advance-fee fraud (EN) ---
    ("congratulations you have won a prize claim your reward enter your details", 1),
    ("limited time offer claim your free gift before it expires today only", 1),
    ("win an iphone enter your credit card number to claim your prize", 1),
    ("dear beneficiary you have inheritance funds please provide bank details", 1),
    ("free gift card enter your personal information to receive your reward", 1),
    ("exclusive offer limited time only act now before it expires click", 1),
    ("you have been selected to receive a special reward claim now limited offer", 1),
    ("congratulations winner selected enter details to claim cash prize today", 1),

    # --- Tax / government impersonation (EN) ---
    ("irs notice you owe back taxes pay immediately to avoid arrest warrant", 1),
    ("your social security number has been suspended call immediately", 1),
    ("government notice your tax refund is pending verify identity to claim", 1),
    ("final notice unpaid invoice please remit payment immediately to avoid penalty", 1),
    ("invoice payment overdue immediately penalty final notice attached", 1),

    # --- Malware lure / attachment (EN) ---
    ("dear user your email storage is full click here to upgrade immediately", 1),
    ("your netflix account payment failed update your billing information now", 1),
    ("your shipment is on hold provide customs fee payment to release", 1),
    ("bitcoin investment opportunity guaranteed returns act now limited offer", 1),
    ("your package could not be delivered pay customs duties to release it", 1),
    ("document shared with you click to view invoice attached open now", 1),
    ("your voicemail is ready to listen click here to play the message", 1),
    ("scan the qr code below to verify your account identity required now", 1),

    # --- Sextortion / extortion (EN) ---
    ("i have recorded you watching adult content pay bitcoin or i will send video", 1),
    ("your device was hacked we have compromising photos pay ransom now", 1),
    ("we have access to your webcam pay bitcoin to keep your privacy protected", 1),

    # --- Microsoft / Office365 phishing (EN) ---
    ("your microsoft account password has expired please reset it immediately", 1),
    ("office 365 your mailbox is almost full upgrade storage click here now", 1),
    ("microsoft account unusual sign in activity detected verify now to secure", 1),
    ("your onedrive files will be deleted unless you verify your account today", 1),

    # --- Phishing bancario italiano ---
    ("la tua carta di credito e stata bloccata accedi ora per sbloccarla subito", 1),
    ("attenzione il tuo conto corrente e stato sospeso verifica identita ora", 1),
    ("poste italiane avviso importante aggiorna i tuoi dati entro 24 ore clic", 1),
    ("unicredit notifica di sicurezza accesso anomalo rilevato clicca qui", 1),
    ("intesa sanpaolo il tuo conto e stato temporaneamente limitato aggiorna ora", 1),
    ("verifica il tuo account bancario immediatamente per evitare la sospensione", 1),
    ("rimborso fiscale disponibile accedi al portale per ricevere il tuo rimborso", 1),
    ("inps comunicazione urgente aggiorna i tuoi dati per ricevere il sussidio", 1),
    ("amazon italy il tuo ordine e stato sospeso conferma il pagamento ora", 1),
    ("tuo conto paypal limitato fornisci informazioni per sbloccare accesso", 1),
    ("urgente la tua email verra eliminata aggiorna le credenziali entro oggi", 1),

    # --- Phishing Amazon / shipping (EN+IT) ---
    ("your amazon order has been placed verify your payment method click here", 1),
    ("amazon your account was used to make a purchase you did not authorize verify", 1),
    ("il tuo pacco non puo essere consegnato paga le spese doganali adesso", 1),

    # ══ LEGITTIMO (label=0) ══════════════════════════════════════════════════

    # --- Comunicazioni aziendali routine (EN) ---
    ("meeting scheduled for tomorrow at 3pm please confirm your attendance", 0),
    ("attached is the quarterly report for your review please provide feedback", 0),
    ("the project deadline has been moved to next friday please update your plans", 0),
    ("weekly team standup notes attached please review action items", 0),
    ("agenda for next weeks board meeting attached please review beforehand", 0),
    ("new message from colleague regarding the project timeline and milestones", 0),
    ("expense report approved reimbursement will be processed next payroll", 0),
    ("quarterly review meeting notes and action items from last thursday", 0),
    ("team lunch tomorrow at noon rsvp by end of day today", 0),
    ("the server maintenance is scheduled this weekend from 2am to 4am", 0),
    ("your feedback has been submitted thank you for helping us improve", 0),
    ("new comment on your post someone replied to your recent article", 0),
    ("software update available version 2 3 includes bug fixes and improvements", 0),
    ("happy birthday wishes from the entire team enjoy your special day", 0),
    ("conference registration confirmed see you at the annual summit", 0),
    ("your job application has been received we will be in touch shortly", 0),
    ("welcome to our newsletter here are this months updates and announcements", 0),
    ("the document you requested has been shared with you in google drive", 0),
    ("reminder your appointment is scheduled for next tuesday at 2pm", 0),

    # --- E-commerce / transazioni legittime (EN) ---
    ("thank you for your purchase your order has been shipped tracking number", 0),
    ("please find attached the invoice for services rendered this month", 0),
    ("your subscription renewal is coming up on the 15th thank you", 0),
    ("your monthly statement is now available in your online account", 0),
    ("invoice paid thank you payment received confirmation number attached", 0),
    ("your package has been delivered to the front door photo attached", 0),
    ("flight confirmation booking reference attached itinerary for your trip", 0),
    ("your library book is due back please return or renew online", 0),
    ("your order has been dispatched estimated delivery is thursday enjoy", 0),
    ("receipt for your recent purchase thank you for shopping with us", 0),
    ("your subscription has been renewed thank you for being a loyal customer", 0),
    ("delivery update your parcel is out for delivery today between 10am 2pm", 0),

    # --- GitHub / sviluppo software (EN) ---
    ("pull request merged into main branch all tests passing deployment complete", 0),
    ("your github repository has new activity pull request opened by contributor", 0),
    ("new issue opened in your repository please review and triage", 0),
    ("ci pipeline passed all checks green ready to merge approved", 0),
    ("dependency update pull request from dependabot review the changes", 0),
    ("code review requested please review the proposed changes in the pull request", 0),

    # --- HR / risorse umane (EN) ---
    ("your vacation request has been approved enjoy your time off", 0),
    ("payslip for this month is now available in the hr portal", 0),
    ("performance review scheduled please prepare a self assessment", 0),
    ("new employee onboarding welcome to the team first day schedule attached", 0),
    ("your benefits enrollment period opens next week please review options", 0),
    ("training session scheduled for next week compliance training mandatory", 0),

    # --- Email quotidiane italiane (IT) ---
    ("riunione domani mattina alle 9 in sala conferenze ordine del giorno allegato", 0),
    ("ho allegato il preventivo come richiesto fammi sapere se hai domande", 0),
    ("il rapporto mensile e pronto puoi trovarlo nella cartella condivisa", 0),
    ("ricorda che venerdi e festivo gli uffici saranno chiusi buon ponte", 0),
    ("la tua prenotazione e confermata ci vediamo il 15 alle ore 10", 0),
    ("grazie per il tuo ordine abbiamo ricevuto il pagamento spediremo domani", 0),
    ("aggiornamento progetto i lavori procedono come da programma prossima call", 0),
    ("la fattura numero 2024 001 e disponibile per il pagamento scadenza 30 giorni", 0),
    ("tuo abbonamento rinnovato grazie per la fiducia trovi il riepilogo allegato", 0),
    ("promemoria appuntamento con il dottore martedi prossimo alle 15 30", 0),
    ("benvenuto nel team siamo lieti di averti a bordo ecco il piano di onboarding", 0),
    ("la nostra newsletter mensile novita aggiornamenti e articoli selezionati", 0),

    # --- Supporto tecnico / notifiche sistema (EN) ---
    ("your support ticket has been resolved please rate your experience", 0),
    ("system notification scheduled downtime tonight from midnight to 2am", 0),
    ("new follower john doe started following you on the platform", 0),
    ("your two factor authentication code is valid for the next 30 seconds", 0),
    ("password changed successfully if this was not you contact support", 0),
    ("your account settings have been updated if this was not you let us know", 0),
]

# ---------------------------------------------------------------------------
# Modello (singleton, addestrato una volta e cachato)
# ---------------------------------------------------------------------------

_model = None


def _preprocess(text: str) -> str:
    """Pulizia testo minima — lower, rimuovi URL, punteggiatura."""
    text = text.lower()
    text = re.sub(r'https?://\S+', ' url ', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_model():
    """Addestra e cacha il modello (thread-safe per uso sincrono)."""
    global _model
    if _model is not None:
        return _model

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import MaxAbsScaler
        from sklearn.pipeline import Pipeline

        texts  = [_preprocess(t) for t, _ in _TRAINING_SAMPLES]
        labels = [lb for _, lb in _TRAINING_SAMPLES]

        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=3000,
                min_df=1,
                sublinear_tf=True,
            )),
            ('scaler', MaxAbsScaler()),
            ('clf', LogisticRegression(
                C=1.0,
                max_iter=1000,
                solver='lbfgs',
                random_state=42,
            )),
        ])
        pipeline.fit(texts, labels)
        _model = pipeline
        logger.info("NLP classifier (LR) trained on %d samples", len(texts))

    except ImportError:
        logger.warning("scikit-learn non installato: NLP classifier disabilitato")
        _model = None

    return _model


# ---------------------------------------------------------------------------
# Risultato classificatore
# ---------------------------------------------------------------------------

@dataclass
class NLPResult:
    available: bool = False             # False se scikit-learn non installato
    phishing_probability: float = 0.0   # 0.0–1.0
    label: str = "unknown"              # "phishing" / "suspicious" / "legitimate" / "unknown"
    confidence: str = "n/a"             # "low" / "medium" / "high"
    top_features: list[str] = field(default_factory=list)  # feature più rilevanti
    score_contribution: float = 0.0


def classify_text(body_text: str, body_html: str = "") -> NLPResult:
    """
    Classifica il testo dell'email come phishing/legittima.
    Combina plain text e HTML (testo estratto).
    """
    result = NLPResult()

    try:
        from sklearn.pipeline import Pipeline  # noqa: F401 — verifica disponibilità
    except ImportError:
        result.available = False
        return result

    model = _get_model()
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

        # Top feature words (coefficienti LR positivi × TF-IDF)
        try:
            tfidf = model.named_steps['tfidf']
            clf   = model.named_steps['clf']
            vec   = tfidf.transform([processed])
            feat_names = tfidf.get_feature_names_out()
            # coef_[0] per classe 1 (phishing): positivo = predice phishing
            coef = clf.coef_[0]
            weights = vec.toarray()[0] * coef
            top_idx = weights.argsort()[-8:][::-1]
            result.top_features = [
                feat_names[i] for i in top_idx
                if weights[i] > 0 and feat_names[i] in processed
            ][:6]
        except Exception:
            pass

        # Score contribution: scala 0–40 punti
        result.score_contribution = round(phishing_prob * 40, 1)

    except Exception as e:
        logger.warning("NLP classification error: %s", e)
        result.available = False

    return result
