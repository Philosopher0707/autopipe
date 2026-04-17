"""Example comprehensive ML/DL pipeline using AutoPipe.

This example demonstrates how to use AutoPipe for a complete ML workflow:
1. Data loading and validation
2. Feature engineering
3. Preprocessing
4. Feature selection
5. Data splitting
6. Model training with hyperparameter tuning
7. Model evaluation
8. Model explainability
9. Model registry
"""

import os
import sys
import numpy as np

# Ensure the repository root is on PYTHONPATH so the local autopipe package imports correctly
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from autopipe import (
    Pipeline,
    DataLoaderStep,
    DataValidatorStep,
    FeatureEngineeringStep,
    DataPreprocessorStep,
    FeatureSelectionStep,
    DataSplitterStep,
    SklearnTrainerStep,
    ModelEvaluatorStep,
    HyperparameterTuner,
    SearchStrategy,
    continuous, discrete, categorical,
    get_registry,
)
from sklearn.ensemble import RandomForestClassifier
import pandas as pd


def create_ml_pipeline():
    """Create a complete ML pipeline."""
    
    # Step 1: Load data
    data_loader = DataLoaderStep(
        source="data/bank_churn.csv",  # Example dataset
        format="csv"
    )
    
    # Step 2: Validate data
    validator = DataValidatorStep(
        required_columns=["customer_id", "age", "salary", "churned"],
        max_null_ratio=0.1,
        check_duplicates=True,
        check_outliers=True,
    )
    
    # Step 3: Feature engineering
    feature_engineer = FeatureEngineeringStep(
        datetime_columns=["join_date"],
        interaction_columns=["age", "salary"],
        binning_columns={"age": 5},
    )
    
    # Step 4: Preprocess
    preprocessor = DataPreprocessorStep(
        numeric_scaling="standard",
        categorical_encoding="onehot",
        imputation_strategy="mean",
    )
    
    # Step 5: Feature selection
    feature_selector = FeatureSelectionStep(
        method="kbest",
        k=10,
        score_func="mutual_info",
    )
    
    # Step 6: Split data
    splitter = DataSplitterStep(
        train_size=0.7,
        val_size=0.15,
        test_size=0.15,
        stratify=True,
        random_state=42,
    )
    
    # Step 7: Train model
    trainer = SklearnTrainerStep(
        model_class=RandomForestClassifier,
        model_params={"n_estimators": 100, "random_state": 42},
        use_cross_validation=True,
        cv_folds=5,
    )
    
    # Step 8: Evaluate
    evaluator = ModelEvaluatorStep(
        task_type="classification",
        metrics=["accuracy", "precision", "recall", "f1", "roc_auc"],
        calculate_proba=True,
        error_analysis=True,
    )
    
    # Build pipeline
    pipeline = (
        Pipeline("bank_churn_prediction")
        .add_step(data_loader)
        .add_step(validator)
        .add_step(feature_engineer)
        .add_step(preprocessor)
        .add_step(feature_selector)
        .add_step(splitter)
        .add_step(trainer)
        .add_step(evaluator)
    )
    
    return pipeline


def hyperparameter_tuning_example():
    """Example of hyperparameter tuning."""
    
    from sklearn.datasets import make_classification
    from sklearn.model_selection import cross_val_score
    
    # Generate synthetic data
    X, y = make_classification(n_samples=1000, n_features=20, n_classes=2, random_state=42)
    
    # Define search space
    param_space = {
        "n_estimators": discrete(50, 500),
        "max_depth": discrete(3, 20),
        "min_samples_split": discrete(2, 20),
        "max_features": categorical(["sqrt", "log2", None]),
    }
    
    # Define objective function
    def objective(params):
        model = RandomForestClassifier(**params, random_state=42)
        scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
        return {"accuracy": scores.mean()}
    
    # Run tuning
    tuner = HyperparameterTuner(
        strategy=SearchStrategy.BAYESIAN,
        n_trials=50,
        direction="maximize",
        random_state=42,
    )
    
    best_trial = tuner.fit(param_space, objective)
    
    print(f"Best params: {best_trial.params}")
    print(f"Best score: {best_trial.metrics}")
    
    return best_trial


def model_registry_example():
    """Example of model registry usage."""
    
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.datasets import make_classification
    
    # Train a model
    X, y = make_classification(n_samples=1000, n_features=20, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Get registry
    registry = get_registry()
    
    # Register model
    metadata = registry.register(
        model=model,
        name="churn_prediction_model",
        metrics={"accuracy": 0.92, "f1": 0.91, "roc_auc": 0.95},
        parameters={"n_estimators": 100, "max_depth": 10},
        tags={"stage": "production", "team": "ml"},
    )
    
    print(f"Registered model: {metadata.model_id}")
    print(f"Version: {metadata.version}")
    
    # Load model back
    loaded_model = registry.load("churn_prediction_model")
    
    # Compare versions
    comparison = registry.compare_versions("churn_prediction_model")
    print(comparison)
    
    return metadata


def complete_workflow_example():
    """Complete end-to-end ML workflow."""
    
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Create pipeline
    pipeline = create_ml_pipeline()
    
    # Run pipeline
    # Note: This requires actual data files
    # result = pipeline.execute()
    
    # Or run step by step
    context = {}
    
    # Simulate data
    np.random.seed(42)
    data = pd.DataFrame({
        "customer_id": range(1000),
        "age": np.random.randint(18, 80, 1000),
        "salary": np.random.normal(50000, 15000, 1000),
        "churned": np.random.randint(0, 2, 1000),
    })
    
    # Process through pipeline steps
    validator = DataValidatorStep(
        required_columns=["age", "salary", "churned"],
        max_null_ratio=0.5,
    )
    data_validated = validator.execute(data, context)
    
    print(f"Validated data shape: {data_validated.shape}")
    print(f"Validation results: {context.get('validation_results')}")
    
    # Feature engineering
    feature_engineer = FeatureEngineeringStep(
        interaction_columns=["age", "salary"],
    )
    data_engineered = feature_engineer.execute(data_validated, context)
    print(f"Engineered features: {context.get('feature_engineering')}")
    
    return context


if __name__ == "__main__":
    print("=" * 60)
    print("AutoPipe Comprehensive ML/DL Pipeline Example")
    print("=" * 60)
    
    # Example 1: Hyperparameter Tuning
    print("\n1. Hyperparameter Tuning Example")
    print("-" * 40)
    # best_params = hyperparameter_tuning_example()
    
    # Example 2: Model Registry
    print("\n2. Model Registry Example")
    print("-" * 40)
    # metadata = model_registry_example()
    
    # Example 3: Complete Workflow
    print("\n3. Complete Workflow Example")
    print("-" * 40)
    context = complete_workflow_example()
    
    print("\nPipeline execution complete!")
    print(f"Context contains: {list(context.keys())}")
