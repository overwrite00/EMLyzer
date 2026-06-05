"""
Synthetic Italian Phishing Data Generator
==========================================

Generates realistic Italian phishing email examples using pattern templates.
NO sensitive data, NO raw email content - only synthetic training features.

Output: CSV with features for NLP model retraining
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
import re
import random

# Phishing templates (Italian)
PHISHING_SUBJECTS = [
    "Azione urgente richiesta: verificare il tuo conto {company}",
    "Ultimo tentativo: reclama la tua ricompensa {product}",
    "Atto di rinnovo obbligatorio entro oggi: {company}",
    "Accesso non autorizzato al tuo {account_type}",
    "Impossibile elaborare il pagamento: {action_required}",
    "Anomalia riscontrata: {company} richiede verifica immediata",
    "Si prega di attendere: {action_required}",
    "{company}: conferma i tuoi dati entro 24 ore",
    "Pagamento scaduto: {company}",
    "Disattivazione imminente del tuo {account_type}",
    "Richiesta di sicurezza urgente",
    "Aggiornamento importante richiesto",
]

PHISHING_BODIES_TEMPLATES = [
    """
    Egregio cliente,
    abbiamo rilevato attività sospetta sul tuo conto.
    Si prega di agire entro {deadline}.
    {cta_action}
    {credential_request}
    Cordiali saluti,
    {company_name}
    """,
    """
    Ultimo tentativo per {action}.
    Non rimandare! {cta_action}
    Documenti richiesti: {documents}
    Entro {deadline}
    """,
    """
    Conferm le tue credenziali per procedere:
    {credential_request}
    {cta_action}
    Grazie,
    {company_name}
    """,
]

COMPANY_NAMES = [
    "Intesa Sanpaolo", "Poste Italiane", "UniCredit", "Banco BPM",
    "INPS", "Agenzia delle Entrate", "PagoPA",
    "Amazon.it", "eBay.it", "Paypal",
    "Vodafone", "TIM", "ENEL",
    "Lidl", "Decathlon", "Leroy Merlin", "Carrefour",
]

CREDENTIAL_REQUESTS = [
    "numero di conto bancario",
    "codice fiscale e data di nascita",
    "IBAN e BIC",
    "numero di carta di credito e CVV",
    "username e password",
    "SPID o CIE",
    "numero di identificazione personale",
    "dati bancari completi",
    "PIN e OTP",
]

CTA_ACTIONS = [
    "accedi al tuo conto cliccando qui",
    "compila il modulo di verifica",
    "visita il sito di {company} cliccando questo link",
    "apri il documento allegato e invia i dati",
    "conferma la tua identità cliccando 'Verifica'",
    "scarica il documento e caricalo",
]

DEADLINES = [
    "entro oggi",
    "entro 24 ore",
    "entro stasera",
    "prima della fine della giornata",
    "entro domani mattina",
]

DOCUMENTS = [
    "documento di identità",
    "certificato di residenza",
    "estratto conto bancario",
    "busta paga",
    "documento e codice fiscale",
]

# Legitimate email templates (Italian)
LEGITIMATE_SUBJECTS = [
    "Estratto conto {month} - {company}",
    "Transazione confermata: {amount} EUR",
    "Ordine #{order_id} - {company}",
    "Notifica di pagamento ricevuto",
    "Aggiornamento account - {company}",
    "Ricezione nuovo messaggio in {platform}",
    "Fattura #{invoice_id} - {company}",
    "Conferma consegna pacco",
    "Saldo disponibile: {amount} EUR",
    "Rendicontazione trimestrale",
]

LEGITIMATE_BODIES_TEMPLATES = [
    """
    Caro cliente,
    La informiamo che abbiamo ricevuto il Suo pagamento di {amount} EUR.
    Transazione: #{txid}
    Data: {date}
    Grazie,
    {company_name}
    """,
    """
    Ordine confermato: #{order_id}
    Articoli: {num_items}
    Importo totale: {amount} EUR
    Data consegna stimata: {delivery_date}
    """,
    """
    Estratto conto di {month}
    Saldo precedente: {amount1} EUR
    Movimenti: {num_transactions}
    Saldo attuale: {amount2} EUR
    """,
]

LEGITIMATE_COMPANIES = [
    "Intesa Sanpaolo", "Poste Italiane", "UniCredit",
    "Amazon.it", "eBay.it", "PayPal",
    "ENEL", "Vodafone", "TIM",
]


@dataclass
class SyntheticEmail:
    """Synthetic email features (NO content stored)."""
    email_type: str  # 'phishing' or 'legitimate'
    subject_length: int
    body_length: int
    urgency_count: int
    cta_count: int
    credential_count: int
    url_count: int
    has_attachments: bool
    spf_pass: bool
    dkim_pass: bool
    dmarc_pass: bool
    label: int  # 0=legitimate, 1=phishing
    confidence: float

    def to_dict(self) -> dict:
        return {
            'source': 'synthetic',
            'filename': f"synthetic_{self.email_type}_{id(self)}.eml",
            'language': 'it',
            'urgency_count': self.urgency_count,
            'cta_count': self.cta_count,
            'credential_count': self.credential_count,
            'body_length': self.body_length,
            'subject_length': self.subject_length,
            'url_count': self.url_count,
            'has_attachments': int(self.has_attachments),
            'spf_pass': int(self.spf_pass),
            'dkim_pass': int(self.dkim_pass),
            'dmarc_pass': int(self.dmarc_pass),
            'label': self.label,
            'confidence': self.confidence,
        }


class ItalianSyntheticEmailGenerator:
    """Generate synthetic Italian phishing/legitimate emails for NLP training."""

    def generate_phishing(self, count: int = 100) -> List[SyntheticEmail]:
        """Generate synthetic Italian phishing emails."""
        emails = []

        for _ in range(count):
            company = random.choice(COMPANY_NAMES)
            subject_template = random.choice(PHISHING_SUBJECTS)
            subject = subject_template.format(
                company=company,
                product=random.choice(["Friggitrice Silvercrest", "Kit Escursionismo", "Coupon"]),
                account_type=random.choice(["conto bancario", "account", "email"]),
                action_required=random.choice(CREDENTIAL_REQUESTS),
            )

            # Generate body
            body_template = random.choice(PHISHING_BODIES_TEMPLATES)
            body = body_template.format(
                deadline=random.choice(DEADLINES),
                cta_action=random.choice(CTA_ACTIONS).format(company=company),
                credential_request="Credenziali richieste: " + random.choice(CREDENTIAL_REQUESTS),
                company_name=company,
                action="reclamare la tua ricompensa",
                documents=", ".join(random.sample(DOCUMENTS, 2)),
            )

            # Count patterns in synthetic text
            combined = (subject + " " + body).lower()
            urgency_count = len(re.findall(r'\b(?:urgente|entro|entro|immediato|ultimo|scade|richiesto|obbligatorio)\b', combined))
            cta_count = len(re.findall(r'\b(?:accedi|clicca|compila|visita|scarica|apri|conferma|invia)\b', combined))
            credential_count = len(re.findall(r'\b(?:credenziali|password|conto|dati|identit|fiscale|iban|carta|cvv|pin|otp|spid|cie)\b', combined))
            url_count = len(re.findall(r'https?://\S+|cliccando(?:\s+)?(?:qui|qua|il\s+link)', combined))

            # Phishing characteristics
            spf_pass = random.choice([False, False, True])  # 2/3 fail SPF
            dkim_pass = random.choice([False, False, True])  # 2/3 fail DKIM
            dmarc_pass = False  # Rarely pass
            has_attachments = random.choice([False, False, True])

            # Confidence score (auto-label)
            confidence = 0.7 + (random.random() * 0.25)  # 0.7-0.95

            email = SyntheticEmail(
                email_type='phishing',
                subject_length=len(subject),
                body_length=len(body),
                urgency_count=max(1, urgency_count),  # At least 1 for phishing
                cta_count=max(1, cta_count),
                credential_count=max(1, credential_count),
                url_count=max(1, url_count),
                has_attachments=has_attachments,
                spf_pass=spf_pass,
                dkim_pass=dkim_pass,
                dmarc_pass=dmarc_pass,
                label=1,  # phishing
                confidence=confidence,
            )
            emails.append(email)

        return emails

    def generate_legitimate(self, count: int = 100) -> List[SyntheticEmail]:
        """Generate synthetic Italian legitimate emails."""
        emails = []

        for _ in range(count):
            company = random.choice(LEGITIMATE_COMPANIES)
            subject_template = random.choice(LEGITIMATE_SUBJECTS)
            subject = subject_template.format(
                month="Settembre 2024",
                company=company,
                amount=f"{random.randint(100, 50000)},00",
                order_id=f"{random.randint(1000000, 9999999)}",
                invoice_id=f"{random.randint(100000, 999999)}",
                platform=random.choice(["LinkedIn", "Gmail", "Outlook"]),
            )

            # Generate body
            body_template = random.choice(LEGITIMATE_BODIES_TEMPLATES)
            body = body_template.format(
                amount=f"{random.randint(100, 50000)},00",
                txid=f"{random.randint(10000000, 99999999)}",
                date="15 settembre 2024",
                company_name=company,
                order_id=f"{random.randint(1000000, 9999999)}",
                num_items=random.randint(1, 10),
                delivery_date="20 settembre 2024",
                month="Settembre 2024",
                amount1=f"{random.randint(10000, 50000)},00",
                num_transactions=random.randint(5, 30),
                amount2=f"{random.randint(10000, 50000)},00",
            )

            # Count patterns (should be minimal for legitimate)
            combined = (subject + " " + body).lower()
            urgency_count = len(re.findall(r'\b(?:urgente|entro|immediato|ultimo|scade)\b', combined))
            cta_count = len(re.findall(r'\b(?:accedi|clicca|compila|visita|scarica|apri|conferma)\b', combined))
            credential_count = len(re.findall(r'\b(?:credenziali|password|conto|dati|identit|fiscale|iban|carta|cvv|pin)\b', combined))
            url_count = 0  # Legitimate emails rarely have suspicious URLs

            # Legitimate characteristics
            spf_pass = random.choice([True, True, False])  # Mostly pass
            dkim_pass = random.choice([True, True, False])
            dmarc_pass = random.choice([True, False])
            has_attachments = random.choice([True, False])

            # Confidence score
            confidence = 0.1 + (random.random() * 0.3)  # 0.1-0.4

            email = SyntheticEmail(
                email_type='legitimate',
                subject_length=len(subject),
                body_length=len(body),
                urgency_count=urgency_count,  # Usually 0
                cta_count=cta_count,  # Usually 0
                credential_count=credential_count,  # Usually 0
                url_count=url_count,
                has_attachments=has_attachments,
                spf_pass=spf_pass,
                dkim_pass=dkim_pass,
                dmarc_pass=dmarc_pass,
                label=0,  # legitimate
                confidence=confidence,
            )
            emails.append(email)

        return emails

    def generate_and_save(self, output_path: str, phishing_count: int = 250, legitimate_count: int = 150):
        """Generate all synthetic data and save to CSV."""
        print(f"Generating {phishing_count} synthetic phishing emails...")
        phishing_emails = self.generate_phishing(phishing_count)

        print(f"Generating {legitimate_count} synthetic legitimate emails...")
        legitimate_emails = self.generate_legitimate(legitimate_count)

        all_emails = phishing_emails + legitimate_emails
        random.shuffle(all_emails)

        print(f"Saving {len(all_emails)} synthetic emails to {output_path}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'source', 'filename', 'language',
                'urgency_count', 'cta_count', 'credential_count',
                'body_length', 'subject_length', 'url_count', 'has_attachments',
                'spf_pass', 'dkim_pass', 'dmarc_pass',
                'label', 'confidence'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for email in all_emails:
                writer.writerow(email.to_dict())

        return len(all_emails)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate synthetic Italian phishing data for NLP training')
    parser.add_argument('--output', type=str, default='synthetic_italian_training.csv',
                       help='Output CSV file path')
    parser.add_argument('--phishing', type=int, default=250,
                       help='Number of synthetic phishing emails')
    parser.add_argument('--legitimate', type=int, default=150,
                       help='Number of synthetic legitimate emails')

    args = parser.parse_args()

    generator = ItalianSyntheticEmailGenerator()
    count = generator.generate_and_save(
        args.output,
        phishing_count=args.phishing,
        legitimate_count=args.legitimate
    )

    print(f"\nSuccess: Generated {count} synthetic emails")
    print(f"Saved to: {args.output}")


if __name__ == '__main__':
    main()
