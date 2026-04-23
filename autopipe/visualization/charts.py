"""Chart generation utilities."""
import logging
import os
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

class ChartGenerator:
    """Generate common ML charts."""

    def __init__(self, output_dir: str = "./figures"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _save_fig(self, filename: str):
        """Save current matplotlib figure."""
        path = os.path.join(self.output_dir, filename)
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved figure to {path}")

    def plot_metrics(self, metrics: Dict[str, List[float]], title: str = "Training Metrics"):
        """Plot training metrics over epochs."""
        fig, axes = plt.subplots(1, 1, figsize=(8, 5))
        for name, values in metrics.items():
            axes.plot(values, label=name)
        axes.set_xlabel("Epoch")
        axes.set_ylabel("Value")
        axes.set_title(title)
        axes.legend()
        axes.grid(True, alpha=0.3)
        self._save_fig(f"metrics_{title.lower().replace(' ', '_')}.png")

    def plot_confusion_matrix(self, cm: np.ndarray, class_names: Optional[List[str]] = None):
        """Plot confusion matrix."""
        import seaborn as sns
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
        ax.set_xlabel('Predicted')
        ax.set_ylabel('True')
        ax.set_title('Confusion Matrix')
        if class_names:
            ax.set_xticklabels(class_names)
            ax.set_yticklabels(class_names)
        self._save_fig("confusion_matrix.png")

    def plot_feature_importance(self, importance: Dict[str, float], top_n: int = 20):
        """Plot feature importance (e.g., from tree-based models)."""
        sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:top_n]
        features, scores = zip(*sorted_items)
        fig, ax = plt.subplots(figsize=(10, 6))
        y_pos = np.arange(len(features))
        ax.barh(y_pos, scores)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(features)
        ax.invert_yaxis()
        ax.set_xlabel('Importance')
        ax.set_title('Feature Importance')
        self._save_fig("feature_importance.png")

    def plot_distribution(self, data: List[float], bins: int = 30, title: str = "Distribution"):
        """Plot histogram of data distribution."""
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(data, bins=bins, edgecolor='black', alpha=0.7)
        ax.set_xlabel('Value')
        ax.set_ylabel('Frequency')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        self._save_fig(f"distribution_{title.lower().replace(' ', '_')}.png")

    def plot_scatter(self, x: List[float], y: List[float], xlabel: str = "X", ylabel: str = "Y", title: str = "Scatter Plot"):
        """Scatter plot."""
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(x, y, alpha=0.6)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        self._save_fig(f"scatter_{title.lower().replace(' ', '_')}.png")

    def plot_learning_curve(self, train_sizes: List[float], train_scores: List[float], val_scores: List[float]):
        """Plot learning curve."""
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(train_sizes, train_scores, 'o-', label='Training score')
        ax.plot(train_sizes, val_scores, 'o-', label='Validation score')
        ax.set_xlabel('Training examples')
        ax.set_ylabel('Score')
        ax.set_title('Learning Curve')
        ax.legend()
        ax.grid(True, alpha=0.3)
        self._save_fig("learning_curve.png")
