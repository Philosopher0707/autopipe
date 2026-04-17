# 🚀 AutoPipe: World-Class ML/DL Pipeline Framework

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive, production-ready machine learning and deep learning pipeline framework with built-in experiment tracking, model registry, explainability, and monitoring.

## ✨ Features

### 🔧 Core Features
- **DAG-based Pipeline Execution**: Build complex ML workflows with automatic dependency resolution
- **Fault Tolerance**: Built-in checkpointing and recovery mechanisms
- **Parallel Execution**: Support for distributed training and parallel step execution
- **Version Control**: Integrated with DVC for data versioning

### 🤖 Machine Learning
- **Cross-Validation**: K-Fold, Stratified K-Fold, Time Series Split, Group K-Fold
- **Bootstrap Validation**: Confidence intervals for model stability
- **Nested CV**: Unbiased hyperparameter evaluation
- **AutoML Support**: Automated model selection and hyperparameter tuning

### 🧠 Deep Learning
- **PyTorch Training**: Advanced trainer with early stopping, gradient clipping, mixed precision
- **TensorFlow/Keras**: Native support for TF training
- **Transfer Learning**: Pre-trained model integration (ResNet, VGG, EfficientNet, etc.)
- **Distributed Training**: Multi-GPU and distributed setup

### 📊 Model Explainability
- **SHAP**: TreeExplainer, KernelExplainer, DeepExplainer for global and local explanations
- **LIME**: Local interpretable model-agnostic explanations
- **Permutation Importance**: Feature ranking via permutation
- **Partial Dependence Plots**: Feature effect visualization
- **Attention Visualization**: For transformer models

### 📦 Model Registry
- **Version Management**: Semantic versioning for models
- **Staging**: Dev → Staging → Production → Archived
- **A/B Testing**: Model comparison and selection
- **Signature Tracking**: Input/output schema validation
- **MLflow Integration**: Seamless integration with MLflow

### 🔍 Data & Model Monitoring
- **Statistical Drift Detection**: KS test, PSI, Wasserstein distance, Chi-square
- **Target Drift**: Concept drift detection
- **Prediction Drift**: Model output monitoring
- **Automated Alerting**: Threshold-based alerts

### 🔄 Feature Engineering
- **Automated Transformations**: Scaling, encoding, binning
- **Text Features**: TF-IDF, Count vectorization
- **Datetime Features**: Day, month, year, hour extraction
- **Mathematical Transforms**: Log, box-cox, polynomial
- **Feature Selection**: Variance threshold, correlation

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install autopipe

# With full ML/DL support
pip install "autopipe[all]"

# With specific extras
pip install "autopipe[torch,tensorflow,ml,explainability]"
```

### Basic Usage

```python
from autopipe import Pipeline, Step

# Define a custom step
class DataPreprocessingStep(Step):
    def run(self, data, **kwargs):
        # Your preprocessing logic
        return processed_data

# Build pipeline
pipeline = Pipeline("my_ml_pipeline") \
    .add_step(DataPreprocessingStep("preprocess")) \
    .add_step(TrainingStep("train")) \
    .add_step(EvaluationStep("evaluate"))

# Execute
results = pipeline.run()
```

## 📚 Examples

### Cross-Validation Example

```python
from autopipe.steps import CrossValidationStep
from sklearn.ensemble import RandomForestClassifier

# Setup CV
cv_step = CrossValidationStep(
    name="rf_cv",
    strategy="stratified",
    n_splits=5,
    metrics=['accuracy', 'f1']
)

# Run CV
cv_results = cv_step.run(
    model_builder=lambda: RandomForestClassifier(n_estimators=100),
    X=X,
    y=y
)

print(f"Mean Val Score: {cv_results['mean_val_score']:.4f}")
```

### Deep Learning (PyTorch)

```python
import torch.nn as nn
from autopipe.steps.deep_learning import PyTorchTrainerStep

# Define model
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(20, 64)
        self.fc2 = nn.Linear(64, 2)
    def forward(self, x):
        return self.fc2(torch.relu(self.fc1(x)))

# Train
trainer = PyTorchTrainerStep(
    name="pytorch_classifier",
    model_builder=Net,
    loss_fn="cross_entropy",
    optimizer="adam",
    epochs=50,
    early_stopping_patience=10
)

results = trainer.run(X_train=X, y_train=y, task='classification')
```

### Model Registry

```python
from autopipe.registry import get_registry

# Get registry
registry = get_registry()

# Register model
metadata = registry.register(
    model=my_trained_model,
    name="churn_predictor",
    metrics={'accuracy': 0.95, 'f1': 0.94},
    parameters={'n_estimators': 100},
    tags={'stage': 'production'}
)

# Promote to production
registry.promote_to_production("churn_predictor", metadata.version)

# Load model
prod_model = registry.load("churn_predictor", stage="PRODUCTION")
```

### Explainability

```python
from autopipe.steps.explainability import ExplainabilityPipeline

# Run comprehensive explainability
explainer = ExplainabilityPipeline(
    name="model_explanation",
    methods=['feature_importance', 'permutation', 'shap']
)

results = explainer.run(
    model=trained_model,
    X_train=X_train,
    y_train=y_train,
    X_test=X_test
)

# View aggregated feature importance
print(results['aggregated_ranks'])
```

### Data Drift Detection

```python
from autopipe.monitoring import StatisticalDriftDetectorStep

# Detect drift
detector = StatisticalDriftDetectorStep(
    name="drift_detector",
    method="ks",
    threshold=0.05
)

results = detector.run(
    reference_data=reference_df,
    current_data=current_df
)

if results['drift_detected_count'] > 0:
    print(f"⚠️ Drift detected in {results['drift_ratio']:.1%} of features")
```

## 🏗️ Architecture

```
autopipe/
├── core/               # Core pipeline and step infrastructure
├── steps/              # ML/DL pipeline steps
│   ├── deep_learning.py
│   ├── explainability.py
│   ├── cross_validation.py
│   └── ...
├── registry/           # Model versioning and deployment
├── monitoring/         # Drift detection and monitoring
├── experiments/        # Experiment tracking
├── tuning/             # Hyperparameter optimization
├── visualization/      # Charts and plots
└── llm/                # LLM integration
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=autopipe

# Run specific test
pytest tests/test_cross_validation.py
```

## 📖 Documentation

Full documentation is available at [autopipe.readthedocs.io](https://autopipe.readthedocs.io)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

AutoPipe is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- scikit-learn for ML algorithms
- PyTorch and TensorFlow for deep learning
- SHAP and LIME for model interpretability
- MLflow for experiment tracking

## 🔗 Links

- Documentation: https://autopipe.readthedocs.io
- PyPI: https://pypi.org/project/autopipe
- GitHub: https://github.com/autopipe/autopipe
- Issues: https://github.com/autopipe/autopipe/issues

---

**Made with ❤️ by the AutoPipe Team**

*Building world-class ML pipelines, one step at a time.*
