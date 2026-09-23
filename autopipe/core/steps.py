"""Built-in pipeline steps."""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from ..llm import LLMFactory
from ..visualization import ChartGenerator
from .step import Step

logger = logging.getLogger(__name__)


class PrintStep(Step):
    """Step that prints its input."""

    def __init__(self, name: str, message: str = "", **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.message = message

    def run(self, **kwargs: Any) -> Any:
        print(f"[{self.name}] {self.message}")
        print(f"Input keys: {list(kwargs.keys())}")
        # Pass through first input or None
        if kwargs:
            return next(iter(kwargs.values()))
        return None


class LLMStep(Step):
    """Step that calls an LLM."""

    def __init__(
        self,
        name: str,
        provider: str = "openrouter",
        model: Optional[str] = None,
        prompt_template: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.provider = provider
        self.model = model
        self.prompt_template = prompt_template
        self.client: Optional[Any] = None

    def run(self, **kwargs: Any) -> str:
        """Format prompt with inputs and call LLM."""
        # Format prompt template using kwargs
        try:
            prompt = self.prompt_template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing key {e} in prompt template, using raw template")
            prompt = self.prompt_template

        if self.client is None:
            self.client = LLMFactory.create_client(self.provider, model=self.model)

        response = self.client.generate(prompt)
        self.log_metrics(response_length=len(response))
        return response

    def visualize(self, **kwargs: Any) -> None:
        """Generate a simple visualization of response length."""
        if self.metrics:
            chart = ChartGenerator()
            chart.plot_distribution(
                [self.metrics.get("response_length", 0)], title=f"LLM Response Length - {self.name}"
            )


class DataLoaderStep(Step):
    """Load a dataset (placeholder)."""

    def __init__(self, name: str, dataset: str = "iris", **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.dataset = dataset

    def run(self, **kwargs: Any) -> pd.DataFrame:
        """Load a sample dataset."""
        if self.dataset == "iris":
            from sklearn.datasets import load_iris

            iris = load_iris()
            df = pd.DataFrame(data=iris.data, columns=iris.feature_names)
            df["target"] = iris.target
        elif self.dataset == "diabetes":
            from sklearn.datasets import load_diabetes

            diabetes = load_diabetes()
            df = pd.DataFrame(data=diabetes.data, columns=diabetes.feature_names)
            df["target"] = diabetes.target
        else:
            raise ValueError(f"Unknown dataset {self.dataset}")
        from autopipe.core.artifacts import record_dataset_input

        # Builtin content is sklearn-version-defined; the environment
        # fingerprint pins scikit-learn, sha256 stays explicitly "unavailable".
        record_dataset_input({"kind": "builtin", "name": self.dataset, "sha256": "unavailable"})
        self.log_metrics(rows=df.shape[0], columns=df.shape[1])
        return df

    def visualize(self, **kwargs: Any) -> None:
        """Plot dataset distributions."""
        df = self.output
        if df is not None and isinstance(df, pd.DataFrame):
            chart = ChartGenerator()
            # Plot distribution of each numeric column
            for col in df.select_dtypes(include=[np.number]).columns:
                chart.plot_distribution(df[col].values, title=f"Distribution of {col}")


class VisualizationStep(Step):
    """Step that generates visualizations from input data."""

    def __init__(self, name: str, chart_type: str = "metrics", **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.chart_type = chart_type

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate charts and return metadata.

        Automatically detects input types:
        - Dict of lists (e.g., {'loss': [1,2,3], 'acc': [0.5,0.6,0.7]}) → metrics plot
        - List of numbers → distribution plot
        - DataFrame → feature importance
        """
        chart = ChartGenerator()
        outputs = {}
        for key, value in kwargs.items():
            # Dict of lists → plot as metrics
            if isinstance(value, dict) and all(
                isinstance(v, (list, tuple)) for v in value.values()
            ):
                chart.plot_metrics(value, title=f"Metrics - {key}")
                outputs[f"chart_{key}"] = f"metrics_{key}.png"
            # Dict with numeric values → plot as feature importance
            elif isinstance(value, dict) and all(
                isinstance(v, (int, float)) for v in value.values()
            ):
                chart.plot_feature_importance(value, top_n=min(20, len(value)))
                outputs[f"chart_{key}"] = f"feature_importance_{key}.png"
            # List of numbers → plot as distribution
            elif (
                isinstance(value, (list, tuple))
                and len(value) > 0
                and isinstance(value[0], (int, float))
            ):
                chart.plot_distribution([float(v) for v in value], title=f"Distribution - {key}")
                outputs[f"chart_{key}"] = f"distribution_{key}.png"
            # DataFrame → plot feature importance
            elif isinstance(value, pd.DataFrame):
                chart.plot_feature_importance(dict.fromkeys(value.columns[:5], 1.0), top_n=5)
                outputs[f"chart_{key}"] = "feature_importance.png"
            # Bare int/float → plot as distribution with single value
            elif isinstance(value, (int, float)):
                chart.plot_distribution([value], title=f"Value - {key}")
                outputs[f"chart_{key}"] = f"distribution_{key}.png"
        return outputs


class FeatureEngineeringStep(Step):
    """Step for automated feature engineering and preprocessing.

    Supports various transformations:
    - scaling: standard, minmax, robust, maxabs
    - encoding: onehot, ordinal, label (for categorical)
    - binning: KBins discretization
    - polynomial: polynomial feature generation
    - selection: variance_threshold, correlation
    - text: tfidf, count (for text columns)
    - datetime: extract day, month, year, hour etc.
    - math: log, sqrt, square, reciprocal transformations
    - interaction: multiply, add, divide features
    """

    def __init__(
        self,
        name: str,
        transformations: Optional[Dict[str, Any]] = None,
        target_column: Optional[str] = None,
        drop_original: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            name: Step name
            transformations: Dict of {operation: config}
                Examples:
                - {"scale": {"method": "standard", "columns": ["col1", "col2"]}}
                - {"encode": {"method": "onehot", "columns": ["category"]}}
                - {"polynomial": {"degree": 2, "columns": ["num1", "num2"]}}
                - {"binning": {"n_bins": 5, "columns": ["age"]}}
                - {"text_tfidf": {"columns": ["description"], "max_features": 100}}
                - {"datetime": {"columns": ["date"], "features": ["day", "month", "year"]}}
                - {"math": {"operation": "log", "columns": ["income"], "offset": 1}}
                - {"drop": {"columns": ["unnecessary_col"]}}
            target_column: Target variable name (for correlation selection)
            drop_original: Whether to drop original columns after transformation
            **kwargs: Additional step arguments
        """
        super().__init__(name, **kwargs)
        self.transformations = transformations or {}
        self.target_column = target_column
        self.drop_original = drop_original
        self._transformers: Dict[str, Any] = {}  # Store fitted transformers

    def run(self, **kwargs: Any) -> pd.DataFrame:
        """Apply feature engineering transformations."""
        # Get input DataFrame from dependencies
        df = None
        for _, value in kwargs.items():
            if isinstance(value, pd.DataFrame):
                df = value.copy()
                break

        if df is None:
            raise ValueError("FeatureEngineeringStep requires a DataFrame input")

        df_original = df.copy()
        new_features = {}
        columns_to_drop = []

        for operation, config in self.transformations.items():
            logger.info(f"Applying {operation} transformation")

            if operation == "scale":
                df, scaled_cols = self._apply_scaling(df, config)
                self.log_metrics(scaling_applied=len(scaled_cols))

            elif operation == "encode":
                df, encoded_cols = self._apply_encoding(df, config)
                self.log_metrics(encoding_applied=len(encoded_cols))

            elif operation == "polynomial":
                new_features_poly = self._apply_polynomial(df, config)
                new_features.update(new_features_poly)
                self.log_metrics(polynomial_features_generated=len(new_features_poly))

            elif operation == "binning":
                binned_features = self._apply_binning(df, config)
                new_features.update(binned_features)
                self.log_metrics(bins_created=len(binned_features))

            elif operation == "text_tfidf":
                text_features = self._apply_text_tfidf(df, config)
                new_features.update(text_features)
                self.log_metrics(text_features_generated=len(text_features))

            elif operation == "text_count":
                text_features = self._apply_text_count(df, config)
                new_features.update(text_features)
                self.log_metrics(text_features_generated=len(text_features))

            elif operation == "datetime":
                datetime_features = self._apply_datetime_extraction(df, config)
                new_features.update(datetime_features)
                self.log_metrics(datetime_features_generated=len(datetime_features))

            elif operation == "math":
                math_features = self._apply_math_transform(df, config)
                new_features.update(math_features)
                self.log_metrics(math_features_generated=len(math_features))

            elif operation == "interaction":
                interaction_features = self._apply_interaction(df, config)
                new_features.update(interaction_features)
                self.log_metrics(interaction_features_generated=len(interaction_features))

            elif operation == "drop":
                cols_to_drop = config.get("columns", [])
                columns_to_drop.extend(cols_to_drop)

            elif operation == "select":
                df = self._apply_feature_selection(df, config)
                self.log_metrics(selection_applied=True)

            else:
                logger.warning(f"Unknown transformation: {operation}")

        # Add all new features
        for col_name, series in new_features.items():
            df[col_name] = series

        # Drop specified columns
        if columns_to_drop:
            df = df.drop(columns=[c for c in columns_to_drop if c in df.columns], errors="ignore")

        # Drop original transformed columns if requested
        if self.drop_original:
            original_cols = set(df_original.columns) - set(new_features.keys())
            # Don't drop target column
            if self.target_column and self.target_column in original_cols:
                original_cols.remove(self.target_column)
            df = df.drop(columns=list(original_cols), errors="ignore")

        # Final metrics
        self.log_metrics(
            original_columns=len(df_original.columns),
            final_columns=len(df.columns),
            new_features_generated=len(new_features),
            rows=len(df),
        )

        return df

    def _apply_scaling(self, df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[Any, ...]:
        """Apply scaling transformations."""
        from sklearn.preprocessing import MaxAbsScaler, MinMaxScaler, RobustScaler, StandardScaler

        method = config.get("method", "standard")
        columns = config.get("columns", df.select_dtypes(include=[np.number]).columns.tolist())
        columns = [c for c in columns if c in df.columns]

        scalers = {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
            "maxabs": MaxAbsScaler(),
        }

        if method not in scalers:
            raise ValueError(f"Unknown scaling method: {method}")

        scaler = scalers[method]

        # Only scale numeric columns that exist
        numeric_cols = df[columns].select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
            self._transformers[f"scaler_{method}"] = scaler

        return df, list(numeric_cols)

    def _apply_encoding(self, df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[Any, ...]:
        """Apply categorical encoding."""
        from sklearn.preprocessing import LabelEncoder, OneHotEncoder, OrdinalEncoder

        method = config.get("method", "onehot")
        columns = config.get(
            "columns", df.select_dtypes(include=["object", "category"]).columns.tolist()
        )
        columns = [c for c in columns if c in df.columns]

        encoded_cols = []

        for col in columns:
            if method == "onehot":
                encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
                encoded = encoder.fit_transform(df[[col]])

                # Create column names
                feature_names = [f"{col}_{cat}" for cat in encoder.categories_[0]]
                for i, name in enumerate(feature_names):
                    df[name] = encoded[:, i]
                    encoded_cols.append(name)

                self._transformers[f"encoder_{col}"] = encoder

            elif method == "ordinal":
                encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
                df[f"{col}_encoded"] = encoder.fit_transform(df[[col]])
                encoded_cols.append(f"{col}_encoded")
                self._transformers[f"encoder_{col}"] = encoder

            elif method == "label":
                # For target encoding
                encoder = LabelEncoder()
                df[f"{col}_label"] = encoder.fit_transform(df[col].astype(str))
                encoded_cols.append(f"{col}_label")
                self._transformers[f"encoder_{col}"] = encoder

        return df, encoded_cols

    def _apply_polynomial(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Generate polynomial features."""
        from sklearn.preprocessing import PolynomialFeatures

        degree = config.get("degree", 2)
        columns = config.get("columns", df.select_dtypes(include=[np.number]).columns.tolist())
        columns = [c for c in columns if c in df.columns and c != self.target_column]

        if not columns:
            return {}

        poly = PolynomialFeatures(degree=degree, include_bias=False)
        features = poly.fit_transform(df[columns])

        # Generate feature names
        feature_names = poly.get_feature_names_out(columns)
        new_features = {}

        for i, name in enumerate(feature_names):
            if name not in columns:  # Only include new features
                new_features[name] = features[:, i]

        self._transformers["polynomial"] = poly
        return new_features

    def _apply_binning(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Apply binning/discretization."""
        from sklearn.preprocessing import KBinsDiscretizer

        n_bins = config.get("n_bins", 5)
        strategy = config.get("strategy", "quantile")
        columns = config.get("columns", [])
        columns = [c for c in columns if c in df.columns]

        new_features = {}

        for col in columns:
            if df[col].dtype in [np.float64, np.int64]:
                binner = KBinsDiscretizer(n_bins=n_bins, encode="ordinal", strategy=strategy)
                binned = binner.fit_transform(df[[col]])
                new_features[f"{col}_binned"] = binned.flatten()
                self._transformers[f"binner_{col}"] = binner

        return new_features

    def _apply_text_tfidf(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Apply TF-IDF to text columns."""
        from sklearn.feature_extraction.text import TfidfVectorizer

        columns = config.get("columns", [])
        max_features = config.get("max_features", 100)
        ngram_range = config.get("ngram_range", (1, 2))
        columns = [c for c in columns if c in df.columns]

        new_features = {}

        for col in columns:
            # Fill NaN with empty string
            texts = df[col].fillna("").astype(str)

            vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=ngram_range)
            tfidf_matrix = vectorizer.fit_transform(texts)

            # Get feature names and create columns
            feature_names = vectorizer.get_feature_names_out()
            for i, feature_name in enumerate(feature_names):
                new_features[f"{col}_tfidf_{feature_name}"] = tfidf_matrix[:, i].toarray().flatten()

            self._transformers[f"tfidf_{col}"] = vectorizer

        return new_features

    def _apply_text_count(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Apply Count Vectorizer to text columns."""
        from sklearn.feature_extraction.text import CountVectorizer

        columns = config.get("columns", [])
        max_features = config.get("max_features", 100)
        columns = [c for c in columns if c in df.columns]

        new_features = {}

        for col in columns:
            texts = df[col].fillna("").astype(str)

            vectorizer = CountVectorizer(max_features=max_features)
            count_matrix = vectorizer.fit_transform(texts)

            feature_names = vectorizer.get_feature_names_out()
            for i, feature_name in enumerate(feature_names):
                new_features[f"{col}_count_{feature_name}"] = count_matrix[:, i].toarray().flatten()

            self._transformers[f"count_{col}"] = vectorizer

        return new_features

    def _apply_datetime_extraction(
        self, df: pd.DataFrame, config: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """Extract features from datetime columns."""
        columns = config.get("columns", [])
        features = config.get("features", ["day", "month", "year", "dayofweek"])
        columns = [c for c in columns if c in df.columns]

        new_features = {}

        for col in columns:
            # Convert to datetime
            dt = pd.to_datetime(df[col], errors="coerce")

            for feature in features:
                if feature == "day":
                    new_features[f"{col}_day"] = dt.dt.day
                elif feature == "month":
                    new_features[f"{col}_month"] = dt.dt.month
                elif feature == "year":
                    new_features[f"{col}_year"] = dt.dt.year
                elif feature == "dayofweek":
                    new_features[f"{col}_dayofweek"] = dt.dt.dayofweek
                elif feature == "hour":
                    new_features[f"{col}_hour"] = dt.dt.hour
                elif feature == "quarter":
                    new_features[f"{col}_quarter"] = dt.dt.quarter
                elif feature == "is_weekend":
                    new_features[f"{col}_is_weekend"] = (dt.dt.dayofweek >= 5).astype(int)

        return new_features

    def _apply_math_transform(
        self, df: pd.DataFrame, config: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """Apply mathematical transformations."""
        operation = config.get("operation", "log")
        columns = config.get("columns", [])
        offset = config.get("offset", 0)  # For log(1+x) type transforms
        columns = [c for c in columns if c in df.columns]

        new_features = {}

        for col in columns:
            data = df[col].fillna(0) + offset

            if operation == "log":
                new_features[f"{col}_log"] = np.log1p(data)  # log(1+x) for stability
            elif operation == "sqrt":
                new_features[f"{col}_sqrt"] = np.sqrt(data.clip(lower=0))
            elif operation == "square":
                new_features[f"{col}_square"] = np.square(data)
            elif operation == "reciprocal":
                new_features[f"{col}_reciprocal"] = 1 / (data.replace(0, np.nan))
            elif operation == "boxcox":
                from scipy import stats

                # Box-Cox requires positive values
                positive_data = data[data > 0].dropna()
                if len(positive_data) > 0:
                    transformed, _ = stats.boxcox(positive_data)
                    new_features[f"{col}_boxcox"] = transformed

        return new_features

    def _apply_interaction(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Create interaction features between columns."""
        operation = config.get("operation", "multiply")  # multiply, add, divide, subtract
        column_pairs = config.get("pairs", [])  # List of [col1, col2] pairs

        new_features = {}

        for pair in column_pairs:
            if len(pair) == 2 and pair[0] in df.columns and pair[1] in df.columns:
                col1, col2 = pair[0], pair[1]

                if operation == "multiply":
                    new_features[f"{col1}_x_{col2}"] = df[col1] * df[col2]
                elif operation == "add":
                    new_features[f"{col1}_plus_{col2}"] = df[col1] + df[col2]
                elif operation == "divide":
                    # Handle division by zero
                    denominator = df[col2].replace(0, np.nan)
                    new_features[f"{col1}_div_{col2}"] = df[col1] / denominator
                elif operation == "subtract":
                    new_features[f"{col1}_minus_{col2}"] = df[col1] - df[col2]

        return new_features

    def _apply_feature_selection(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """Apply feature selection."""
        method = config.get("method", "variance_threshold")

        if method == "variance_threshold":
            from sklearn.feature_selection import VarianceThreshold

            threshold = config.get("threshold", 0.01)

            # Only apply to numeric columns
            numeric_df = df.select_dtypes(include=[np.number])
            selector = VarianceThreshold(threshold=threshold)

            try:
                selector.fit_transform(numeric_df)
                selected_features = numeric_df.columns[selector.get_support()].tolist()

                # Keep non-numeric columns and selected numeric
                non_numeric = [c for c in df.columns if c not in numeric_df.columns]
                return df[selected_features + non_numeric]
            except Exception:
                # If fails (e.g., all features same), return original
                return df

        elif method == "correlation":
            threshold = config.get("threshold", 0.95)

            numeric_df = df.select_dtypes(include=[np.number])

            # Correlation matrix
            corr_matrix = numeric_df.corr().abs()

            # Select upper triangle of correlation matrix
            upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))

            # Find features with correlation > threshold
            to_drop = [column for column in upper.columns if any(upper[column] > threshold)]

            return df.drop(columns=to_drop, errors="ignore")

        return df

    def visualize(self, **kwargs: Any) -> None:
        """Visualize feature engineering results."""
        chart = ChartGenerator()

        # Plot transformation metrics if available
        if self.metrics:
            metrics_to_plot = {
                k: [v]
                for k, v in self.metrics.items()
                if isinstance(v, (int, float)) and k not in ["rows"]
            }
            if metrics_to_plot:
                chart.plot_metrics(
                    metrics_to_plot, title=f"Feature Engineering Metrics - {self.name}"
                )
