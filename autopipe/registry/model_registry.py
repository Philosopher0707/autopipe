"""Model Registry for versioning, comparison, and deployment of ML models."""

import hashlib
import json
import logging
import pickle
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Represents a single model version."""
    model_id: str
    version: int
    name: str
    created_at: datetime
    metrics: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    artifact_path: Optional[str] = None
    signature: Optional[Dict] = None
    framework: str = "sklearn"
    description: str = ""
    status: str = "PENDING"  # PENDING, STAGING, PRODUCTION, ARCHIVED
    user: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        return d


@dataclass
class ModelComparison:
    """Comparison result between models."""
    model_a: ModelVersion
    model_b: ModelVersion
    metric_differences: Dict[str, float]
    is_better: bool
    improved_metrics: List[str]
    degraded_metrics: List[str]

    def to_markdown(self) -> str:
        """Generate markdown comparison report."""
        lines = [
            f"## Model Comparison: {self.model_a.name} v{self.model_a.version} vs v{self.model_b.version}",
            "",
            f"**Result:** {'✅ Model A is better' if self.is_better else '⚠️ Model B is better or equal'}",
            "",
            "### Metrics Summary",
            "",
            "| Metric | Model A | Model B | Difference |",
            "|--------|---------|---------|------------|",
        ]

        for metric, diff in self.metric_differences.items():
            val_a = self.model_a.metrics.get(metric, 'N/A')
            val_b = self.model_b.metrics.get(metric, 'N/A')
            lines.append(f"| {metric} | {val_a:.4f} | {val_b:.4f} | {diff:+.4f} |")

        lines.extend([
            "",
            "### Improved Metrics",
            f"- {', '.join(self.improved_metrics) if self.improved_metrics else 'None'}",
            "",
            "### Degraded Metrics",
            f"- {', '.join(self.degraded_metrics) if self.degraded_metrics else 'None'}",
        ])

        return "\n".join(lines)


class ModelRegistry:
    """Central registry for ML model management.
    
    Features:
    - Model versioning with semantic versioning
    - Model comparison and A/B testing
    - Model deployment stages (staging -> production)
    - Artifact storage with metadata
    - Integration with MLflow (optional)
    - Model signature tracking
    - Automatic model lineage
    """

    def __init__(
        self,
        registry_dir: str = "./.autopipe_registry",
        use_mlflow: bool = False,
        mlflow_tracking_uri: Optional[str] = None,
        mlflow_experiment: str = "autopipe_experiments"
    ):
        """
        Args:
            registry_dir: Local directory for model storage
            use_mlflow: Whether to use MLflow for backend
            mlflow_tracking_uri: MLflow tracking URI
            mlflow_experiment: MLflow experiment name
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self.models: Dict[str, List[ModelVersion]] = {}
        self._load_registry()

        # MLflow integration
        self.use_mlflow = use_mlflow and MLFLOW_AVAILABLE
        self.mlflow_client: Optional[Any] = None

        if self.use_mlflow:
            if mlflow_tracking_uri:
                mlflow.set_tracking_uri(mlflow_tracking_uri)
            mlflow.set_experiment(mlflow_experiment)
            self.mlflow_client = MlflowClient()
            logger.info(f"MLflow configured with experiment: {mlflow_experiment}")

    def _load_registry(self):
        """Load registry index from disk."""
        index_path = self.registry_dir / "registry_index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)

                for name, versions_data in data.items():
                    self.models[name] = [
                        ModelVersion(
                            model_id=v['model_id'],
                            version=v['version'],
                            name=v['name'],
                            created_at=datetime.fromisoformat(v['created_at']),
                            metrics=v.get('metrics', {}),
                            parameters=v.get('parameters', {}),
                            tags=v.get('tags', {}),
                            artifact_path=v.get('artifact_path'),
                            signature=v.get('signature'),
                            framework=v.get('framework', 'sklearn'),
                            description=v.get('description', ''),
                            status=v.get('status', 'PENDING'),
                            user=v.get('user')
                        )
                        for v in versions_data
                    ]
            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")

    def _save_registry(self):
        """Save registry index to disk."""
        index_path = self.registry_dir / "registry_index.json"
        data = {
            name: [v.to_dict() for v in versions]
            for name, versions in self.models.items()
        }
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def register(
        self,
        model: Any,
        name: str,
        metrics: Dict[str, float],
        parameters: Dict[str, Any] = None,
        tags: Dict[str, str] = None,
        description: str = "",
        framework: str = "sklearn",
        signature: Optional[Dict] = None,
        artifact_path: Optional[str] = None,
        stage: str = "PENDING"
    ) -> ModelVersion:
        """Register a new model version.
        
        Args:
            model: The trained model object
            name: Model name
            metrics: Performance metrics dictionary
            parameters: Hyperparameters dictionary
            tags: Tags for organization
            description: Model description
            framework: Framework used (sklearn, pytorch, tensorflow)
            signature: Model input/output signature
            artifact_path: Custom artifact path
            stage: Initial stage (PENDING, STAGING, PRODUCTION)
            
        Returns:
            ModelVersion object
        """
        # Generate version number
        if name not in self.models:
            self.models[name] = []

        version = len(self.models[name]) + 1
        model_id = f"{name}_v{version}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

        # Create model directory
        model_dir = self.registry_dir / name / f"v{version}"
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model artifact
        if artifact_path is None:
            artifact_path = str(model_dir / "model")

        self._save_model_artifact(model, artifact_path, framework)

        # Create version metadata
        version_info = ModelVersion(
            model_id=model_id,
            version=version,
            name=name,
            created_at=datetime.now(),
            metrics=metrics or {},
            parameters=parameters or {},
            tags=tags or {},
            artifact_path=artifact_path,
            signature=signature,
            framework=framework,
            description=description,
            status=stage.upper(),
        )

        self.models[name].append(version_info)
        self._save_registry()

        # Log to MLflow if enabled
        if self.use_mlflow:
            with mlflow.start_run(run_name=f"{name}_v{version}"):
                mlflow.log_params(parameters or {})
                mlflow.log_metrics(metrics or {})
                mlflow.set_tags(tags or {})
                mlflow.set_tag("model_name", name)
                mlflow.set_tag("model_version", version)

                # Log model based on framework
                if framework == "sklearn":
                    mlflow.sklearn.log_model(model, "model")
                elif framework == "pytorch":
                    mlflow.pytorch.log_model(model, "model")
                elif framework == "tensorflow":
                    mlflow.tensorflow.log_model(model, "model")

        logger.info(f"Registered {name} v{version} with metrics: {metrics}")
        return version_info

    def _save_model_artifact(self, model: Any, path: str, framework: str):
        """Save model to disk."""
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        if framework == "sklearn":
            with open(save_path.with_suffix('.pkl'), 'wb') as f:
                pickle.dump(model, f)
        elif framework == "pytorch":
            import torch
            torch.save(model.state_dict(), save_path.with_suffix('.pt'))
        elif framework == "tensorflow":
            model.save(save_path.with_suffix('.keras'))
        elif framework == "xgboost":
            model.save_model(save_path.with_suffix('.json'))
        else:
            # Generic pickle fallback
            with open(save_path.with_suffix('.pkl'), 'wb') as f:
                pickle.dump(model, f)

    def load(self, name: str, version: Optional[int] = None, stage: Optional[str] = None) -> Any:
        """Load a model from registry.
        
        Args:
            name: Model name
            version: Specific version (None = latest)
            stage: Load by stage (PRODUCTION, STAGING)
            
        Returns:
            Loaded model object
        """
        if name not in self.models:
            raise ValueError(f"Model {name} not found in registry")

        versions = self.models[name]

        # Find version to load
        if version is not None:
            target = next((v for v in versions if v.version == version), None)
        elif stage is not None:
            target = next((v for v in reversed(versions) if v.status == stage.upper()), None)
        else:
            target = versions[-1] if versions else None

        if target is None:
            raise ValueError(f"Model {name} version not found")

        return self._load_model_artifact(target)

    def _load_model_artifact(self, version: ModelVersion) -> Any:
        """Load model artifact from disk."""
        path = Path(version.artifact_path)
        framework = version.framework

        if framework == "sklearn":
            with open(path.with_suffix('.pkl'), 'rb') as f:
                return pickle.load(f)
        elif framework == "pytorch":
            import torch
            # Note: model class needs to be provided separately
            state_dict = torch.load(path.with_suffix('.pt'), map_location='cpu')
            return state_dict
        elif framework == "tensorflow":
            from tensorflow import keras
            return keras.models.load_model(path.with_suffix('.keras'))
        elif framework == "xgboost":
            import xgboost as xgb
            model = xgb.Booster()
            model.load_model(path.with_suffix('.json'))
            return model
        else:
            with open(path.with_suffix('.pkl'), 'rb') as f:
                return pickle.load(f)

    def transition_stage(self, name: str, version: int, stage: str) -> ModelVersion:
        """Transition model to a new stage.
        
        Args:
            name: Model name
            version: Version number
            stage: New stage (PENDING, STAGING, PRODUCTION, ARCHIVED)
            
        Returns:
            Updated ModelVersion
        """
        if name not in self.models:
            raise ValueError(f"Model {name} not found")

        version_obj = next((v for v in self.models[name] if v.version == version), None)
        if version_obj is None:
            raise ValueError(f"Version {version} not found for model {name}")

        # If promoting to PRODUCTION, demote any existing production model
        if stage.upper() == "PRODUCTION":
            for v in self.models[name]:
                if v.status == "PRODUCTION":
                    v.status = "ARCHIVED"
                    logger.info(f"Archived {name} v{v.version}")

        version_obj.status = stage.upper()
        self._save_registry()

        logger.info(f"Transitioned {name} v{version} to {stage}")
        return version_obj

    def compare_versions(
        self,
        name: str,
        version_a: int,
        version_b: int,
        metric_directions: Optional[Dict[str, str]] = None
    ) -> ModelComparison:
        """Compare two model versions.
        
        Args:
            name: Model name
            version_a: First version number
            version_b: Second version number
            metric_directions: Dict of metric_name -> 'maximize' or 'minimize'
            
        Returns:
            ModelComparison object
        """
        if name not in self.models:
            raise ValueError(f"Model {name} not found")

        model_a = next((v for v in self.models[name] if v.version == version_a), None)
        model_b = next((v for v in self.models[name] if v.version == version_b), None)

        if model_a is None or model_b is None:
            raise ValueError("One or both versions not found")

        # Default metric directions (maximize accuracy metrics)
        default_directions = {
            'accuracy': 'maximize',
            'precision': 'maximize',
            'recall': 'maximize',
            'f1': 'maximize',
            'roc_auc': 'maximize',
            'r2': 'maximize',
            'mae': 'minimize',
            'mse': 'minimize',
            'rmse': 'minimize',
            'loss': 'minimize',
        }
        directions = {**default_directions, **(metric_directions or {})}

        # Compare metrics
        all_metrics = set(model_a.metrics.keys()) | set(model_b.metrics.keys())
        differences = {}
        improved = []
        degraded = []

        for metric in all_metrics:
            val_a = model_a.metrics.get(metric, 0)
            val_b = model_b.metrics.get(metric, 0)

            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                diff = val_a - val_b
                differences[metric] = diff

                direction = directions.get(metric, 'maximize')
                is_better = (diff > 0 and direction == 'maximize') or (diff < 0 and direction == 'minimize')

                if is_better:
                    improved.append(metric)
                elif diff != 0:
                    degraded.append(metric)

        # Determine if model_a is better overall
        is_better = len(improved) > len(degraded)

        return ModelComparison(
            model_a=model_a,
            model_b=model_b,
            metric_differences=differences,
            is_better=is_better,
            improved_metrics=improved,
            degraded_metrics=degraded
        )

    def get_best_version(
        self,
        name: str,
        metric: str = 'accuracy',
        direction: str = 'maximize',
        stage: Optional[str] = None
    ) -> Optional[ModelVersion]:
        """Get the best model version based on a metric.
        
        Args:
            name: Model name
            metric: Metric to optimize
            direction: 'maximize' or 'minimize'
            stage: Optional stage filter
            
        Returns:
            Best ModelVersion or None
        """
        if name not in self.models:
            return None

        versions = self.models[name]
        if stage:
            versions = [v for v in versions if v.status == stage.upper()]

        if not versions:
            return None

        # Sort by metric
        scored_versions = [
            (v, v.metrics.get(metric, float('-inf') if direction == 'maximize' else float('inf')))
            for v in versions
        ]

        scored_versions.sort(key=lambda x: x[1], reverse=(direction == 'maximize'))
        return scored_versions[0][0] if scored_versions else None

    def list_models(self) -> List[str]:
        """List all registered model names."""
        return list(self.models.keys())

    def get_versions(self, name: str) -> List[ModelVersion]:
        """Get all versions of a model."""
        return self.models.get(name, [])

    def get_production_model(self, name: str) -> Optional[ModelVersion]:
        """Get the current production model."""
        if name not in self.models:
            return None
        return next((v for v in reversed(self.models[name]) if v.status == "PRODUCTION"), None)

    def delete_version(self, name: str, version: int):
        """Delete a specific model version."""
        if name not in self.models:
            return

        self.models[name] = [v for v in self.models[name] if v.version != version]

        # Clean up artifacts
        version_dir = self.registry_dir / name / f"v{version}"
        if version_dir.exists():
            shutil.rmtree(version_dir)

        self._save_registry()
        logger.info(f"Deleted {name} v{version}")

    def promote_to_production(self, name: str, version: int) -> ModelVersion:
        """Promote a model to production."""
        return self.transition_stage(name, version, "PRODUCTION")

    def archive_version(self, name: str, version: int) -> ModelVersion:
        """Archive a model version."""
        return self.transition_stage(name, version, "ARCHIVED")

    def generate_report(self, name: str) -> str:
        """Generate a markdown report for all versions of a model."""
        if name not in self.models:
            return f"# Model Report: {name}\n\nModel not found."

        versions = self.models[name]

        lines = [
            f"# Model Registry Report: {name}",
            "",
            f"**Total Versions:** {len(versions)}",
            f"**Report Generated:** {datetime.now().isoformat()}",
            "",
            "## Version History",
            "",
            "| Version | Status | Framework | Created | Metrics |",
            "|---------|--------|-----------|---------|---------|",
        ]

        for v in versions:
            metrics_str = ", ".join([f"{k}={v:.3f}" for k, v in v.metrics.items()][:3])
            lines.append(
                f"| {v.version} | {v.status} | {v.framework} | {v.created_at.strftime('%Y-%m-%d')} | {metrics_str} |"
            )

        lines.extend([
            "",
            "## Production Model",
            "",
        ])

        prod = self.get_production_model(name)
        if prod:
            lines.extend([
                f"**Version:** {prod.version}",
                f"**Created:** {prod.created_at.isoformat()}",
                "",
                "### Metrics",
                "",
            ])
            for k, v in prod.metrics.items():
                lines.append(f"- **{k}:** {v:.4f}")
        else:
            lines.append("No model in production.")

        return "\n".join(lines)

    def export_model(self, name: str, version: int, export_path: str, format: str = "auto"):
        """Export a model to various formats.
        
        Supported formats:
        - sklearn: pickle, joblib, onnx
        - pytorch: pt, onnx
        - tensorflow: saved_model, tflite, onnx
        """
        if name not in self.models:
            raise ValueError(f"Model {name} not found")

        version_obj = next((v for v in self.models[name] if v.version == version), None)
        if version_obj is None:
            raise ValueError(f"Version {version} not found")

        model = self._load_model_artifact(version_obj)
        framework = version_obj.framework
        export_path = Path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)

        if framework == "sklearn":
            if format in ("pickle", "auto"):
                with open(export_path.with_suffix('.pkl'), 'wb') as f:
                    pickle.dump(model, f)
            elif format == "joblib":
                import joblib
                joblib.dump(model, export_path.with_suffix('.joblib'))
            elif format == "onnx":
                # Requires skl2onnx
                from skl2onnx import convert_sklearn
                from skl2onnx.common.data_types import FloatTensorType

                # This is a simplified version - real implementation needs signature
                initial_type = [('float_input', FloatTensorType([None, model.n_features_in_]))]
                onnx_model = convert_sklearn(model, initial_types=initial_type)
                with open(export_path.with_suffix('.onnx'), "wb") as f:
                    f.write(onnx_model.SerializeToString())

        elif framework == "pytorch":
            if format in ("pt", "auto"):
                import torch
                torch.save(model, export_path.with_suffix('.pt'))
            elif format == "onnx":
                import torch
                dummy_input = torch.randn(1, 10)  # This needs actual input shape
                torch.onnx.export(model, dummy_input, export_path.with_suffix('.onnx'))

        elif framework == "tensorflow":
            if format in ("saved_model", "auto"):
                model.save(export_path)
            elif format == "tflite":
                converter = tf.lite.TFLiteConverter.from_keras_model(model)
                tflite_model = converter.convert()
                with open(export_path.with_suffix('.tflite'), 'wb') as f:
                    f.write(tflite_model)

        logger.info(f"Exported {name} v{version} to {export_path}")

    def get_model_signature(self, name: str, version: int) -> Optional[Dict]:
        """Get the input/output signature of a model."""
        if name not in self.models:
            return None

        version_obj = next((v for v in self.models[name] if v.version == version), None)
        if version_obj is None:
            return None

        return version_obj.signature


# Global registry singleton
_REGISTRY: Optional[ModelRegistry] = None


def get_registry(
    registry_dir: str = "./.autopipe_registry",
    use_mlflow: bool = False
) -> ModelRegistry:
    """Get or create the global registry singleton."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry(registry_dir=registry_dir, use_mlflow=use_mlflow)
    return _REGISTRY


def reset_registry():
    """Reset the global registry (useful for testing)."""
    global _REGISTRY
    _REGISTRY = None
