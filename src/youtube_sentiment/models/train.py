import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import joblib
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.svm import LinearSVC
from threadpoolctl import threadpool_limits

from youtube_sentiment.data.download import LABELS
from youtube_sentiment.data.prepare import PROCESSED, SEED, read_split
from youtube_sentiment.models.benchmark import benchmark
from youtube_sentiment.preprocessing import clean_comments

MODELS = Path("models")
REPORTS = Path("reports")


def training_pipeline() -> Pipeline:
    return Pipeline([
        ("clean", FunctionTransformer(clean_comments, validate=False)),
        ("tfidf", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                     token_pattern=r"(?u)\b\w[\w']*\b", max_features=85000)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                     sublinear_tf=True, max_features=60000)),
        ])),
        ("classifier", LogisticRegression(max_iter=350, tol=1e-3, random_state=SEED)),
    ])


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def train(data: Path, models: Path, reports: Path) -> dict:
    x_train, y_train = read_split(data / "train.csv")
    x_test, y_test = read_split(data / "test.csv")
    pipeline = training_pipeline()
    folds = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED)
    grid = [
        {"tfidf__char": ["drop"], "tfidf__word__min_df": [1, 2],
         "classifier__C": [4, 16], "classifier__class_weight": [None, "balanced"]},
        {"tfidf__transformer_weights": [{"word": 1, "char": 0.7}],
         "classifier__C": [4, 16], "classifier__class_weight": ["balanced"]},
    ]
    search = GridSearchCV(pipeline, grid, scoring="f1_macro", cv=folds,
                          error_score="raise", verbose=1)
    with threadpool_limits(limits=2):
        dummy = cross_validate(DummyClassifier(strategy="most_frequent"),
                               [[0]] * len(y_train), y_train, cv=folds, scoring="f1_macro")
        svm_pipeline = clone(pipeline).set_params(
            tfidf__char="drop", classifier=LinearSVC(random_state=SEED, class_weight="balanced")
        )
        svm = cross_validate(svm_pipeline, x_train, y_train, cv=folds, scoring="f1_macro")
        search.fit(x_train, y_train)
        best = search.best_estimator_
        predictions = best.predict(x_test)

    models.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    artifact = models / "sentiment_pipeline.joblib"
    joblib.dump(best, artifact, compress=3)
    joblib.dump(best.named_steps["tfidf"], models / "vectorizer.joblib", compress=3)
    joblib.dump(best.named_steps["classifier"], models / "classifier.joblib", compress=3)
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    metadata = {
        "model_version": sha[:12],
        "pipeline_sha256": sha,
        "runtime_versions": {name: importlib.metadata.version(name) for name in
                             ("scikit-learn", "numpy", "scipy", "joblib")},
        "labels": LABELS,
        "data": json.loads((data / "metadata.json").read_text(encoding="utf-8")),
        "parameters": search.best_params_,
    }
    save_json(models / "metadata.json", metadata)
    label_order = sorted(LABELS)
    metrics = {
        "model_version": sha[:12],
        "accuracy": accuracy_score(y_test, predictions),
        "classification_report": classification_report(
            y_test, predictions, labels=label_order, target_names=[LABELS[i] for i in label_order],
            output_dict=True, zero_division=0,
        ),
        "label_order": label_order,
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=label_order).tolist(),
        "cv_macro_f1": {
            "majority": float(dummy["test_score"].mean()),
            "linear_svm": float(svm["test_score"].mean()),
            "best_logistic_regression": float(search.best_score_),
        },
        "trials": [{"parameters": parameters, "macro_f1": float(score)}
                   for parameters, score in zip(search.cv_results_["params"],
                                                search.cv_results_["mean_test_score"], strict=True)],
        "benchmark": benchmark(joblib.load(artifact), x_test),
    }
    save_json(reports / "metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate the sentiment classifier")
    parser.add_argument("--data", type=Path, default=PROCESSED)
    parser.add_argument("--models", type=Path, default=MODELS)
    parser.add_argument("--reports", type=Path, default=REPORTS)
    args = parser.parse_args()
    result = train(args.data, args.models, args.reports)
    print(json.dumps({k: v for k, v in result.items() if k != "trials"}, indent=2))


if __name__ == "__main__":
    main()
