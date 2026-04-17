"""Integration tests for end-to-end ML pipeline workflows."""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import shutil

from autopipe.core.pipeline import Pipeline
from autopipe.core.steps import PrintStep
from autopipe.steps.data import DataLoaderStep
from autopipe.steps.training import SklearnTrainerStep
from autopipe.steps.cross_validation import CrossValidationStep, DataSplitterStep
from autopipe.steps.explainability import PermutationImportanceStep, FeatureImportanceStep
from autopipe.registry import get_registry


class TestEndToEndMLPipeline:
    """End-to-end tests for complete ML workflows."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs."""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    @pytest.fixture
    def sample_classification_data(self):
        """Generate sample classification data."""
        from sklearn.datasets import make_classification
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            n_redundant=2,
            n_classes=2,
            random_state=42
        )
        
        feature_names = [f"feature_{i}" for i in range(10)]
        df = pd.DataFrame(X, columns=feature_names)
        df['target'] = y
        return df, feature_names
    
    def test_complete_classification_pipeline(self, sample_classification_data, temp_dir):
        """Test a complete ML pipeline from data loading to model registry."""
        df, feature_names = sample_classification_data
        
        # Step 1: Split data
        splitter = DataSplitterStep(
            name="data_split",
            train_size=0.7,
            val_size=0.15,
            test_size=0.15,
            random_state=42
        )
        splits = splitter.run(data=df, target_column='target')
        
        assert 'train' in splits
        assert 'val' in splits
        assert 'test' in splits
        assert len(splits['train']) > 0
        assert len(splits['val']) > 0
        assert len(splits['test']) > 0
        
        # Step 2: Model training
        from sklearn.ensemble import RandomForestClassifier
        
        train_data = splits['train']
        X_train = train_data.drop('target', axis=1).values
        y_train = train_data['target'].values
        
        trainer = SklearnTrainerStep(
            name="model_training",
            model_class=RandomForestClassifier,
            model_params={'n_estimators': 50, 'random_state': 42}
        )
        
        model = trainer.run(data=(X_train, y_train))
        assert model is not None
        
        # Step 3: Evaluation
        test_data = splits['test']
        X_test = test_data.drop('target', axis=1).values
        y_test = test_data['target'].values
        
        from sklearn.metrics import accuracy_score, f1_score
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        
        assert accuracy > 0.5  # Should be better than random
        assert f1 > 0.5
        
        # Step 4: Model registry
        registry = get_registry(registry_dir=f"{temp_dir}/registry")
        version_info = registry.register(
            model=model,
            name="test_classifier",
            metrics={'accuracy': accuracy, 'f1': f1},
            parameters={'n_estimators': 50}
        )
        
        assert version_info.name == "test_classifier"
        assert version_info.version == 1
        assert version_info.metrics['accuracy'] == accuracy
        
        # Step 5: Model loading
        loaded_model = registry.load("test_classifier")
        assert loaded_model is not None
        
        # Verify loaded model makes same predictions
        y_pred_loaded = loaded_model.predict(X_test)
        assert np.array_equal(y_pred, y_pred_loaded)


class TestDeepLearningIntegration:
    """Integration tests for PyTorch/TensorFlow training."""
    
    def test_pytorch_training_step(self):
        """Test PyTorch training step with simple dataset."""
        try:
            import torch
            import torch.nn as nn
        except ImportError:
            pytest.skip("PyTorch not installed")
        
        from autopipe.steps.deep_learning import PyTorchTrainerStep
        
        # Simple dataset
        X = np.random.randn(100, 10).astype(np.float32)
        y = np.random.randint(0, 2, size=100)
        
        # Simple model
        class SimpleNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc1 = nn.Linear(10, 20)
                self.fc2 = nn.Linear(20, 2)
            
            def forward(self, x):
                x = torch.relu(self.fc1(x))
                x = self.fc2(x)
                return x
        
        trainer = PyTorchTrainerStep(
            name="pytorch_test",
            model_builder=SimpleNet,
            epochs=5,
            batch_size=20,
            learning_rate=0.001
        )
        
        result = trainer.run(X_train=X, y_train=y, task='classification')
        
        assert 'model' in result
        assert 'history' in result
        assert len(result['history']['train_loss']) > 0


class TestCrossValidationIntegration:
    """Integration tests for cross-validation workflows."""
    
    def test_cv_with_nested_pipeline(self):
        """Test cross-validation integrated with pipeline."""
        from sklearn.datasets import make_classification
        from sklearn.ensemble import RandomForestClassifier
        
        X, y = make_classification(n_samples=100, n_features=10, n_informative=5, 
                                    n_redundant=2, random_state=42)
        
        pipeline = Pipeline("cv_pipeline")
        
        # Create CV step
        cv_step = CrossValidationStep(
            name="cv",
            strategy="stratified",
            n_splits=3,
            metrics=['accuracy', 'f1']
        )
        
        # Run CV
        results = cv_step.run(
            model_builder=lambda: RandomForestClassifier(n_estimators=10, random_state=42),
            X=X,
            y=y
        )
        
        assert 'mean_val_score' in results
        assert 'fold_results' in results
        assert len(results['fold_results']) == 3


class TestExplainabilityIntegration:
    """Integration tests for explainability workflows."""
    
    def test_permutation_importance_with_model(self):
        """Test permutation importance with a trained model."""
        from sklearn.datasets import make_classification
        from sklearn.ensemble import RandomForestClassifier
        
        X, y = make_classification(n_samples=100, n_features=10, n_informative=5, 
                                    n_redundant=2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        
        perm_imp_step = PermutationImportanceStep(
            name="perm_importance",
            n_repeats=5
        )
        
        result = perm_imp_step.run(
            model=model,
            X=X,
            y=y,
            feature_names=[f"feat_{i}" for i in range(10)]
        )
        
        assert 'importances' in result
        assert 'sorted_importance' in result
        assert len(result['sorted_importance']) == 10


class TestFeatureEngineeringIntegration:
    """Integration tests for feature engineering workflows."""
    
    def test_feature_engineering_pipeline(self):
        """Test feature engineering with multiple transformations."""
        from autopipe.steps.data import FeatureSelectionStep
        
        # Create sample data
        np.random.seed(42)
        df = pd.DataFrame({
            'num1': np.random.randn(100),
            'num2': np.random.randn(100),
            'num3': np.random.randn(100),
            'category': np.random.choice(['A', 'B', 'C'], 100),
            'target': np.random.randint(0, 2, 100)
        })
        
        pipeline = Pipeline("feature_pipeline")
        
        # Step 1: Feature selection
        feature_step = FeatureSelectionStep(
            name="feature_selection",
            method="variance_threshold"
        )
        
        # This just tests that the step can be added to pipeline
        pipeline.add_step(feature_step)
        
        # Verify pipeline was created correctly
        assert len(pipeline.steps) == 1
        assert "feature_selection" in pipeline.steps


class TestDriftDetectionIntegration:
    """Integration tests for drift detection workflows."""
    
    def test_drift_detection_no_drift(self):
        """Test drift detection when no drift is expected."""
        from autopipe.monitoring.drift_detection import StatisticalDriftDetectorStep
        
        # Same distribution
        ref_data = pd.DataFrame({'feature': np.random.normal(0, 1, 100)})
        cur_data = pd.DataFrame({'feature': np.random.normal(0, 1, 100)})
        
        detector = StatisticalDriftDetectorStep(
            name="drift_detector",
            method="ks",
            threshold=0.05
        )
        
        result = detector.run(
            reference_data=ref_data,
            current_data=cur_data
        )
        
        assert 'drift_reports' in result
        assert 'drift_detected_count' in result
        assert result['total_features'] == 1
    
    def test_drift_detection_with_drift(self):
        """Test drift detection when drift is expected."""
        from autopipe.monitoring.drift_detection import StatisticalDriftDetectorStep
        
        # Different distributions
        ref_data = pd.DataFrame({'feature': np.random.normal(0, 1, 100)})
        cur_data = pd.DataFrame({'feature': np.random.normal(5, 1, 100)})  # Shifted mean
        
        detector = StatisticalDriftDetectorStep(
            name="drift_detector",
            method="ks",
            threshold=0.05
        )
        
        result = detector.run(
            reference_data=ref_data,
            current_data=cur_data
        )
        
        # Should detect drift
        assert result['drift_detected_count'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
