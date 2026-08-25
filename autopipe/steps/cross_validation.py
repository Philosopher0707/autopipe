"""Cross-validation and data splitting steps."""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import (
    GroupKFold,
    KFold,
    StratifiedKFold,
    TimeSeriesSplit,
    train_test_split,
)

from autopipe.core.step import Step

logger = logging.getLogger(__name__)


class CrossValidationStep(Step):
    """Cross-validation step for robust model evaluation.

    Supports various CV strategies:
    - K-Fold
    - Stratified K-Fold
    - Time Series Split
    - Group K-Fold
    """

    def __init__(
        self,
        name: str,
        strategy: str = "kfold",
        n_splits: int = 5,
        shuffle: bool = True,
        random_state: int = 42,
        stratify: bool = False,
        groups: Optional[np.ndarray] = None,
        metrics: Optional[List[str]] = None,
        return_train_score: bool = True,
        n_jobs: int = -1,
        **kwargs,
    ):
        """
        Args:
            name: Step name
            strategy: CV strategy ('kfold', 'stratified', 'timeseries', 'group')
            n_splits: Number of folds
            shuffle: Whether to shuffle data before splitting
            random_state: Random seed
            stratify: Whether to stratify splits
            groups: Group labels for GroupKFold
            metrics: Scoring metrics to compute
            return_train_score: Whether to compute train scores
            n_jobs: Number of parallel jobs
        """
        super().__init__(name, **kwargs)
        self.strategy = strategy
        self.n_splits = n_splits
        self.shuffle = shuffle
        self.random_state = random_state
        self.stratify = stratify
        self.groups = groups
        self.metric_names = metrics or ["accuracy"]
        self.return_train_score = return_train_score
        self.n_jobs = n_jobs

        self.cv_results = None
        self.best_fold_idx = None

    def get_cv_splitter(self, y: np.ndarray = None) -> Any:
        """Get the appropriate CV splitter."""
        if self.strategy == "kfold":
            return KFold(
                n_splits=self.n_splits, shuffle=self.shuffle, random_state=self.random_state
            )
        elif self.strategy == "stratified":
            return StratifiedKFold(
                n_splits=self.n_splits, shuffle=self.shuffle, random_state=self.random_state
            )
        elif self.strategy == "timeseries":
            return TimeSeriesSplit(n_splits=self.n_splits)
        elif self.strategy == "group":
            return GroupKFold(n_splits=self.n_splits)
        else:
            raise ValueError(f"Unknown CV strategy: {self.strategy}")

    def run(
        self,
        model_builder: Callable,
        X: np.ndarray,
        y: np.ndarray,
        groups: Optional[np.ndarray] = None,
        fit_params: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run cross-validation.

        Args:
            model_builder: Callable that returns an unfitted model
            X: Feature matrix
            y: Target values
            groups: Optional group labels
            fit_params: Additional parameters for model.fit()

        Returns:
            Dictionary with CV results
        """
        cv = self.get_cv_splitter(y)

        fold_results = []
        fold_models = []

        for fold_idx, (train_idx, val_idx) in enumerate(cv.split(X, y, groups)):
            logger.info(f"Training fold {fold_idx + 1}/{self.n_splits}")

            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Clone model for this fold
            model = model_builder()

            # Fit model
            fit_kwargs = fit_params or {}
            model.fit(X_train, y_train, **fit_kwargs)

            # Evaluate
            train_score = self._score_model(model, X_train, y_train)
            val_score = self._score_model(model, X_val, y_val)

            fold_result = {
                "fold": fold_idx,
                "train_score": train_score,
                "val_score": val_score,
                "train_size": len(train_idx),
                "val_size": len(val_idx),
            }
            fold_results.append(fold_result)
            fold_models.append(model)

            self.log_metrics(
                **{f"fold_{fold_idx}_train_score": train_score},
                **{f"fold_{fold_idx}_val_score": val_score},
            )

        # Aggregate results
        train_scores = [r["train_score"] for r in fold_results]
        val_scores = [r["val_score"] for r in fold_results]

        self.cv_results = {
            "fold_results": fold_results,
            "fold_models": fold_models,
            "mean_train_score": np.mean(train_scores),
            "std_train_score": np.std(train_scores),
            "mean_val_score": np.mean(val_scores),
            "std_val_score": np.std(val_scores),
            "best_fold_idx": np.argmax(val_scores),
            "worst_fold_idx": np.argmin(val_scores),
        }

        self.log_metrics(
            mean_train_score=self.cv_results["mean_train_score"],
            std_train_score=self.cv_results["std_train_score"],
            mean_val_score=self.cv_results["mean_val_score"],
            std_val_score=self.cv_results["std_val_score"],
        )

        return self.cv_results

    def _score_model(self, model, X: np.ndarray, y: np.ndarray) -> float:
        """Score model on data."""
        from sklearn.metrics import get_scorer

        # Use first metric for primary scoring
        scorer = get_scorer(self.metric_names[0])
        return scorer(model, X, y)

    def get_best_model(self) -> Any:
        """Get the model from the best fold."""
        if self.cv_results is None:
            raise ValueError("Cross-validation has not been run")

        best_idx = self.cv_results["best_fold_idx"]
        return self.cv_results["fold_models"][best_idx]

    def visualize(self, **kwargs):
        """Visualize CV results."""
        if self.cv_results is None:
            return

        import matplotlib.pyplot as plt

        fold_results = self.cv_results["fold_results"]

        _fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Plot 1: Train vs Val scores
        folds = [r["fold"] for r in fold_results]
        train_scores = [r["train_score"] for r in fold_results]
        val_scores = [r["val_score"] for r in fold_results]

        ax1.plot(folds, train_scores, "o-", label="Train", linewidth=2)
        ax1.plot(folds, val_scores, "s-", label="Validation", linewidth=2)
        ax1.axhline(
            self.cv_results["mean_val_score"],
            color="r",
            linestyle="--",
            label=f"Mean Val: {self.cv_results['mean_val_score']:.4f}",
        )
        ax1.fill_between(
            folds,
            self.cv_results["mean_val_score"] - self.cv_results["std_val_score"],
            self.cv_results["mean_val_score"] + self.cv_results["std_val_score"],
            alpha=0.2,
            color="r",
        )
        ax1.set_xlabel("Fold")
        ax1.set_ylabel("Score")
        ax1.set_title(f"{self.name} - Cross-Validation Scores")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Score distribution
        ax2.hist(val_scores, bins=10, alpha=0.7, edgecolor="black")
        ax2.axvline(
            self.cv_results["mean_val_score"],
            color="r",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {self.cv_results['mean_val_score']:.4f}",
        )
        ax2.axvline(
            self.cv_results["mean_val_score"] + self.cv_results["std_val_score"],
            color="orange",
            linestyle=":",
            alpha=0.7,
        )
        ax2.axvline(
            self.cv_results["mean_val_score"] - self.cv_results["std_val_score"],
            color="orange",
            linestyle=":",
            alpha=0.7,
        )
        ax2.set_xlabel("Validation Score")
        ax2.set_ylabel("Frequency")
        ax2.set_title("Score Distribution")
        ax2.legend()

        plt.tight_layout()
        plt.savefig(f"{self.name}_cv_results.png", dpi=150, bbox_inches="tight")
        plt.close()


class NestedCrossValidationStep(Step):
    """Nested cross-validation for unbiased hyperparameter evaluation."""

    def __init__(
        self,
        name: str,
        outer_splits: int = 5,
        inner_splits: int = 3,
        random_state: int = 42,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.outer_splits = outer_splits
        self.inner_splits = inner_splits
        self.random_state = random_state

    def run(
        self,
        model_builder: Callable,
        param_grid: Dict[str, List],
        X: np.ndarray,
        y: np.ndarray,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run nested cross-validation with grid search."""
        from itertools import product

        outer_cv = KFold(n_splits=self.outer_splits, shuffle=True, random_state=self.random_state)

        outer_results = []

        for outer_fold, (train_idx, test_idx) in enumerate(outer_cv.split(X, y)):
            logger.info(f"Outer fold {outer_fold + 1}/{self.outer_splits}")

            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # Inner CV for hyperparameter selection
            inner_cv = KFold(
                n_splits=self.inner_splits, shuffle=True, random_state=self.random_state
            )

            # Grid search on inner CV
            best_score = -float("inf")
            best_params = None

            param_combinations = [
                dict(zip(param_grid.keys(), v, strict=False)) for v in product(*param_grid.values())
            ]

            for params in param_combinations:
                inner_scores = []

                for inner_train_idx, inner_val_idx in inner_cv.split(X_train, y_train):
                    X_inner_train = X_train[inner_train_idx]
                    y_inner_train = y_train[inner_train_idx]
                    X_inner_val = X_train[inner_val_idx]
                    y_inner_val = y_train[inner_val_idx]

                    model = model_builder(**params)
                    model.fit(X_inner_train, y_inner_train)

                    score = model.score(X_inner_val, y_inner_val)
                    inner_scores.append(score)

                mean_score = np.mean(inner_scores)
                if mean_score > best_score:
                    best_score = mean_score
                    best_params = params

            # Train final model on full train set with best params
            final_model = model_builder(**best_params)
            final_model.fit(X_train, y_train)

            # Evaluate on test set
            test_score = final_model.score(X_test, y_test)

            outer_results.append(
                {
                    "outer_fold": outer_fold,
                    "best_params": best_params,
                    "inner_cv_score": best_score,
                    "outer_test_score": test_score,
                }
            )

            self.log_metrics(
                **{f"outer_{outer_fold}_inner_score": best_score},
                **{f"outer_{outer_fold}_test_score": test_score},
            )

        # Aggregate results
        test_scores = [r["outer_test_score"] for r in outer_results]

        return {
            "outer_results": outer_results,
            "mean_test_score": np.mean(test_scores),
            "std_test_score": np.std(test_scores),
            "all_test_scores": test_scores,
        }


class DataSplitterStep(Step):
    """Comprehensive data splitting step.

    Supports various splitting strategies:
    - Train/Val/Test split
    - Stratified splitting
    - Time-based splitting
    """

    def __init__(
        self,
        name: str,
        train_size: float = 0.7,
        val_size: float = 0.15,
        test_size: float = 0.15,
        stratify: bool = False,
        stratify_column: Optional[str] = None,
        random_state: int = 42,
        shuffle: bool = True,
        time_column: Optional[str] = None,
        **kwargs,
    ):
        """
        Args:
            train_size: Fraction for training
            val_size: Fraction for validation
            test_size: Fraction for testing
            stratify: Whether to stratify split
            stratify_column: Column to stratify on
            random_state: Random seed
            shuffle: Whether to shuffle data
            time_column: Column for time-based splitting
        """
        super().__init__(name, **kwargs)
        self.train_size = train_size
        self.val_size = val_size
        self.test_size = test_size
        self.stratify = stratify
        self.stratify_column = stratify_column
        self.random_state = random_state
        self.shuffle = shuffle
        self.time_column = time_column

        self.splits = None

    def run(
        self, data: pd.DataFrame, target_column: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Split data into train/val/test sets.

        Args:
            data: DataFrame with features and optional target
            target_column: Name of target column

        Returns:
            Dictionary with splits
        """
        if self.time_column and self.time_column in data.columns:
            # Time-based split
            data = data.sort_values(self.time_column)

            n = len(data)
            train_end = int(n * self.train_size)
            val_end = train_end + int(n * self.val_size)

            train_data = data.iloc[:train_end]
            val_data = data.iloc[train_end:val_end]
            test_data = data.iloc[val_end:]
        else:
            # Random split
            if target_column and self.stratify:
                y = data[target_column].values
            else:
                y = None

            # First split: separate test
            train_val_data, test_data = train_test_split(
                data,
                test_size=self.test_size,
                stratify=y if self.stratify else None,
                random_state=self.random_state,
                shuffle=self.shuffle,
            )

            # Second split: separate train and val
            val_ratio = self.val_size / (self.train_size + self.val_size)

            if self.stratify and target_column:
                y_train_val = train_val_data[target_column].values
            else:
                y_train_val = None

            train_data, val_data = train_test_split(
                train_val_data,
                test_size=val_ratio,
                stratify=y_train_val if self.stratify else None,
                random_state=self.random_state,
                shuffle=self.shuffle,
            )

        self.splits = {
            "train": train_data,
            "val": val_data,
            "test": test_data,
            "train_size": len(train_data),
            "val_size": len(val_data),
            "test_size": len(test_data),
        }

        self.log_metrics(
            train_size=len(train_data),
            val_size=len(val_data),
            test_size=len(test_data),
            train_ratio=len(train_data) / len(data),
            val_ratio=len(val_data) / len(data),
            test_ratio=len(test_data) / len(data),
        )

        return self.splits

    def get_train_val_test(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Get train, validation, and test data."""
        if self.splits is None:
            raise ValueError("Data has not been split")
        return self.splits["train"], self.splits["val"], self.splits["test"]

    def visualize(self, **kwargs):
        """Visualize data splits."""
        if self.splits is None:
            return

        import matplotlib.pyplot as plt

        splits = ["Train", "Validation", "Test"]
        sizes = [self.splits["train_size"], self.splits["val_size"], self.splits["test_size"]]
        colors = ["#2ecc71", "#f39c12", "#e74c3c"]

        _fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Pie chart
        ax1.pie(sizes, labels=splits, autopct="%1.1f%%", colors=colors, startangle=90)
        ax1.set_title(f"{self.name} - Data Split Distribution")

        # Bar chart with sizes
        bars = ax2.bar(splits, sizes, color=colors, alpha=0.7, edgecolor="black")
        ax2.set_ylabel("Number of Samples")
        ax2.set_title("Split Sizes")

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{int(height):,}",
                ha="center",
                va="bottom",
            )

        plt.tight_layout()
        plt.savefig(f"{self.name}_splits.png", dpi=150, bbox_inches="tight")
        plt.close()


class StratifiedGroupKFoldStep(Step):
    """Custom CV step for stratified group k-fold.

    Ensures that:
    - Groups don't appear in multiple folds
    - Class distribution is similar across folds
    """

    def __init__(
        self, name: str, n_splits: int = 5, shuffle: bool = True, random_state: int = 42, **kwargs
    ):
        super().__init__(name, **kwargs)
        self.n_splits = n_splits
        self.shuffle = shuffle
        self.random_state = random_state

    def run(self, X: np.ndarray, y: np.ndarray, groups: np.ndarray, **kwargs) -> Dict[str, Any]:
        """Create stratified group k-fold splits.

        Args:
            X: Features
            y: Targets
            groups: Group labels

        Returns:
            Dictionary with fold indices
        """
        # Create group-level labels (majority class per group)
        unique_groups = np.unique(groups)
        group_labels = []

        for group in unique_groups:
            group_mask = groups == group
            group_y = y[group_mask]
            # Use majority class as group label
            counts = np.bincount(group_y.astype(int))
            group_labels.append(np.argmax(counts))

        group_labels = np.array(group_labels)

        # Use stratified k-fold on groups
        skf = StratifiedKFold(
            n_splits=self.n_splits, shuffle=self.shuffle, random_state=self.random_state
        )

        folds = []
        for fold_idx, (train_group_idx, val_group_idx) in enumerate(
            skf.split(unique_groups, group_labels)
        ):
            train_groups = unique_groups[train_group_idx]
            val_groups = unique_groups[val_group_idx]

            # Convert group indices to sample indices
            train_idx = np.where(np.isin(groups, train_groups))[0]
            val_idx = np.where(np.isin(groups, val_groups))[0]

            folds.append(
                {
                    "fold": fold_idx,
                    "train_idx": train_idx,
                    "val_idx": val_idx,
                    "train_size": len(train_idx),
                    "val_size": len(val_idx),
                }
            )

        return {"folds": folds, "n_splits": self.n_splits}


class BootstrapValidatorStep(Step):
    """Bootstrap validation for estimating model stability and confidence intervals."""

    def __init__(
        self,
        name: str,
        n_bootstrap: int = 100,
        random_state: int = 42,
        confidence: float = 0.95,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.n_bootstrap = n_bootstrap
        self.random_state = random_state
        self.confidence = confidence

    def run(
        self, model_builder: Callable, X: np.ndarray, y: np.ndarray, metric_fn: Callable, **kwargs
    ) -> Dict[str, Any]:
        """Run bootstrap validation.

        Args:
            model_builder: Callable that returns model
            X: Features
            y: Targets
            metric_fn: Function to compute metric: metric_fn(y_true, y_pred)

        Returns:
            Dictionary with bootstrap statistics
        """
        rng = np.random.RandomState(self.random_state)
        n_samples = len(X)

        scores = []

        for _i in range(self.n_bootstrap):
            # Bootstrap sample
            indices = rng.choice(n_samples, size=n_samples, replace=True)
            oob_indices = np.setdiff1d(np.arange(n_samples), indices)

            X_train = X[indices]
            y_train = y[indices]

            if len(oob_indices) == 0:
                continue

            X_oob = X[oob_indices]
            y_oob = y[oob_indices]

            # Train and evaluate
            model = model_builder()
            model.fit(X_train, y_train)

            y_pred = model.predict(X_oob)
            score = metric_fn(y_oob, y_pred)
            scores.append(score)

        scores = np.array(scores)

        # Compute statistics
        alpha = (1 - self.confidence) / 2
        ci_lower = np.percentile(scores, alpha * 100)
        ci_upper = np.percentile(scores, (1 - alpha) * 100)

        result = {
            "mean_score": np.mean(scores),
            "std_score": np.std(scores),
            "median_score": np.median(scores),
            "min_score": np.min(scores),
            "max_score": np.max(scores),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "scores": scores.tolist(),
            "n_bootstrap": len(scores),
        }

        self.log_metrics(
            bootstrap_mean=result["mean_score"],
            bootstrap_std=result["std_score"],
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        )

        return result

    def visualize(self, **kwargs):
        """Visualize bootstrap distribution."""
        if self.output is None or "scores" not in self.output:
            return

        import matplotlib.pyplot as plt

        scores = self.output["scores"]

        plt.figure(figsize=(10, 6))

        # Histogram
        plt.hist(scores, bins=30, alpha=0.7, edgecolor="black", density=True)

        # Add statistics
        mean = self.output["mean_score"]
        ci_lower = self.output["ci_lower"]
        ci_upper = self.output["ci_upper"]

        plt.axvline(mean, color="r", linestyle="--", linewidth=2, label=f"Mean: {mean:.4f}")
        plt.axvline(
            ci_lower,
            color="orange",
            linestyle=":",
            linewidth=2,
            label=f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]",
        )
        plt.axvline(ci_upper, color="orange", linestyle=":", linewidth=2)

        plt.xlabel("Score")
        plt.ylabel("Density")
        plt.title(f"{self.name} - Bootstrap Score Distribution")
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(f"{self.name}_bootstrap.png", dpi=150, bbox_inches="tight")
        plt.close()
