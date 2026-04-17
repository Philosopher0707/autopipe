"""AutoPipe Training Steps - Comprehensive ML/DL model training.

This module provides training steps for:
- Scikit-learn models (with CV support)
- PyTorch models (with distributed training, mixed precision)
- TensorFlow models (Keras API)
- Transfer learning support
"""

from typing import Any, Callable, Dict, List, Optional, Union, Tuple
import numpy as np
import pandas as pd
import warnings
from dataclasses import dataclass
from pathlib import Path

from autopipe.core.step import Step


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
        scoring: Union[str, List[str]] = None,
        fit_params: Optional[Dict] = None,
        save_path: Optional[str] = None,
        n_jobs: int = 1,
        **kwargs
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
        
        self.model = None
        self.cv_results = {}
        
    def run(self, **kwargs) -> Any:
        """Train model with optional cross-validation."""
        import logging
        from sklearn.model_selection import cross_validate, StratifiedKFold, KFold
        
        logger = logging.getLogger(__name__)
        
        # Extract data from inputs
        X_train, y_train = None, None
        
        for key, value in kwargs.items():
            if isinstance(value, dict) and 'train' in value:
                train_data = value.get('train')
                if isinstance(train_data, pd.DataFrame):
                    if y_train is None:
                        y_train = train_data.iloc[:, -1].values
                        X_train = train_data.iloc[:, :-1].values
            elif isinstance(value, tuple) and len(value) == 2:
                X_train, y_train = value
            elif isinstance(value, pd.DataFrame):
                y_train = value.iloc[:, -1].values
                X_train = value.iloc[:, :-1].values
            elif isinstance(value, np.ndarray):
                if X_train is None:
                    X_train = value
        
        if X_train is None or y_train is None:
            raise ValueError("SklearnTrainerStep requires training data (X) and target labels (y)")
        
        logger.info(f"Training on {len(X_train)} samples")
        
        # Initialize model
        if self.model_class is None:
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(**self.model_params, random_state=42)
        else:
            self.model = self.model_class(**self.model_params)
        
        # Cross-validation
        if self.use_cross_validation:
            logger.info(f"Running {self.cv_folds}-fold cross-validation...")
            
            if self.cv_strategy == "stratified":
                cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
            else:
                cv = KFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
            
            scoring = self.scoring if isinstance(self.scoring, list) else [self.scoring]
            self.cv_results = cross_validate(
                self.model, X_train, y_train,
                cv=cv, scoring=scoring, return_train_score=True, n_jobs=self.n_jobs
            )
            
            for metric in scoring:
                train_scores = self.cv_results.get(f'train_{metric}', [])
                val_scores = self.cv_results.get(f'test_{metric}', [])
                
                self.log_metrics(
                    **{f"cv_train_{metric}_mean": np.mean(train_scores)},
                    **{f"cv_val_{metric}_mean": np.mean(val_scores)}
                )
        
        self.model.fit(X_train, y_train, **self.fit_params)
        
        self.log_metrics(
            training_samples=len(X_train),
            n_features=X_train.shape[1],
            model_type=self.model.__class__.__name__
        )
        
        if self.save_path:
            import joblib
            Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, self.save_path)
        
        return self.model


class _PyTorchTrainerStepStub(Step):
    """DEPRECATED: PyTorch model training step.
    
    .. deprecated::
        Use :class:`autopipe.steps.deep_learning.PyTorchTrainerStep` instead.
        This stub provides minimal functionality. Import from deep_learning module
        for full training support.
    """
    
    def __init__(
        self,
        name: str = "pytorch_trainer",
        model_builder: Optional[Callable] = None,
        config: Optional[TrainingConfig] = None,
        loss_fn: Optional[str] = None,
        task_type: str = "classification",
        **kwargs
    ):
        import warnings
        warnings.warn(
            "PyTorchTrainerStep from training module is deprecated. "
            "Use autopipe.steps.deep_learning.PyTorchTrainerStep for full training support.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(name, **kwargs)
        self.model_builder = model_builder
        self.config = config or TrainingConfig()
        self.loss_fn_name = loss_fn or ("cross_entropy" if task_type == "classification" else "mse")
        self.task_type = task_type
        self.history = {'train_loss': [], 'val_loss': []}

    def run(self, **kwargs) -> Any:
        """Build model without training. Use deep_learning.PyTorchTrainerStep for training."""
        try:
            import torch
            import torch.nn as nn
        except ImportError:
            raise ImportError("PyTorch is required. Install with: pip install torch")
        
        # Build model only (no training)
        if self.model_builder:
            self.model = self.model_builder()
        else:
            self.model = nn.Sequential(nn.Linear(10, 2))
        
        return self.model


# Backwards compatibility alias
PyTorchTrainerStep = _PyTorchTrainerStepStub


class _TensorFlowTrainerStepStub(Step):
    """DEPRECATED: TensorFlow/Keras model training step.
    
    .. deprecated::
        Use :class:`autopipe.steps.deep_learning.TensorFlowTrainerStep` instead.
        This stub provides minimal functionality.
    """
    
    def __init__(
        self,
        name: str = "tensorflow_trainer",
        **kwargs
    ):
        import warnings
        warnings.warn(
            "TensorFlowTrainerStep from training module is deprecated. "
            "Use autopipe.steps.deep_learning.TensorFlowTrainerStep for full training support.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(name, **kwargs)
        self.history = None

    def run(self, **kwargs) -> Any:
        try:
            import tensorflow as tf
        except ImportError:
            raise ImportError("TensorFlow is required. Install with: pip install tensorflow")
        
        # Placeholder
        self.model = tf.keras.Sequential([tf.keras.layers.Dense(2, input_shape=(10,))])
        return self.model


# Backwards compatibility alias
TensorFlowTrainerStep = _TensorFlowTrainerStepStub


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
        **kwargs
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
        from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
        from sklearn.ensemble import RandomForestClassifier

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

        model = (self.model_class or RandomForestClassifier)()
        SearchCV = GridSearchCV if self.search_strategy == "grid" else RandomizedSearchCV

        search_kwargs = dict(
            estimator=model,
            param_grid=self.param_grid,
            cv=self.cv,
            scoring=self.scoring,
            n_jobs=self.n_jobs,
        )
        if self.search_strategy == "random":
            search_kwargs["n_iter"] = self.n_iter
            search_kwargs["param_distributions"] = search_kwargs.pop("param_grid")

        searcher = SearchCV(**search_kwargs)
        searcher.fit(X, y)

        self.best_estimator_ = searcher.best_estimator_
        self.best_params_ = searcher.best_params_
        self.log_metrics(best_score=searcher.best_score_, **{f"best_{k}": v for k, v in self.best_params_.items() if isinstance(v, (int, float))})
        return self.best_estimator_


class _TransferLearningStepStub(Step):
    """DEPRECATED: Transfer learning step for pretrained models.
    
    .. deprecated::
        Use :class:`autopipe.steps.deep_learning.TransferLearningStep` instead.
    """
    
    def __init__(
        self,
        name: str = "transfer_learning",
        base_model: str = "resnet50",
        num_classes: int = 10,
        **kwargs
    ):
        import warnings
        warnings.warn(
            "TransferLearningStep from training module is deprecated. "
            "Use autopipe.steps.deep_learning.TransferLearningStep for full support.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(name, **kwargs)
        self.base_model = base_model
        self.num_classes = num_classes

    def run(self, **kwargs) -> Any:
        try:
            import torchvision.models as models
        except ImportError:
            raise ImportError("torchvision is required")
        
        self.model = getattr(models, self.base_model)(pretrained=True)
        return self.model


# Backwards compatibility alias
TransferLearningStep = _TransferLearningStepStub
