"""
Tabular NLP Model Retraining — Italian Phishing Detection (v0.15.1)
===================================================================

Retrain the phishing classifier using extracted features (tabular data).
Uses Random Forest to model extracted feature patterns without text reconstruction.

Features used:
  - urgency_count, phishing_cta_count, credential_keyword_count
  - body_length, subject_length, url_count, has_attachments
  - spf_pass, dkim_pass, dmarc_pass

This approach avoids overfitting from synthetic text and generalizes better.

Usage:
  cd backend
  python3 nlp_retrain_tabular_model.py

Output:
  - nlp_training/nlp_model_tabular_v0.15.1.pkl (serialized model)
  - nlp_training/tabular_retraining_report.json (performance metrics)
"""

import csv
import json
import pickle
import logging
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import warnings

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class TabularNLPRetrainer:
    """Retrain phishing classifier on extracted feature vectors."""

    # Features to use from CSV
    FEATURE_NAMES = [
        'urgency_count',
        'cta_count',
        'credential_count',
        'body_length',
        'subject_length',
        'url_count',
        'has_attachments',
        'spf_pass',
        'dkim_pass',
        'dmarc_pass',
    ]

    def __init__(self, data_path: str):
        self.data_path = data_path
        self.samples: List[Dict] = []
        self.X = None
        self.y = None
        self.scaler = None
        self.model = None
        self.report = {}

    def load_dataset(self) -> int:
        """Load training data from CSV file."""
        logger.info(f"Loading dataset from {self.data_path}")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Extract features
                    features = {}
                    for fname in self.FEATURE_NAMES:
                        # Handle both int and float values
                        val = row.get(fname, '0')
                        try:
                            features[fname] = float(val)
                        except ValueError:
                            features[fname] = 0.0

                    # Get label
                    label = int(row.get('label', 0))

                    row_data = {**features, 'label': label}
                    self.samples.append(row_data)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping row: {e}")
                    continue

        logger.info(f"Loaded {len(self.samples)} samples with {len(self.FEATURE_NAMES)} features")
        return len(self.samples)

    def prepare_data(self) -> bool:
        """Prepare feature vectors and labels."""
        if not self.samples:
            logger.error("No samples loaded")
            return False

        # Extract features and labels
        X_list = []
        y_list = []

        for sample in self.samples:
            x = [sample.get(fname, 0.0) for fname in self.FEATURE_NAMES]
            y = sample.get('label', 0)
            X_list.append(x)
            y_list.append(y)

        self.X = np.array(X_list, dtype=np.float32)
        self.y = np.array(y_list, dtype=np.int32)

        logger.info(f"Feature matrix shape: {self.X.shape}")
        logger.info(f"Label distribution: {np.bincount(self.y)}")

        return True

    def retrain(self) -> bool:
        """Retrain the model."""
        if self.X is None or self.y is None:
            logger.error("Data not prepared")
            return False

        logger.info("Preparing training data...")

        # Split: 70% train, 15% val, 15% test
        X_train, X_temp, y_train, y_temp = train_test_split(
            self.X, self.y, test_size=0.30, random_state=42, stratify=self.y
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
        )

        logger.info(f"Train set: {len(X_train)}, Val set: {len(X_val)}, Test set: {len(X_test)}")

        # Analyze distribution
        train_phishing = np.sum(y_train == 1)
        val_phishing = np.sum(y_val == 1)
        test_phishing = np.sum(y_test == 1)

        logger.info(f"Train distribution: {train_phishing}/{len(y_train)} phishing ({train_phishing/len(y_train)*100:.1f}%)")
        logger.info(f"Val distribution: {val_phishing}/{len(y_val)} phishing ({val_phishing/len(y_val)*100:.1f}%)")
        logger.info(f"Test distribution: {test_phishing}/{len(y_test)} phishing ({test_phishing/len(y_test)*100:.1f}%)")

        # Scale features
        logger.info("Scaling features...")
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        X_test_scaled = self.scaler.transform(X_test)

        # Train Random Forest
        logger.info("Training Random Forest model...")
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1,
        )

        self.model.fit(X_train_scaled, y_train)
        logger.info("Model trained successfully")

        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        val_score = self.model.score(X_val_scaled, y_val)
        test_score = self.model.score(X_test_scaled, y_test)

        logger.info(f"Train accuracy: {train_score:.3f}")
        logger.info(f"Val accuracy: {val_score:.3f}")
        logger.info(f"Test accuracy: {test_score:.3f}")

        # Cross-validation
        cv_scores = cross_val_score(
            self.model, X_train_scaled, y_train, cv=5, scoring='accuracy'
        )
        logger.info(f"Cross-validation (5-fold): {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

        # Classification report
        y_pred = self.model.predict(X_test_scaled)
        logger.info("\nTest Set Classification Report:")
        logger.info(classification_report(y_test, y_pred, target_names=['Legitimate', 'Phishing']))

        # Feature importance
        feature_importance = sorted(
            zip(self.FEATURE_NAMES, self.model.feature_importances_),
            key=lambda x: x[1],
            reverse=True
        )
        logger.info("\nTop Features by Importance:")
        for fname, importance in feature_importance[:5]:
            logger.info(f"  {fname:30s}: {importance:.3f}")

        self.report = {
            'version': 'v0.15.1',
            'model_type': 'RandomForestClassifier',
            'total_samples': len(self.samples),
            'train_samples': len(X_train),
            'val_samples': len(X_val),
            'test_samples': len(X_test),
            'train_accuracy': round(train_score, 3),
            'val_accuracy': round(val_score, 3),
            'test_accuracy': round(test_score, 3),
            'cv_mean_accuracy': round(cv_scores.mean(), 3),
            'cv_std_accuracy': round(cv_scores.std(), 3),
            'train_phishing_pct': round(train_phishing / len(y_train) * 100, 1),
            'val_phishing_pct': round(val_phishing / len(y_val) * 100, 1),
            'test_phishing_pct': round(test_phishing / len(y_test) * 100, 1),
            'feature_names': self.FEATURE_NAMES,
            'feature_importance': [
                {'feature': fname, 'importance': round(imp, 3)}
                for fname, imp in feature_importance
            ],
        }

        return True

    def save_model(self, output_path: str) -> bool:
        """Serialize and save the model + scaler."""
        if self.model is None or self.scaler is None:
            logger.error("No model or scaler to save")
            return False

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.FEATURE_NAMES,
            }
            with open(output_path, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info(f"Model saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            return False

    def save_report(self, output_path: str) -> bool:
        """Save retraining report."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2)
            logger.info(f"Report saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Retrain tabular phishing classifier on Italian features'
    )
    parser.add_argument(
        '--dataset',
        type=str,
        default='nlp_training/italian_training_complete.csv',
        help='Input training dataset path',
    )
    parser.add_argument(
        '--output-model',
        type=str,
        default='nlp_training/nlp_model_tabular_v0.15.1.pkl',
        help='Output model path',
    )
    parser.add_argument(
        '--output-report',
        type=str,
        default='nlp_training/tabular_retraining_report.json',
        help='Output report path',
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Tabular NLP Model Retraining — Italian Phishing Detection (v0.15.1)")
    logger.info("=" * 80)
    logger.info("")

    retrainer = TabularNLPRetrainer(args.dataset)

    # Load
    if retrainer.load_dataset() == 0:
        logger.error("Failed to load dataset")
        return 1

    # Prepare
    if not retrainer.prepare_data():
        logger.error("Failed to prepare data")
        return 1

    # Retrain
    if not retrainer.retrain():
        logger.error("Retraining failed")
        return 1

    # Save
    if not retrainer.save_model(args.output_model):
        logger.error("Failed to save model")
        return 1

    if not retrainer.save_report(args.output_report):
        logger.error("Failed to save report")
        return 1

    logger.info("")
    logger.info("=" * 80)
    logger.info("RETRAINING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Model saved to: {args.output_model}")
    logger.info(f"Report saved to: {args.output_report}")
    logger.info("")
    logger.info("Next step: Integrate model into nlp_classifier.py")

    return 0


if __name__ == '__main__':
    exit(main())
