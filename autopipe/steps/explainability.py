"""Model Explainability module for feature importance and interpretability.

Supports:
- SHAP (SHapley Additive exPlanations)
- LIME (Local Interpretable Model-agnostic Explanations)
- Permutation Importance
- Partial Dependence Plots
- Feature Importance (built-in)
- Attention Visualization (for deep learning)
"""

import logging
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path
import pickle
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from autopipe.core.step import Step

logger = logging.getLogger(__name__)


class SHAPExplainerStep(Step):
    """SHAP-based model explainability step.
    
    Provides global and local explanations for model predictions
    using SHAP (SHapley Additive exPlanations) values.
    """
    
    def __init__(
        self,
        name: str,
        explainer_type: str = "tree",
        background_data: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        plot_types: List[str] = None,
        max_samples: int = 100,
        **kwargs
    ):
        """
        Args:
            explainer_type: Type of SHAP explainer ('tree', 'kernel', 'deep', 'gradient')
            background_data: Background data for explainer
            feature_names: Names of features
            plot_types: List of plots to generate ('summary', 'bar', 'waterfall', 'dependence', 'force')
            max_samples: Maximum samples to explain
        """
        super().__init__(name, **kwargs)
        self.explainer_type = explainer_type
        self.background_data = background_data
        self.feature_names = feature_names
        self.plot_types = plot_types or ['summary', 'bar']
        self.max_samples = max_samples
        
        self.explainer = None
        self.shap_values = None
        
    def run(self, model: Any, X: np.ndarray, X_sample: Optional[np.ndarray] = None,
            feature_names: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """Compute SHAP explanations.
        
        Args:
            model: Trained model
            X: Feature matrix
            X_sample: Sample to explain (for local explanations)
            feature_names: Feature names
            
        Returns:
            Dictionary with SHAP values and explanations
        """
        try:
            import shap
        except ImportError:
            raise ImportError("SHAP is required. Install with: pip install shap")
        
        fnames = feature_names or self.feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        
        # Limit samples for speed
        if len(X) > self.max_samples:
            X_explainer = shap.sample(X, self.max_samples)
        else:
            X_explainer = X
        
        # Create explainer
        if self.explainer_type == "tree":
            self.explainer = shap.TreeExplainer(model)
        elif self.explainer_type == "kernel":
            background = self.background_data if self.background_data is not None else shap.sample(X, 100)
            self.explainer = shap.KernelExplainer(model.predict, background)
        elif self.explainer_type == "deep":
            self.explainer = shap.DeepExplainer(model, self.background_data or X_explainer[:100])
        elif self.explainer_type == "gradient":
            self.explainer = shap.GradientExplainer(model, self.background_data or X_explainer[:100])
        else:
            # Auto-detect
            try:
                self.explainer = shap.TreeExplainer(model)
            except Exception:
                background = self.background_data if self.background_data is not None else shap.sample(X, 100)
                self.explainer = shap.KernelExplainer(model.predict, background)
        
        # Compute SHAP values
        self.shap_values = self.explainer.shap_values(X_explainer)
        
        # Handle multi-class
        if isinstance(self.shap_values, list):
            # Multi-class classification
            shap_values_agg = np.mean([np.abs(sv).mean(axis=0) for sv in self.shap_values], axis=0)
        else:
            shap_values_agg = np.abs(self.shap_values).mean(axis=0) if self.shap_values.ndim == 2 else np.abs(self.shap_values).mean(axis=(0, 1))
        
        # Compute feature importance
        feature_importance = dict(zip(fnames, shap_values_agg))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:20]
        
        results = {
            'shap_values': self.shap_values,
            'explainer': self.explainer,
            'feature_importance': feature_importance,
            'top_features': top_features,
            'X_explained': X_explainer
        }
        
        if X_sample is not None:
            local_shap = self.explainer.shap_values(X_sample)
            results['local_shap'] = local_shap
        
        self.log_metrics(
            top_feature=top_features[0][0] if top_features else None,
            top_feature_importance=top_features[0][1] if top_features else None,
            num_features=X.shape[1]
        )
        
        return results
    
    def visualize(self, **kwargs):
        """Generate SHAP visualizations."""
        if self.shap_values is None:
            return
        
        try:
            import shap
        except ImportError:
            return
        
        X = self.output.get('X_explained')
        fnames = self.feature_names
        
        for plot_type in self.plot_types:
            try:
                plt.figure()
                
                if plot_type == 'summary':
                    shap.summary_plot(self.shap_values, X, feature_names=fnames, show=False)
                elif plot_type == 'bar':
                    shap.summary_plot(self.shap_values, X, feature_names=fnames, plot_type='bar', show=False)
                elif plot_type == 'dependence' and len(fnames) > 0:
                    shap.dependence_plot(fnames[0], self.shap_values, X, show=False)
                
                plt.tight_layout()
                plt.savefig(f'{self.name}_shap_{plot_type}.png', dpi=150, bbox_inches='tight')
                plt.close()
            except Exception as e:
                logger.warning(f"SHAP {plot_type} plot failed: {e}")


class LIMEExplainerStep(Step):
    """LIME-based local model explainability step.
    
    Provides local explanations for individual predictions.
    """
    
    def __init__(
        self,
        name: str,
        mode: str = "classification",
        feature_names: Optional[List[str]] = None,
        class_names: Optional[List[str]] = None,
        num_features: int = 10,
        num_samples: int = 5000,
        **kwargs
    ):
        """
        Args:
            mode: 'classification' or 'regression'
            feature_names: Names of features
            class_names: Names of classes
            num_features: Number of features to include in explanation
            num_samples: Number of perturbed samples
        """
        super().__init__(name, **kwargs)
        self.mode = mode
        self.feature_names = feature_names
        self.class_names = class_names
        self.num_features = num_features
        self.num_samples = num_samples
        
        self.explainer = None
        
    def run(self, model: Any, X_train: np.ndarray, X_instance: np.ndarray,
            **kwargs) -> Dict[str, Any]:
        """Generate LIME explanation for an instance.
        
        Args:
            model: Trained model with predict/predict_proba
            X_train: Training data for explainer
            X_instance: Instance to explain
            
        Returns:
            Dictionary with LIME explanation
        """
        try:
            from lime.lime_tabular import LimeTabularExplainer
        except ImportError:
            raise ImportError("LIME is required. Install with: pip install lime")
        
        fnames = self.feature_names or [f"feature_{i}" for i in range(X_train.shape[1])]
        cnames = self.class_names
        
        # Create explainer
        self.explainer = LimeTabularExplainer(
            X_train,
            feature_names=fnames,
            class_names=cnames,
            mode=self.mode,
            discretize_continuous=True
        )
        
        # Generate explanation
        if self.mode == "classification":
            predict_fn = model.predict_proba if hasattr(model, 'predict_proba') else model.predict
            explanation = self.explainer.explain_instance(
                X_instance,
                predict_fn,
                num_features=self.num_features,
                num_samples=self.num_samples
            )
        else:
            explanation = self.explainer.explain_instance(
                X_instance,
                model.predict,
                num_features=self.num_features,
                num_samples=self.num_samples
            )
        
        # Extract feature weights
        feature_weights = dict(explanation.as_list())
        
        self.log_metrics(
            top_positive_feature=list(feature_weights.keys())[0] if feature_weights else None,
            num_features_explained=len(feature_weights)
        )
        
        return {
            'explanation': explanation,
            'feature_weights': feature_weights,
            'local_prediction': explanation.local_pred,
            'score': explanation.score
        }
    
    def visualize(self, **kwargs):
        """Generate LIME visualization."""
        if self.output is None or 'explanation' not in self.output:
            return
        
        try:
            explanation = self.output['explanation']
            
            # Save HTML explanation
            html = explanation.as_html()
            with open(f'{self.name}_lime_explanation.html', 'w') as f:
                f.write(html)
            
            # Generate matplotlib plot
            fig = explanation.as_pyplot_figure()
            plt.tight_layout()
            plt.savefig(f'{self.name}_lime_plot.png', dpi=150, bbox_inches='tight')
            plt.close()
        except Exception as e:
            logger.warning(f"LIME visualization failed: {e}")


class PermutationImportanceStep(Step):
    """Permutation importance for feature ranking.
    
    Measures the decrease in model performance when a single feature value is randomly shuffled.
    """
    
    def __init__(
        self,
        name: str,
        n_repeats: int = 10,
        scoring: Optional[str] = None,
        random_state: int = 42,
        n_jobs: int = -1,
        **kwargs
    ):
        """
        Args:
            n_repeats: Number of times to permute each feature
            scoring: Scoring metric (if None, uses model's score method)
            random_state: Random seed
            n_jobs: Number of parallel jobs
        """
        super().__init__(name, **kwargs)
        self.n_repeats = n_repeats
        self.scoring = scoring
        self.random_state = random_state
        self.n_jobs = n_jobs
        
        self.importances = None
        
    def run(self, model: Any, X: np.ndarray, y: np.ndarray,
            feature_names: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """Compute permutation importance.
        
        Args:
            model: Trained model
            X: Feature matrix
            y: Target values
            feature_names: Feature names
            
        Returns:
            Dictionary with importance scores
        """
        from sklearn.inspection import permutation_importance
        
        result = permutation_importance(
            model, X, y,
            n_repeats=self.n_repeats,
            scoring=self.scoring,
            random_state=self.random_state,
            n_jobs=self.n_jobs
        )
        
        fnames = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        
        self.importances = {
            name: {
                'importance_mean': mean,
                'importance_std': std
            }
            for name, mean, std in zip(fnames, result.importances_mean, result.importances_std)
        }
        
        # Sort by importance
        sorted_importance = sorted(
            self.importances.items(),
            key=lambda x: x[1]['importance_mean'],
            reverse=True
        )
        
        self.log_metrics(
            top_feature=sorted_importance[0][0] if sorted_importance else None,
            top_importance=sorted_importance[0][1]['importance_mean'] if sorted_importance else None
        )
        
        return {
            'importances': self.importances,
            'sorted_importance': sorted_importance,
            'raw_importances': result.importances
        }
    
    def visualize(self, **kwargs):
        """Generate permutation importance plot."""
        if self.importances is None:
            return
        
        import matplotlib.pyplot as plt
        
        sorted_items = sorted(
            self.importances.items(),
            key=lambda x: x[1]['importance_mean'],
            reverse=True
        )[:20]  # Top 20
        
        names = [item[0] for item in sorted_items]
        means = [item[1]['importance_mean'] for item in sorted_items]
        stds = [item[1]['importance_std'] for item in sorted_items]
        
        plt.figure(figsize=(10, 8))
        y_pos = np.arange(len(names))
        plt.barh(y_pos, means, xerr=stds, align='center', alpha=0.7)
        plt.yticks(y_pos, names)
        plt.xlabel('Permutation Importance')
        plt.title(f'{self.name} - Permutation Importance')
        plt.tight_layout()
        plt.gca().invert_yaxis()
        plt.savefig(f'{self.name}_permutation_importance.png', dpi=150, bbox_inches='tight')
        plt.close()


class PartialDependenceStep(Step):
    """Partial Dependence Plots (PDP) for feature effects."""
    
    def __init__(
        self,
        name: str,
        features: Union[int, str, List[Union[int, str]], List[tuple]],
        kind: str = "average",
        subsample: int = 1000,
        **kwargs
    ):
        """
        Args:
            features: Feature(s) to plot (indices, names, or pairs for 2-way PDP)
            kind: 'average', 'individual', or 'both'
            subsample: Number of samples to use for computation
        """
        super().__init__(name, **kwargs)
        self.features = features
        self.kind = kind
        self.subsample = subsample
        
    def run(self, model: Any, X: np.ndarray,
            feature_names: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """Compute partial dependence.
        
        Args:
            model: Trained model
            X: Feature matrix
            feature_names: Feature names
            
        Returns:
            Dictionary with PDP data
        """
        from sklearn.inspection import partial_dependence
        
        fnames = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        
        # Map feature names to indices
        if isinstance(self.features, list) and isinstance(self.features[0], str):
            feature_indices = [fnames.index(f) for f in self.features if f in fnames]
        else:
            feature_indices = self.features
        
        # Subsample if needed
        if len(X) > self.subsample:
            np.random.seed(42)
            indices = np.random.choice(len(X), self.subsample, replace=False)
            X = X[indices]
        
        pdp_results = partial_dependence(
            model, X, features=feature_indices,
            kind=self.kind, grid_resolution=100
        )
        
        return {
            'pdp_results': pdp_results,
            'features': feature_indices,
            'feature_names': [fnames[i] if isinstance(i, int) else str(i) for i in (feature_indices if isinstance(feature_indices, list) else [feature_indices])]
        }
    
    def visualize(self, **kwargs):
        """Generate PDP plots."""
        if self.output is None or 'pdp_results' not in self.output:
            return
        
        from sklearn.inspection import plot_partial_dependence
        import matplotlib.pyplot as plt
        
        pdp_results = self.output['pdp_results']
        feature_names = self.output.get('feature_names', [])
        
        # Create figure
        n_features = len(feature_names)
        fig, axes = plt.subplots(n_features, 1, figsize=(10, 4 * n_features))
        
        if n_features == 1:
            axes = [axes]
        
        for idx, (ax, fname) in enumerate(zip(axes, feature_names)):
            if idx < len(pdp_results['average']):
                grid_values = pdp_results['grid_values'][idx]
                avg_preds = pdp_results['average'][idx]
                
                ax.plot(grid_values, avg_preds.T)
                ax.set_xlabel(fname)
                ax.set_ylabel('Partial Dependence')
                ax.set_title(f'PDP for {fname}')
        
        plt.tight_layout()
        plt.savefig(f'{self.name}_pdp.png', dpi=150, bbox_inches='tight')
        plt.close()


class FeatureImportanceStep(Step):
    """Extract feature importance from tree-based models."""
    
    def __init__(
        self,
        name: str,
        importance_type: str = "auto",
        **kwargs
    ):
        """
        Args:
            importance_type: 'auto', 'gain', 'cover', or 'weight'
        """
        super().__init__(name, **kwargs)
        self.importance_type = importance_type
        
    def run(self, model: Any, feature_names: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """Extract feature importance from model.
        
        Args:
            model: Tree-based model
            feature_names: Feature names
            
        Returns:
            Dictionary with importance scores
        """
        # Try different methods
        importance = None
        
        # sklearn trees
        if hasattr(model, 'feature_importances_'):
            importance = model.feature_importances_
        # XGBoost
        elif hasattr(model, 'get_booster'):
            booster = model.get_booster()
            importance_dict = booster.get_score(importance_type=self.importance_type if self.importance_type != 'auto' else 'weight')
            importance = np.array([importance_dict.get(f'f{i}', 0) for i in range(model.n_features_in_)])
        # LightGBM
        elif hasattr(model, 'feature_importances'):
            importance = model.feature_importances()
        # CatBoost
        elif hasattr(model, 'get_feature_importance'):
            importance = model.get_feature_importance()
        
        if importance is None:
            raise ValueError(f"Model {type(model)} does not have feature importance")
        
        fnames = feature_names or [f"feature_{i}" for i in range(len(importance))]
        
        importance_dict = dict(zip(fnames, importance))
        sorted_importance = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        
        self.log_metrics(
            top_feature=sorted_importance[0][0] if sorted_importance else None,
            top_importance=sorted_importance[0][1] if sorted_importance else None
        )
        
        return {
            'importance': importance_dict,
            'sorted_importance': sorted_importance,
            'raw_importance': importance
        }
    
    def visualize(self, **kwargs):
        """Generate feature importance plot."""
        if self.output is None:
            return
        
        sorted_items = self.output.get('sorted_importance', [])[:20]
        
        if not sorted_items:
            return
        
        import matplotlib.pyplot as plt
        
        names = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]
        
        plt.figure(figsize=(10, 8))
        y_pos = np.arange(len(names))
        plt.barh(y_pos, values, align='center', alpha=0.7)
        plt.yticks(y_pos, names)
        plt.xlabel('Feature Importance')
        plt.title(f'{self.name} - Feature Importance')
        plt.tight_layout()
        plt.gca().invert_yaxis()
        plt.savefig(f'{self.name}_feature_importance.png', dpi=150, bbox_inches='tight')
        plt.close()


class AttentionVisualizerStep(Step):
    """Visualize attention weights from transformer models."""
    
    def __init__(
        self,
        name: str,
        layer: int = -1,
        head: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            layer: Layer to visualize (default: last layer)
            head: Specific attention head (None = average all heads)
        """
        super().__init__(name, **kwargs)
        self.layer = layer
        self.head = head
        
    def run(self, model: Any, input_ids: np.ndarray, tokenizer: Any = None,
            **kwargs) -> Dict[str, Any]:
        """Extract and visualize attention weights.
        
        Args:
            model: Transformer model with attention outputs
            input_ids: Token IDs
            tokenizer: Tokenizer for converting IDs to tokens
            
        Returns:
            Dictionary with attention data
        """
        import torch
        
        # Forward pass with attention outputs
        with torch.no_grad():
            outputs = model(input_ids, output_attentions=True)
            attentions = outputs.attentions
        
        # Select layer
        layer_attn = attentions[self.layer]  # (batch, heads, seq_len, seq_len)
        
        # Select or average heads
        if self.head is not None:
            attn_weights = layer_attn[0, self.head].cpu().numpy()
        else:
            attn_weights = layer_attn[0].mean(dim=0).cpu().numpy()
        
        # Get tokens if tokenizer provided
        tokens = None
        if tokenizer is not None:
            tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
        
        return {
            'attention_weights': attn_weights,
            'tokens': tokens,
            'layer': self.layer,
            'head': self.head
        }
    
    def visualize(self, **kwargs):
        """Generate attention heatmap."""
        if self.output is None:
            return
        
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        attn_weights = self.output['attention_weights']
        tokens = self.output.get('tokens')
        
        plt.figure(figsize=(12, 10))
        sns.heatmap(
            attn_weights,
            xticklabels=tokens if tokens else 'auto',
            yticklabels=tokens if tokens else 'auto',
            cmap='viridis',
            cbar_kws={'label': 'Attention Weight'}
        )
        plt.title(f'{self.name} - Attention Weights')
        plt.tight_layout()
        plt.savefig(f'{self.name}_attention.png', dpi=150, bbox_inches='tight')
        plt.close()


class ExplainabilityPipeline(Step):
    """Comprehensive explainability pipeline.
    
    Runs multiple explainability methods and aggregates results.
    """
    
    def __init__(
        self,
        name: str,
        methods: List[str] = None,
        feature_names: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Args:
            methods: List of methods to run ('shap', 'lime', 'permutation', 'feature_importance')
            feature_names: Feature names
        """
        super().__init__(name, **kwargs)
        self.methods = methods or ['permutation', 'feature_importance']
        self.feature_names = feature_names
        self.results = {}
        
    def run(self, model: Any, X_train: np.ndarray, y_train: np.ndarray,
            X_test: Optional[np.ndarray] = None, X_instance: Optional[np.ndarray] = None,
            **kwargs) -> Dict[str, Any]:
        """Run comprehensive explainability analysis.
        
        Args:
            model: Trained model
            X_train: Training features
            y_train: Training labels
            X_test: Test features
            X_instance: Single instance for local explanation
            
        Returns:
            Dictionary with all explanations
        """
        self.results = {}
        
        if 'feature_importance' in self.methods:
            try:
                step = FeatureImportanceStep(f"{self.name}_fi")
                self.results['feature_importance'] = step.run(
                    model, feature_names=self.feature_names, **kwargs
                )
            except Exception as e:
                logger.warning(f"Feature importance failed: {e}")
        
        if 'permutation' in self.methods:
            try:
                step = PermutationImportanceStep(f"{self.name}_perm")
                self.results['permutation'] = step.run(
                    model, X_train, y_train, feature_names=self.feature_names, **kwargs
                )
            except Exception as e:
                logger.warning(f"Permutation importance failed: {e}")
        
        if 'shap' in self.methods and X_test is not None:
            try:
                step = SHAPExplainerStep(f"{self.name}_shap", max_samples=100)
                self.results['shap'] = step.run(
                    model, X_test, feature_names=self.feature_names, **kwargs
                )
            except Exception as e:
                logger.warning(f"SHAP failed: {e}")
        
        if 'lime' in self.methods and X_instance is not None:
            try:
                step = LIMEExplainerStep(f"{self.name}_lime")
                self.results['lime'] = step.run(
                    model, X_train, X_instance, feature_names=self.feature_names, **kwargs
                )
            except Exception as e:
                logger.warning(f"LIME failed: {e}")
        
        # Aggregate feature ranks
        feature_ranks = self._aggregate_ranks()
        
        return {
            'explanations': self.results,
            'aggregated_ranks': feature_ranks
        }
    
    def _aggregate_ranks(self) -> Dict[str, float]:
        """Aggregate feature rankings across methods."""
        all_features = set()
        method_ranks = []
        
        for method, result in self.results.items():
            if 'sorted_importance' in result:
                sorted_imp = result['sorted_importance']
                ranks = {name: idx for idx, (name, _) in enumerate(sorted_imp)}
                all_features.update(ranks.keys())
                method_ranks.append(ranks)
        
        # Average ranks
        avg_ranks = {}
        for feature in all_features:
            ranks = [r.get(feature, len(all_features)) for r in method_ranks]
            avg_ranks[feature] = np.mean(ranks)
        
        return dict(sorted(avg_ranks.items(), key=lambda x: x[1]))
    
    def visualize(self, **kwargs):
        """Generate all visualizations."""
        for method, result in self.results.items():
            viz_method = f"_{method}_visualize"
            if hasattr(self, viz_method):
                getattr(self, viz_method)(result)
