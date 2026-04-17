"""Minimal AutoPipe pipeline usage example.

This example shows how to:
- build a pipeline with ordered steps
- pass inputs into the pipeline
- access step outputs after execution
"""

import os
import sys

# Ensure the repository root is on PYTHONPATH so the local autopipe package imports correctly
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

from autopipe import Pipeline, DataValidatorStep, DataSplitterStep, SklearnTrainerStep


def create_pipeline() -> Pipeline:
    """Build a simple AutoPipe pipeline."""
    return (
        Pipeline("simple_classification")
        .add_step(
            DataValidatorStep(
                name="validate",
                required_columns=["feature_0", "feature_1", "feature_2", "target"],
                max_null_ratio=0.05,
                check_duplicates=True,
                check_outliers=False,
            )
        )
        .add_step(
            DataSplitterStep(
                name="split",
                depends_on=["validate"],
                train_size=0.7,
                val_size=0.2,
                test_size=0.1,
                stratify=True,
                stratify_column="target",
                random_state=42,
            )
        )
        .add_step(
            SklearnTrainerStep(
                name="train",
                depends_on=["split"],
                model_class=RandomForestClassifier,
                model_params={"n_estimators": 50, "random_state": 42},
                use_cross_validation=True,
                cv_folds=3,
                scoring=["accuracy"],
            )
        )
    )


def make_example_data() -> pd.DataFrame:
    """Create a small synthetic classification dataset."""
    X, y = make_classification(
        n_samples=300,
        n_features=3,
        n_informative=3,
        n_redundant=0,
        n_classes=2,
        random_state=42,
    )

    df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(X.shape[1])])
    df["target"] = y
    return df


def main() -> None:
    pipeline = create_pipeline()
    data = make_example_data()

    result = pipeline.run(initial_inputs={"data": data})

    print("Pipeline execution complete")
    print("Step outputs:")
    for step_name, output in result.items():
        print(f"- {step_name}: {type(output).__name__}")

    splitter_output = result["split"]
    model = result["train"]

    print(f"Train rows: {splitter_output['train_size']}")
    print(f"Validation rows: {splitter_output['val_size']}")
    print(f"Test rows: {splitter_output['test_size']}")
    print(f"Trained model type: {model.__class__.__name__}")


if __name__ == "__main__":
    main()
