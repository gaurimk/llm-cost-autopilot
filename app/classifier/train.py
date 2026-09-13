"""
Train the Complexity Classifier
=================================
Loads data/training_prompts.csv, extracts features for each prompt, trains
a logistic regression model to predict the complexity tier (1/2/3), and
saves the trained model + a held-out accuracy report to
app/classifier/model.joblib.

Run with:  python -m app.classifier.train
"""

import csv
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

from app.classifier.features import extract_features, features_to_vector

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "training_prompts.csv"
MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"


def load_dataset():
    prompts, tiers = [], []
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prompts.append(row["prompt"])
            tiers.append(int(row["tier"]))
    return prompts, tiers


def build_feature_matrix(prompts):
    return np.array([features_to_vector(extract_features(p)) for p in prompts])


def train():
    prompts, tiers = load_dataset()
    X = build_feature_matrix(prompts)
    y = np.array(tiers)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    acc = accuracy_score(y_test, preds)
    cm = confusion_matrix(y_test, preds)

    print(f"Held-out accuracy: {acc:.2%}")
    print("Confusion matrix (rows=true tier 1/2/3, cols=predicted 1/2/3):")
    print(cm)

    if acc < 0.80:
        print(
            "WARNING: accuracy is below the 80% bar the build guide sets for a "
            "V1 classifier. Consider adding more labeled examples per tier."
        )

    joblib.dump(clf, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")
    return clf, acc, cm


if __name__ == "__main__":
    train()
