"""
World-Class ML Pipeline Example
==============================

This example demonstrates a comprehensive, production-ready ML pipeline using AutoPipe.
Features demonstrated:
- Data loading and feature engineering
- Cross-validation
- Multiple model comparisons
- Hyperparameter tuning
- Deep learning (PyTorch)
- Model explainability (SHAP, LIME, Permutation Importance)
- Model registry (versioning and deployment stages)
- Data drift detection
- A/B testing framework

Author: AutoPipe Team
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.datasets import make_classification
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Import AutoPipe components
from autopipe.monitoring import (
    StatisticalDriftDetectorStep,
)
from autopipe.registry import get_registry
from autopipe.steps import (
    BootstrapValidatorStep,
    CrossValidationStep,
)
from autopipe.steps.deep_learning import (
    PyTorchTrainerStep,
)
from autopipe.steps.explainability import (
    ExplainabilityPipeline,
)


def create_sample_data(n_samples=1000, n_features=20, n_classes=2):
    """Create synthetic dataset."""
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_features // 2,
        n_redundant=n_features // 4,
        n_classes=n_classes,
        random_state=42,
    )

    feature_names = [f"feature_{i}" for i in range(n_features)]

    df = pd.DataFrame(X, columns=feature_names)
    df["target"] = y

    return df, feature_names


def create_pytorch_model(input_dim=20, hidden_dim=64, output_dim=2):
    """Create a simple PyTorch neural network."""

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(input_dim, hidden_dim)
            self.fc2 = nn.Linear(hidden_dim, hidden_dim)
            self.fc3 = nn.Linear(hidden_dim, output_dim)
            self.dropout = nn.Dropout(0.3)

        def forward(self, x):
            x = torch.relu(self.fc1(x))
            x = self.dropout(x)
            x = torch.relu(self.fc2(x))
            x = self.dropout(x)
            x = self.fc3(x)
            return x

    return Net


def example_1_cv_and_training():
    """Example 1: Cross-validation and model training."""
    print("=" * 60)
    print("Example 1: Cross-Validation and Model Training")
    print("=" * 60)

    # Create data
    df, feature_names = create_sample_data(n_samples=1000)
    X = df[feature_names].values
    y = df["target"].values

    # Cross-validation step
    cv_step = CrossValidationStep(
        name="rf_cv", strategy="stratified", n_splits=5, metrics=["accuracy", "f1"]
    )

    # Model builder function
    def build_rf():
        return RandomForestClassifier(n_estimators=100, random_state=42)

    # Run CV
    cv_results = cv_step.run(model_builder=build_rf, X=X, y=y)

    print("\nCross-Validation Results:")
    print(
        f"  Mean Train Score: {cv_results['mean_train_score']:.4f} ± {cv_results['std_train_score']:.4f}"
    )
    print(
        f"  Mean Val Score: {cv_results['mean_val_score']:.4f} ± {cv_results['std_val_score']:.4f}"
    )
    print(f"  Best Fold: {cv_results['best_fold_idx']}")

    return cv_results


def example_2_bootstrap_validation():
    """Example 2: Bootstrap validation for confidence intervals."""
    print("=" * 60)
    print("Example 2: Bootstrap Validation")
    print("=" * 60)

    df, feature_names = create_sample_data(n_samples=500)
    X = df[feature_names].values
    y = df["target"].values

    def build_model():
        return RandomForestClassifier(n_estimators=50, random_state=42)

    from sklearn.metrics import accuracy_score

    bootstrap_step = BootstrapValidatorStep(
        name="bootstrap_validation", n_bootstrap=100, confidence=0.95
    )

    results = bootstrap_step.run(model_builder=build_model, X=X, y=y, metric_fn=accuracy_score)

    print("\nBootstrap Validation Results:")
    print(f"  Mean Score: {results['mean_score']:.4f}")
    print(f"  Std Score: {results['std_score']:.4f}")
    print(f"  95% CI: [{results['ci_lower']:.4f}, {results['ci_upper']:.4f}]")

    return results


def example_3_deep_learning():
    """Example 3: Deep Learning with PyTorch."""
    print("=" * 60)
    print("Example 3: Deep Learning Training")
    print("=" * 60)

    df, feature_names = create_sample_data(n_samples=1000, n_features=20, n_classes=2)
    X = df[feature_names].values
    y = df["target"].values

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PyTorch trainer step
    dl_step = PyTorchTrainerStep(
        name="pytorch_classifier",
        model_builder=create_pytorch_model(input_dim=20, hidden_dim=64, output_dim=2),
        loss_fn="cross_entropy",
        optimizer="adam",
        learning_rate=0.001,
        epochs=50,
        batch_size=32,
        validation_split=0.2,
        early_stopping_patience=10,
        metrics=["accuracy", "f1"],
    )

    results = dl_step.run(X_train=X_scaled, y_train=y, task="classification")

    print("\nPyTorch Training Results:")
    print(f"  Device: {results['device']}")
    print(f"  Best Val Loss: {min(results['history']['val_loss']):.4f}")
    print(f"  Final Train Accuracy: {results['history']['train_metrics']['accuracy'][-1]:.4f}")

    return results


def example_4_model_registry():
    """Example 4: Model Registry with versioning."""
    print("=" * 60)
    print("Example 4: Model Registry and Versioning")
    print("=" * 60)

    # Get registry
    registry = get_registry(registry_dir="./.autopipe_registry_demo")

    # Train multiple models
    df, feature_names = create_sample_data(n_samples=800)
    X = df[feature_names].values
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = [
        ("RandomForest_v1", RandomForestClassifier(n_estimators=50, random_state=42)),
        (
            "RandomForest_v2",
            RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
        ),
        ("GradientBoosting", GradientBoostingClassifier(random_state=42)),
    ]

    registered = []

    for name, model in models:
        model.fit(X_train, y_train)
        train_acc = model.score(X_train, y_train)
        test_acc = model.score(X_test, y_test)

        metadata = registry.register(
            model=model,
            name=name,
            metrics={"train_accuracy": train_acc, "test_accuracy": test_acc},
            parameters=model.get_params(),
            tags={"model_type": "sklearn", "dataset": "demo"},
            framework="sklearn",
        )

        registered.append(metadata)
        print(f"\nRegistered {name} v{metadata.version}")
        print(f"  Train Accuracy: {train_acc:.4f}")
        print(f"  Test Accuracy: {test_acc:.4f}")

    # Compare versions
    if len(registered) >= 2:
        comparison = registry.compare_versions(registered[0].name, 1, 2)
        print("\nModel Comparison (v1 vs v2):")
        print(comparison.to_markdown())

    # Promote best to production
    best = registered[np.argmax([r.metrics["test_accuracy"] for r in registered])]
    registry.promote_to_production(best.name, best.version)
    print(f"\nPromoted {best.name} v{best.version} to production")

    return registered


def example_5_explainability():
    """Example 5: Model Explainability."""
    print("=" * 60)
    print("Example 5: Model Explainability")
    print("=" * 60)

    df, feature_names = create_sample_data(n_samples=500, n_features=15)
    X = df[feature_names].values
    y = df["target"].values

    X_train, X_test, y_train, _y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    # Train model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Run explainability pipeline
    explainer = ExplainabilityPipeline(
        name="feature_importance_analysis",
        methods=["feature_importance", "permutation", "shap"],
        feature_names=feature_names,
    )

    results = explainer.run(model=model, X_train=X_train, y_train=y_train, X_test=X_test)

    print("\nExplainability Results:")
    if "shap" in results["explanations"]:
        top_shap = results["explanations"]["shap"]["top_features"][:5]
        print("\nTop 5 SHAP Features:")
        for feat, importance in top_shap:
            print(f"  {feat}: {importance:.4f}")

    if "aggregated_ranks" in results:
        print("\nTop 5 Aggregated Feature Importance:")
        for _i, (feat, rank) in enumerate(list(results["aggregated_ranks"].items())[:5]):
            print(f"  {feat}: rank {rank:.2f}")

    return results


def example_6_drift_detection():
    """Example 6: Data Drift Detection."""
    print("=" * 60)
    print("Example 6: Data Drift Detection")
    print("=" * 60)

    # Create reference data
    df_ref, feature_names = create_sample_data(n_samples=1000)

    # Simulate drift by modifying current data
    df_current = df_ref.copy()
    # Add drift to some features
    for i in range(5):
        df_current[f"feature_{i}"] = df_current[f"feature_{i}"] + np.random.normal(
            5, 1, len(df_current)
        )

    # Run drift detection
    drift_detector = StatisticalDriftDetectorStep(
        name="drift_detection", method="ks", threshold=0.05
    )

    results = drift_detector.run(
        reference_data=df_ref, current_data=df_current, feature_names=feature_names
    )

    print("\nDrift Detection Results:")
    print(f"  Total Features Checked: {results['total_features']}")
    print(f"  Features with Drift: {results['drift_detected_count']}")
    print(f"  Drift Ratio: {results['drift_ratio']:.2%}")

    if results["drift_detected_count"] > 0:
        print("\nDrifted Features:")
        for report in results["drift_reports"]:
            if report.drift_detected:
                print(f"  - {report.feature_name}: {report.metric_name}={report.metric_value:.4f}")

    return results


def run_all_examples():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("AUTOPICE - World-Class ML Pipeline Examples")
    print("=" * 60 + "\n")

    examples = [
        ("Cross-Validation", example_1_cv_and_training),
        ("Bootstrap Validation", example_2_bootstrap_validation),
        ("Deep Learning", example_3_deep_learning),
        ("Model Registry", example_4_model_registry),
        ("Explainability", example_5_explainability),
        ("Drift Detection", example_6_drift_detection),
    ]

    results = {}
    for name, func in examples:
        try:
            print("\n" + "=" * 60)
            print(f"Running: {name}")
            print("=" * 60)
            results[name] = func()
            print(f"\n✓ {name} completed successfully")
        except Exception as e:
            print(f"\n✗ {name} failed: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print("All Examples Complete!")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = run_all_examples()
