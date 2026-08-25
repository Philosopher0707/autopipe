"""Deep Learning training steps for PyTorch and TensorFlow."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from autopipe.core.step import Step

logger = logging.getLogger(__name__)


class PyTorchTrainerStep(Step):
    """PyTorch model training step with advanced features.

    Features:
    - Customizable model architecture
    - Early stopping
    - Learning rate scheduling
    - Gradient clipping
    - Mixed precision training
    - Distributed training support
    - Callback system
    """

    def __init__(
        self,
        name: str,
        model_builder: Callable,
        loss_fn: str = "cross_entropy",
        optimizer: str = "adam",
        learning_rate: float = 0.001,
        epochs: int = 10,
        batch_size: int = 32,
        validation_split: float = 0.2,
        early_stopping_patience: int = None,
        lr_scheduler: str = None,
        lr_scheduler_params: Dict = None,
        gradient_clip_val: float = None,
        use_mixed_precision: bool = False,
        device: str = "auto",
        callbacks: List[Callable] = None,
        metrics: List[str] = None,
        class_weights: Optional[np.ndarray] = None,
        **kwargs,
    ):
        """
        Args:
            model_builder: Callable that returns a PyTorch model
            loss_fn: Loss function name ('cross_entropy', 'bce', 'mse', 'mae', 'huber', 'triplet')
            optimizer: Optimizer name ('adam', 'sgd', 'adamw', 'rmsprop')
            learning_rate: Initial learning rate
            epochs: Number of training epochs
            batch_size: Batch size for training
            validation_split: Fraction of data for validation
            early_stopping_patience: Epochs to wait before stopping (None = disabled)
            lr_scheduler: LR scheduler type ('reduce_on_plateau', 'cosine', 'exponential', 'step')
            lr_scheduler_params: Parameters for LR scheduler
            gradient_clip_val: Max gradient norm for clipping
            use_mixed_precision: Whether to use automatic mixed precision
            device: Device to use ('cpu', 'cuda', 'auto')
            callbacks: List of callback functions
            metrics: List of metrics to track ('accuracy', 'f1', 'precision', 'recall', 'auc')
            class_weights: Optional class weights for imbalanced datasets
        """
        super().__init__(name, **kwargs)
        self.model_builder = model_builder
        self.loss_fn_name = loss_fn
        self.optimizer_name = optimizer
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.validation_split = validation_split
        self.early_stopping_patience = early_stopping_patience
        self.lr_scheduler = lr_scheduler
        self.lr_scheduler_params = lr_scheduler_params or {}
        self.gradient_clip_val = gradient_clip_val
        self.use_mixed_precision = use_mixed_precision
        self.device = device
        self.callbacks = callbacks or []
        self.metric_names = metrics or []
        self.class_weights = class_weights

        self.model = None
        self.history = {"train_loss": [], "val_loss": [], "train_metrics": {}, "val_metrics": {}}
        self.best_weights = None
        self.best_val_loss = float("inf")
        self.patience_counter = 0

    def _get_device(self) -> str:
        """Determine training device."""
        import torch

        if self.device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return self.device

    def _get_loss_fn(self, device: str):
        """Get loss function."""
        import torch.nn as nn

        loss_fns = {
            "cross_entropy": nn.CrossEntropyLoss(weight=self.class_weights),
            "bce": nn.BCEWithLogitsLoss(weight=self.class_weights),
            "mse": nn.MSELoss(),
            "mae": nn.L1Loss(),
            "huber": nn.SmoothL1Loss(),
            "triplet": nn.TripletMarginLoss(),
            "nll": nn.NLLLoss(weight=self.class_weights),
            "kldiv": nn.KLDivLoss(),
        }

        if self.loss_fn_name not in loss_fns:
            raise ValueError(f"Unknown loss function: {self.loss_fn_name}")

        return loss_fns[self.loss_fn_name].to(device)

    def _get_optimizer(self, model):
        """Get optimizer."""
        import torch.optim as optim

        optimizers = {
            "adam": optim.Adam(model.parameters(), lr=self.learning_rate),
            "sgd": optim.SGD(model.parameters(), lr=self.learning_rate, momentum=0.9),
            "adamw": optim.AdamW(model.parameters(), lr=self.learning_rate, weight_decay=0.01),
            "rmsprop": optim.RMSprop(model.parameters(), lr=self.learning_rate),
            "adagrad": optim.Adagrad(model.parameters(), lr=self.learning_rate),
        }

        if self.optimizer_name not in optimizers:
            raise ValueError(f"Unknown optimizer: {self.optimizer_name}")

        return optimizers[self.optimizer_name]

    def _get_lr_scheduler(self, optimizer):
        """Get learning rate scheduler."""
        import torch.optim.lr_scheduler as schedulers

        if self.lr_scheduler is None:
            return None

        scheds = {
            "reduce_on_plateau": schedulers.ReduceLROnPlateau(
                optimizer, mode="min", patience=2, **self.lr_scheduler_params
            ),
            "cosine": schedulers.CosineAnnealingLR(
                optimizer, T_max=self.epochs, **self.lr_scheduler_params
            ),
            "exponential": schedulers.ExponentialLR(
                optimizer, gamma=0.95, **self.lr_scheduler_params
            ),
            "step": schedulers.StepLR(
                optimizer, step_size=10, gamma=0.1, **self.lr_scheduler_params
            ),
        }

        return scheds.get(self.lr_scheduler)

    def _compute_metrics(
        self, y_true: np.ndarray, y_pred: np.ndarray, task: str = "classification"
    ) -> Dict[str, float]:
        """Compute metrics."""
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            mean_absolute_error,
            mean_squared_error,
            precision_score,
            r2_score,
            recall_score,
        )

        metrics_dict = {}

        if task == "classification":
            if "accuracy" in self.metric_names:
                metrics_dict["accuracy"] = accuracy_score(y_true, y_pred)
            if "f1" in self.metric_names:
                metrics_dict["f1"] = f1_score(y_true, y_pred, average="weighted", zero_division=0)
            if "precision" in self.metric_names:
                metrics_dict["precision"] = precision_score(
                    y_true, y_pred, average="weighted", zero_division=0
                )
            if "recall" in self.metric_names:
                metrics_dict["recall"] = recall_score(
                    y_true, y_pred, average="weighted", zero_division=0
                )
        else:
            if "r2" in self.metric_names:
                metrics_dict["r2"] = r2_score(y_true, y_pred)
            if "mse" in self.metric_names:
                metrics_dict["mse"] = mean_squared_error(y_true, y_pred)
            if "mae" in self.metric_names:
                metrics_dict["mae"] = mean_absolute_error(y_true, y_pred)

        return metrics_dict

    def run(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        task: str = "classification",
        **kwargs,
    ) -> Dict[str, Any]:
        """Train PyTorch model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            task: 'classification' or 'regression'

        Returns:
            Dictionary with model and training history
        """
        import torch
        from torch.utils.data import DataLoader, TensorDataset

        device = self._get_device()
        logger.info(f"Training on device: {device}")

        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train).to(device)
        y_train_tensor = (
            torch.LongTensor(y_train).to(device)
            if task == "classification"
            else torch.FloatTensor(y_train).to(device)
        )

        # Split validation if not provided
        if X_val is None and self.validation_split > 0:
            split_idx = int(len(X_train) * (1 - self.validation_split))
            X_val_tensor = X_train_tensor[split_idx:]
            y_val_tensor = y_train_tensor[split_idx:]
            X_train_tensor = X_train_tensor[:split_idx]
            y_train_tensor = y_train_tensor[:split_idx]
        elif X_val is not None:
            X_val_tensor = torch.FloatTensor(X_val).to(device)
            y_val_tensor = (
                torch.LongTensor(y_val).to(device)
                if task == "classification"
                else torch.FloatTensor(y_val).to(device)
            )
        else:
            X_val_tensor, y_val_tensor = None, None

        # Create data loaders
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)

        if X_val_tensor is not None:
            val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
            val_loader = DataLoader(val_dataset, batch_size=self.batch_size)

        # Build model
        self.model = self.model_builder().to(device)
        criterion = self._get_loss_fn(device)
        optimizer = self._get_optimizer(self.model)
        scheduler = self._get_lr_scheduler(optimizer)

        # Mixed precision scaler
        scaler = (
            torch.cuda.amp.GradScaler() if self.use_mixed_precision and device == "cuda" else None
        )

        # Training loop
        for epoch in range(self.epochs):
            self.model.train()
            train_loss = 0.0
            train_preds, train_true = [], []

            for batch_x, batch_y in train_loader:
                optimizer.zero_grad()

                if scaler:
                    with torch.cuda.amp.autocast():
                        outputs = self.model(batch_x)
                        if task == "classification":
                            loss = criterion(outputs, batch_y)
                        else:
                            loss = criterion(outputs.squeeze(), batch_y)

                    scaler.scale(loss).backward()

                    if self.gradient_clip_val:
                        scaler.unscale_(optimizer)
                        torch.nn.utils.clip_grad_norm_(
                            self.model.parameters(), self.gradient_clip_val
                        )

                    scaler.step(optimizer)
                    scaler.update()
                else:
                    outputs = self.model(batch_x)
                    if task == "classification":
                        loss = criterion(outputs, batch_y)
                    else:
                        loss = criterion(outputs.squeeze(), batch_y)

                    loss.backward()

                    if self.gradient_clip_val:
                        torch.nn.utils.clip_grad_norm_(
                            self.model.parameters(), self.gradient_clip_val
                        )

                    optimizer.step()

                train_loss += loss.item()

                if task == "classification":
                    preds = torch.argmax(outputs, dim=1).cpu().numpy()
                else:
                    preds = outputs.squeeze().detach().cpu().numpy()

                train_preds.extend(preds)
                train_true.extend(batch_y.cpu().numpy())

            train_loss /= len(train_loader)
            train_metrics = self._compute_metrics(np.array(train_true), np.array(train_preds), task)

            # Validation
            val_loss = 0.0
            val_metrics = {}
            if X_val_tensor is not None:
                self.model.eval()
                val_preds, val_true = [], []

                with torch.no_grad():
                    for batch_x, batch_y in val_loader:
                        outputs = self.model(batch_x)
                        if task == "classification":
                            loss = criterion(outputs, batch_y)
                            preds = torch.argmax(outputs, dim=1).cpu().numpy()
                        else:
                            loss = criterion(outputs.squeeze(), batch_y)
                            preds = outputs.squeeze().cpu().numpy()

                        val_loss += loss.item()
                        val_preds.extend(preds)
                        val_true.extend(batch_y.cpu().numpy())

                val_loss /= len(val_loader)
                val_metrics = self._compute_metrics(np.array(val_true), np.array(val_preds), task)

            # Update history
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            for k, v in train_metrics.items():
                self.history["train_metrics"].setdefault(k, []).append(v)
            for k, v in val_metrics.items():
                self.history["val_metrics"].setdefault(k, []).append(v)

            # Log metrics
            self.log_metrics(
                epoch=epoch,
                train_loss=train_loss,
                val_loss=val_loss,
                **{f"train_{k}": v for k, v in train_metrics.items()},
                **{f"val_{k}": v for k, v in val_metrics.items()},
            )

            # Early stopping check
            if X_val_tensor is not None:
                if val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.best_weights = {
                        k: v.cpu().clone() for k, v in self.model.state_dict().items()
                    }
                    self.patience_counter = 0
                else:
                    self.patience_counter += 1

                if (
                    self.early_stopping_patience
                    and self.patience_counter >= self.early_stopping_patience
                ):
                    logger.info(f"Early stopping at epoch {epoch}")
                    self.model.load_state_dict(self.best_weights)
                    break

            # LR scheduler step
            if scheduler:
                if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_loss if X_val_tensor is not None else train_loss)
                else:
                    scheduler.step()

            # Callbacks
            for callback in self.callbacks:
                callback(epoch, self.history)

            if epoch % 10 == 0:
                logger.info(
                    f"Epoch {epoch}/{self.epochs} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}"
                )

        # Load best weights
        if self.best_weights is not None:
            self.model.load_state_dict(self.best_weights)

        self.log_metrics(
            final_train_loss=self.history["train_loss"][-1],
            best_val_loss=self.best_val_loss,
            total_epochs=len(self.history["train_loss"]),
        )

        return {"model": self.model, "history": self.history, "device": device, "task": task}

    def visualize(self, **kwargs):
        """Visualize training history."""
        from ..visualization import ChartGenerator

        chart = ChartGenerator()

        # Plot loss curves
        if self.history["train_loss"]:
            chart.plot_metrics(
                {"train_loss": self.history["train_loss"], "val_loss": self.history["val_loss"]},
                title=f"{self.name} - Loss Curves",
            )

        # Plot metric curves
        for metric_name in self.metric_names:
            if metric_name in self.history.get("train_metrics", {}):
                chart.plot_metrics(
                    {
                        f"train_{metric_name}": self.history["train_metrics"].get(metric_name, []),
                        f"val_{metric_name}": self.history["val_metrics"].get(metric_name, []),
                    },
                    title=f"{self.name} - {metric_name.upper()}",
                )


class TensorFlowTrainerStep(Step):
    """TensorFlow/Keras model training step with advanced features."""

    def __init__(
        self,
        name: str,
        model_builder: Callable,
        loss: str = "categorical_crossentropy",
        optimizer: str = "adam",
        learning_rate: float = 0.001,
        epochs: int = 10,
        batch_size: int = 32,
        validation_split: float = 0.2,
        early_stopping_patience: int = None,
        lr_scheduler: str = None,
        reduce_lr_on_plateau: bool = False,
        tensorboard_dir: Optional[str] = None,
        checkpoint_dir: Optional[str] = None,
        class_weights: Optional[Dict] = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.model_builder = model_builder
        self.loss = loss
        self.optimizer = optimizer
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.validation_split = validation_split
        self.early_stopping_patience = early_stopping_patience
        self.lr_scheduler = lr_scheduler
        self.reduce_lr_on_plateau = reduce_lr_on_plateau
        self.tensorboard_dir = tensorboard_dir
        self.checkpoint_dir = checkpoint_dir
        self.class_weights = class_weights

        self.model = None
        self.history = None

    def _get_callbacks(self) -> List:
        """Get Keras callbacks."""
        from tensorflow import keras

        callbacks = []

        # Early stopping
        if self.early_stopping_patience:
            callbacks.append(
                keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    patience=self.early_stopping_patience,
                    restore_best_weights=True,
                )
            )

        # Reduce LR on plateau
        if self.reduce_lr_on_plateau:
            callbacks.append(
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss", factor=0.5, patience=3, min_lr=1e-7
                )
            )

        # LR scheduler
        if self.lr_scheduler == "exponential":
            callbacks.append(
                keras.callbacks.LearningRateScheduler(
                    lambda epoch: self.learning_rate * 0.95**epoch
                )
            )

        # TensorBoard
        if self.tensorboard_dir:
            callbacks.append(
                keras.callbacks.TensorBoard(log_dir=self.tensorboard_dir, histogram_freq=1)
            )

        # Checkpoint
        if self.checkpoint_dir:
            Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)
            callbacks.append(
                keras.callbacks.ModelCheckpoint(
                    filepath=f"{self.checkpoint_dir}/checkpoint_{{epoch:03d}}.keras",
                    monitor="val_loss",
                    save_best_only=True,
                )
            )

        return callbacks

    def run(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Train TensorFlow model."""
        from tensorflow import keras

        # Build model
        self.model = self.model_builder()

        # Compile
        optimizer_map = {
            "adam": keras.optimizers.Adam(self.learning_rate),
            "sgd": keras.optimizers.SGD(self.learning_rate, momentum=0.9),
            "adamw": keras.optimizers.AdamW(self.learning_rate),
            "rmsprop": keras.optimizers.RMSprop(self.learning_rate),
        }

        opt = optimizer_map.get(self.optimizer, keras.optimizers.Adam(self.learning_rate))

        self.model.compile(optimizer=opt, loss=self.loss, metrics=["accuracy"])

        # Prepare validation data
        validation_data = None
        if X_val is not None and y_val is not None:
            validation_data = (X_val, y_val)

        # Train
        callbacks = self._get_callbacks()

        self.history = self.model.fit(
            X_train,
            y_train,
            batch_size=self.batch_size,
            epochs=self.epochs,
            validation_split=self.validation_split if validation_data is None else 0.0,
            validation_data=validation_data,
            callbacks=callbacks,
            class_weight=self.class_weights,
            verbose=1,
        )

        # Log final metrics
        final_metrics = {k: v[-1] for k, v in self.history.history.items()}
        self.log_metrics(**final_metrics)

        return {"model": self.model, "history": self.history.history}

    def visualize(self, **kwargs):
        """Visualize training history."""
        if self.history is None:
            return

        from ..visualization import ChartGenerator

        chart = ChartGenerator()

        # Plot all metrics
        for metric in self.history.history:
            if "val_" not in metric:
                val_metric = f"val_{metric}"
                data = {metric: self.history.history[metric]}
                if val_metric in self.history.history:
                    data[val_metric] = self.history.history[val_metric]
                chart.plot_metrics(data, title=f"{self.name} - {metric}")


class TransferLearningStep(Step):
    """Transfer learning step for fine-tuning pre-trained models."""

    def __init__(
        self,
        name: str,
        base_model: str,
        num_classes: int,
        freeze_layers: int | List[int] | float = 0.7,
        fine_tune_from_layer: Optional[int] = None,
        input_shape: Tuple[int, ...] = (224, 224, 3),
        preprocessing: bool = True,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.base_model = base_model
        self.num_classes = num_classes
        self.freeze_layers = freeze_layers
        self.fine_tune_from_layer = fine_tune_from_layer
        self.input_shape = input_shape
        self.preprocessing = preprocessing

    def _build_model(self):
        """Build transfer learning model."""
        from tensorflow import keras

        # Get pre-trained model
        base_models = {
            "resnet50": keras.applications.ResNet50,
            "resnet101": keras.applications.ResNet101,
            "vgg16": keras.applications.VGG16,
            "vgg19": keras.applications.VGG19,
            "efficientnetb0": keras.applications.EfficientNetB0,
            "efficientnetb1": keras.applications.EfficientNetB1,
            "mobilenet": keras.applications.MobileNet,
            "mobilenetv2": keras.applications.MobileNetV2,
            "densenet121": keras.applications.DenseNet121,
            "inceptionv3": keras.applications.InceptionV3,
        }

        if self.base_model not in base_models:
            raise ValueError(f"Unknown base model: {self.base_model}")

        # Load base model
        base = base_models[self.base_model](
            weights="imagenet", include_top=False, input_shape=self.input_shape
        )

        # Freeze layers
        if isinstance(self.freeze_layers, float):
            # Freeze percentage of layers
            freeze_until = int(len(base.layers) * self.freeze_layers)
            for layer in base.layers[:freeze_until]:
                layer.trainable = False
        elif isinstance(self.freeze_layers, int):
            # Freeze first N layers
            for layer in base.layers[: self.freeze_layers]:
                layer.trainable = False
        elif isinstance(self.freeze_layers, list):
            # Freeze specific layer indices
            for i, layer in enumerate(base.layers):
                if i in self.freeze_layers:
                    layer.trainable = False

        # Build complete model
        inputs = keras.Input(shape=self.input_shape)

        x = keras.applications.resnet50.preprocess_input(inputs) if self.preprocessing else inputs

        x = base(x, training=False)
        x = keras.layers.GlobalAveragePooling2D()(x)
        x = keras.layers.Dropout(0.2)(x)
        outputs = keras.layers.Dense(self.num_classes, activation="softmax")(x)

        model = keras.Model(inputs, outputs)

        return model

    def run(self, **kwargs) -> Dict[str, Any]:
        """Build transfer learning model."""
        model = self._build_model()

        self.log_metrics(
            total_layers=len(model.layers),
            trainable_layers=sum(1 for layer in model.layers if layer.trainable),
            frozen_layers=sum(1 for layer in model.layers if not layer.trainable),
        )

        return {"model": model, "base_model": self.base_model, "num_classes": self.num_classes}
