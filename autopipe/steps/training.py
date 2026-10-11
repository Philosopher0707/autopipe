"""AutoPipe Training Steps - Comprehensive ML/DL model training.

This module provides training steps for:
- Scikit-learn models (with CV support)
- PyTorch models (with distributed training, mixed precision)
- TensorFlow models (Keras API)
- Transfer learning support
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from autopipe.core.artifacts import record_produced_file
from autopipe.core.step import Step

# Seed used when the run declared none. Historical default, kept so that an
# unseeded run is still reproducible rather than silently random.
_DEFAULT_RANDOM_STATE = 42


@dataclass
class TrainingConfig:
    """Configuration for deep learning training."""

    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    optimizer: str = "adam"
    optimizer_params: Optional[Dict] = None
    scheduler: Optional[str] = None
    scheduler_params: Optional[Dict] = None
    early_stopping_patience: int = 10
    early_stopping_min_delta: float = 0.0
    gradient_clip_val: Optional[float] = None
    mixed_precision: bool = False
    validation_split: float = 0.1
    shuffle: bool = True
    verbose: int = 1


class SklearnTrainerStep(Step):
    """Scikit-learn model training step with cross-validation support.

    Trains any sklearn-compatible estimator with optional cross-validation,
    hyperparameter tracking, and automatic metrics logging.
    """

    def __init__(
        self,
        name: str = "sklearn_trainer",
        model_class: Optional[type] = None,
        model_params: Optional[Dict] = None,
        use_cross_validation: bool = False,
        cv_folds: int = 5,
        cv_strategy: str = "stratified",
        scoring: str | List[str] = None,
        fit_params: Optional[Dict] = None,
        save_path: Optional[str] = None,
        n_jobs: int = 1,
        target_column: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.model_class = model_class
        self.model_params = model_params or {}
        self.use_cross_validation = use_cross_validation
        self.cv_folds = cv_folds
        self.cv_strategy = cv_strategy
        self.scoring = scoring or ["accuracy", "precision", "recall", "f1"]
        self.fit_params = fit_params or {}
        self.save_path = save_path
        self.n_jobs = n_jobs
        self.target_column = target_column

        self.model = None
        self.cv_results = {}

    def _resolve_seed(self) -> int:
        """Seed for model randomness, taken from the run's declared seed.

        The engine binds ``self.run_rng`` only for seeded runs (CONTEXT.md
        records the applied seed in provenance), so the seed has to be threaded
        into the estimator here or provenance would attest to a reproducibility
        that training does not have. Unseeded runs keep the historical default,
        which keeps them reproducible too.
        """
        if self.run_rng is not None:
            return self.run_rng.seed
        return _DEFAULT_RANDOM_STATE

    def _frame_to_xy(self, frame: pd.DataFrame):
        """Split a frame into (X, y), using ``target_column`` when declared."""
        if self.target_column is None:
            return frame.iloc[:, :-1].values, frame.iloc[:, -1].values
        if self.target_column not in frame.columns:
            raise ValueError(
                f"target_column {self.target_column!r} is not a column of the input "
                f"(columns: {list(frame.columns)})"
            )
        y = frame[self.target_column].values
        return frame.drop(columns=[self.target_column]).values, y

    def _extract_xy(self, kwargs: Dict[str, Any]):
        """Choose the training input by a FIXED priority, not by kwargs order.

        A splits dict and an ``(X, y)`` tuple both state exactly what to train
        on, so they outrank a bare DataFrame. Choosing by iteration order
        instead let a later raw frame silently override the train split, so the
        model trained on the held-out test rows and reported healthy metrics.
        """
        for value in kwargs.values():
            if isinstance(value, dict) and isinstance(value.get("train"), pd.DataFrame):
                return self._frame_to_xy(value["train"])
        for value in kwargs.values():
            if isinstance(value, tuple) and len(value) == 2:
                X, y = value
                return np.asarray(X), np.asarray(y)
        for value in kwargs.values():
            if isinstance(value, pd.DataFrame):
                return self._frame_to_xy(value)
        for value in kwargs.values():
            if isinstance(value, np.ndarray):
                return value, None
        return None, None

    def run(self, **kwargs) -> Any:
        """Train model with optional cross-validation."""
        import logging

        from sklearn.model_selection import KFold, StratifiedKFold, cross_validate

        logger = logging.getLogger(__name__)

        X_train, y_train = self._extract_xy(kwargs)

        if X_train is None or y_train is None:
            raise ValueError("SklearnTrainerStep requires training data (X) and target labels (y)")

        logger.info(f"Training on {len(X_train)} samples")

        seed = self._resolve_seed()

        # Initialize model
        if self.model_class is None:
            from sklearn.ensemble import RandomForestClassifier

            self.model = RandomForestClassifier(**self.model_params, random_state=seed)
        else:
            params = dict(self.model_params)
            params.setdefault("random_state", seed)
            self.model = self.model_class(**params)

        # Cross-validation
        if self.use_cross_validation:
            logger.info(f"Running {self.cv_folds}-fold cross-validation...")

            if self.cv_strategy == "stratified":
                cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=seed)
            else:
                cv = KFold(n_splits=self.cv_folds, shuffle=True, random_state=seed)

            scoring = self.scoring if isinstance(self.scoring, list) else [self.scoring]
            self.cv_results = cross_validate(
                self.model,
                X_train,
                y_train,
                cv=cv,
                scoring=scoring,
                return_train_score=True,
                n_jobs=self.n_jobs,
            )

            for metric in scoring:
                train_scores = self.cv_results.get(f"train_{metric}", [])
                val_scores = self.cv_results.get(f"test_{metric}", [])

                self.log_metrics(
                    **{f"cv_train_{metric}_mean": np.mean(train_scores)},
                    **{f"cv_val_{metric}_mean": np.mean(val_scores)},
                )

        self.model.fit(X_train, y_train, **self.fit_params)

        self.log_metrics(
            training_samples=len(X_train),
            n_features=X_train.shape[1],
            model_type=self.model.__class__.__name__,
        )

        if self.save_path:
            import joblib

            Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, self.save_path)
            record_produced_file(str(self.save_path))

        return self.model


class HyperparameterTunerStep(Step):
    """Sklearn GridSearchCV / RandomizedSearchCV hyperparameter tuning step."""

    def __init__(
        self,
        name: str = "hyperparameter_tuner",
        model_class: Optional[type] = None,
        param_grid: Optional[Dict] = None,
        search_strategy: str = "grid",
        n_iter: int = 10,
        cv: int = 5,
        scoring: Optional[str] = None,
        n_jobs: int = -1,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.model_class = model_class
        self.param_grid = param_grid or {}
        self.search_strategy = search_strategy
        self.n_iter = n_iter
        self.cv = cv
        self.scoring = scoring
        self.n_jobs = n_jobs
        self.best_estimator_ = None
        self.best_params_ = {}

    def run(self, **kwargs) -> Any:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import GridSearchCV, RandomizedSearchCV

        X, y = None, None
        for value in kwargs.values():
            if isinstance(value, tuple) and len(value) == 2:
                X, y = value
                break
            elif isinstance(value, pd.DataFrame):
                y = value.iloc[:, -1].values
                X = value.iloc[:, :-1].values

        if X is None or y is None:
            raise ValueError("HyperparameterTunerStep requires (X, y) input")

        # Sampling must be seeded from the run's declared seed; otherwise two
        # identical seeded runs search different parameter subsets. The
        # estimator needs the same seed, or the fitted model still differs.
        seed = self.run_rng.seed if self.run_rng is not None else _DEFAULT_RANDOM_STATE
        model = (self.model_class or RandomForestClassifier)()
        if "random_state" in model.get_params():
            model.set_params(random_state=seed)
        SearchCV = GridSearchCV if self.search_strategy == "grid" else RandomizedSearchCV

        search_kwargs = {
            "estimator": model,
            "param_grid": self.param_grid,
            "cv": self.cv,
            "scoring": self.scoring,
            "n_jobs": self.n_jobs,
        }
        if self.search_strategy == "random":
            # RandomizedSearchCV draws candidates from random_state; without it
            # two identical seeded runs search different subsets. GridSearchCV
            # enumerates the grid exhaustively and takes no random_state.
            search_kwargs["random_state"] = seed
            search_kwargs["n_iter"] = self.n_iter
            search_kwargs["param_distributions"] = search_kwargs.pop("param_grid")

        searcher = SearchCV(**search_kwargs)
        searcher.fit(X, y)

        self.best_estimator_ = searcher.best_estimator_
        self.best_params_ = searcher.best_params_
        self.log_metrics(
            best_score=searcher.best_score_,
            **{f"best_{k}": v for k, v in self.best_params_.items() if isinstance(v, (int, float))},
        )
        return self.best_estimator_
