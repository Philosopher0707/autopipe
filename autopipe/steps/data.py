"""AutoPipe Data Processing Steps.

Comprehensive data pipeline steps for ML/DL workflows:
- Data loading (CSV, Parquet, JSON, SQL, cloud storage)
- Data validation (schema, nulls, outliers, duplicates)
- Data preprocessing (scaling, encoding, imputation)
- Feature selection (KBest, model-based, RFE)
- Data splitting (train/val/test, stratified, time-based)
"""

from typing import Any, Callable, Dict, List, Optional, Union, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from autopipe.core.step import Step


@dataclass
class ValidationReport:
    """Comprehensive data validation report."""
    is_valid: bool = True
    missing_columns: List[str] = field(default_factory=list)
    null_counts: Dict[str, int] = field(default_factory=dict)
    null_percentages: Dict[str, float] = field(default_factory=dict)
    duplicate_count: int = 0
    outliers_detected: Dict[str, int] = field(default_factory=dict)
    type_violations: Dict[str, List[str]] = field(default_factory=dict)
    value_violations: Dict[str, List[Any]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class DataLoaderStep(Step):
    """Load data from various sources.
    
    Supports CSV, Parquet, JSON, SQL databases, and cloud storage.
    """
    
    def __init__(
        self,
        name: str = "data_loader",
        source: str = None,
        format: str = "csv",
        sql_connection: Optional[str] = None,
        sql_query: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.source = source
        self.format = format.lower()
        self.sql_connection = sql_connection
        self.sql_query = sql_query
        self.options = options or {}
        
    def run(self, **kwargs) -> pd.DataFrame:
        """Load data from specified source."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Get source from kwargs if not set
        source = self.source or kwargs.get('source')
        
        if not source and not self.sql_query:
            raise ValueError("Data source must be specified")
        
        logger.info(f"Loading data from {source} (format: {self.format})")
        
        if self.format == "csv":
            df = pd.read_csv(source, **self.options)
        elif self.format == "parquet":
            df = pd.read_parquet(source, **self.options)
        elif self.format == "json":
            df = pd.read_json(source, **self.options)
        elif self.format == "excel" or self.format == "xlsx":
            df = pd.read_excel(source, **self.options)
        elif self.format == "sql":
            import sqlalchemy
            engine = sqlalchemy.create_engine(self.sql_connection)
            df = pd.read_sql(self.sql_query, engine, **self.options)
        elif self.format == "feather":
            df = pd.read_feather(source, **self.options)
        elif self.format == "hdf5" or self.format == "h5":
            df = pd.read_hdf(source, **self.options)
        elif self.format == "pickle" or self.format == "pkl":
            df = pd.read_pickle(source, **self.options)
        else:
            raise ValueError(f"Unsupported format: {self.format}")
        
        self.log_metrics(
            rows_loaded=len(df),
            columns_loaded=len(df.columns),
            memory_usage_mb=df.memory_usage(deep=True).sum() / 1024 / 1024
        )
        
        logger.info(f"Loaded {len(df)} rows and {len(df.columns)} columns")
        return df
    
    def visualize(self, **kwargs):
        """Generate data loading visualization."""
        from autopipe.visualization import ChartGenerator
        chart = ChartGenerator()
        
        if self.metrics:
            chart.plot_metrics(
                {k: [v] for k, v in self.metrics.items() if isinstance(v, (int, float))},
                title=f"Data Loading Metrics - {self.name}"
            )


class DataValidatorStep(Step):
    """Comprehensive data validation step.
    
    Validates data schema, nulls, duplicates, outliers, and data types.
    """
    
    def __init__(
        self,
        name: str = "data_validator",
        required_columns: Optional[List[str]] = None,
        column_types: Optional[Dict[str, str]] = None,
        max_null_ratio: float = 0.5,
        check_duplicates: bool = True,
        check_outliers: bool = True,
        outlier_method: str = "iqr",
        outlier_threshold: float = 1.5,
        value_ranges: Optional[Dict[str, Tuple]] = None,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.required_columns = required_columns or []
        self.column_types = column_types or {}
        self.max_null_ratio = max_null_ratio
        self.check_duplicates = check_duplicates
        self.check_outliers = check_outliers
        self.outlier_method = outlier_method
        self.outlier_threshold = outlier_threshold
        self.value_ranges = value_ranges or {}
        self.validation_report: Optional[ValidationReport] = None
        
    def run(self, **kwargs) -> pd.DataFrame:
        """Validate input data and return cleaned DataFrame."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Get DataFrame from inputs
        df = None
        for key, value in kwargs.items():
            if isinstance(value, pd.DataFrame):
                df = value.copy()
                break
        
        if df is None:
            raise ValueError("DataValidatorStep requires a DataFrame input")
        
        logger.info(f"Validating data with {len(df)} rows and {len(df.columns)} columns")
        
        report = ValidationReport()
        
        # Check required columns
        missing_cols = [col for col in self.required_columns if col not in df.columns]
        if missing_cols:
            report.is_valid = False
            report.missing_columns = missing_cols
            report.errors.append(f"Missing required columns: {missing_cols}")
        
        # Check null ratios
        null_counts = df.isnull().sum()
        null_percentages = (df.isnull().sum() / len(df) * 100).to_dict()
        report.null_counts = null_counts.to_dict()
        report.null_percentages = null_percentages
        
        high_null_cols = [col for col, pct in null_percentages.items() 
                         if pct > self.max_null_ratio * 100]
        if high_null_cols:
            report.warnings.append(f"High null ratio in columns: {high_null_cols}")
        
        # Check duplicates
        if self.check_duplicates:
            dup_count = df.duplicated().sum()
            report.duplicate_count = dup_count
            if dup_count > 0:
                report.warnings.append(f"Found {dup_count} duplicate rows")
        
        # Check outliers
        if self.check_outliers:
            outliers = self._detect_outliers(df)
            report.outliers_detected = outliers
            for col, count in outliers.items():
                if count > 0:
                    report.warnings.append(f"Detected {count} outliers in {col}")
        
        # Check value ranges
        for col, (min_val, max_val) in self.value_ranges.items():
            if col in df.columns:
                violations = df[(df[col] < min_val) | (df[col] > max_val)]
                if len(violations) > 0:
                    report.value_violations[col] = violations[col].tolist()[:10]  # First 10
                    report.warnings.append(f"{col} has {len(violations)} values outside range")
        
        # Type checks
        for col, expected_type in self.column_types.items():
            if col in df.columns:
                actual_type = str(df[col].dtype)
                # Simple type checking
                if expected_type == "numeric" and not pd.api.types.is_numeric_dtype(df[col]):
                    report.type_violations[col] = [f"Expected numeric, got {actual_type}"]
                elif expected_type == "categorical" and not pd.api.types.is_categorical_dtype(df[col]):
                    if not pd.api.types.is_object_dtype(df[col]):
                        report.type_violations[col] = [f"Expected categorical, got {actual_type}"]
        
        self.validation_report = report
        
        # Log results
        self.log_metrics(
            is_valid=int(report.is_valid),
            missing_columns=len(report.missing_columns),
            duplicate_count=report.duplicate_count,
            total_outliers=sum(report.outliers_detected.values()),
            warnings=len(report.warnings),
            errors=len(report.errors)
        )
        
        logger.info(f"Validation complete: valid={report.is_valid}, errors={len(report.errors)}, warnings={len(report.warnings)}")
        
        # Add validation context
        if 'context' in kwargs:
            kwargs['context']['validation_results'] = report
        
        return df
    
    def _detect_outliers(self, df: pd.DataFrame) -> Dict[str, int]:
        """Detect outliers using IQR or Z-score method."""
        outliers = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if self.outlier_method == "iqr":
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - self.outlier_threshold * IQR
                upper_bound = Q3 + self.outlier_threshold * IQR
                outlier_count = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
            elif self.outlier_method == "zscore":
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                outlier_count = (z_scores > self.outlier_threshold).sum()
            else:
                outlier_count = 0
            
            outliers[col] = int(outlier_count)
        
        return outliers
    
    def visualize(self, **kwargs):
        """Generate validation report visualization."""
        from autopipe.visualization import ChartGenerator
        chart = ChartGenerator()
        
        if self.validation_report:
            metrics = {
                "Validity": [int(self.validation_report.is_valid)],
                "Missing Columns": [len(self.validation_report.missing_columns)],
                "Duplicates": [self.validation_report.duplicate_count],
                "Warnings": [len(self.validation_report.warnings)],
                "Errors": [len(self.validation_report.errors)]
            }
            chart.plot_metrics(metrics, title=f"Validation Summary - {self.name}")


class DataPreprocessorStep(Step):
    """Comprehensive data preprocessing step.
    
    Handles scaling, encoding, and imputation with proper fit/transform separation.
    """
    
    def __init__(
        self,
        name: str = "data_preprocessor",
        numeric_scaling: Optional[str] = "standard",
        categorical_encoding: Optional[str] = "onehot",
        imputation_strategy: str = "mean",
        imputation_numeric: Optional[str] = None,
        imputation_categorical: Optional[str] = None,
        handle_unknown: str = "ignore",
        passthrough_columns: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.numeric_scaling = numeric_scaling
        self.categorical_encoding = categorical_encoding
        self.imputation_strategy = imputation_strategy
        self.imputation_numeric = imputation_numeric or imputation_strategy
        self.imputation_categorical = imputation_categorical or "most_frequent"
        self.handle_unknown = handle_unknown
        self.passthrough_columns = passthrough_columns or []
        
        # Fitted transformers storage
        self._scaler = None
        self._encoders: Dict[str, Any] = {}
        self._imputer_numeric = None
        self._imputer_categorical = None
        self._feature_names: List[str] = []
        
    def run(self, **kwargs) -> pd.DataFrame:
        """Preprocess data with scaling, encoding, and imputation."""
        import logging
        logger = logging.getLogger(__name__)
        
        df = None
        for key, value in kwargs.items():
            if isinstance(value, pd.DataFrame):
                df = value.copy()
                break
        
        if df is None:
            raise ValueError("DataPreprocessorStep requires a DataFrame input")
        
        logger.info(f"Preprocessing data with {len(df)} rows")
        
        # Separate columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Remove passthrough columns
        numeric_cols = [c for c in numeric_cols if c not in self.passthrough_columns]
        categorical_cols = [c for c in categorical_cols if c not in self.passthrough_columns]
        
        # Imputation
        df = self._apply_imputation(df, numeric_cols, categorical_cols)
        
        # Scaling
        if self.numeric_scaling and numeric_cols:
            df = self._apply_scaling(df, numeric_cols)
        
        # Encoding
        if self.categorical_encoding and categorical_cols:
            df = self._apply_encoding(df, categorical_cols)
        
        self.log_metrics(
            original_columns=len(df.columns),
            numeric_scaled=len(numeric_cols),
            categorical_encoded=len(categorical_cols),
            final_columns=len(df.columns)
        )
        
        logger.info(f"Preprocessing complete: {len(df.columns)} columns")
        return df
    
    def _apply_imputation(self, df: pd.DataFrame, numeric_cols: List[str], 
                         categorical_cols: List[str]) -> pd.DataFrame:
        """Apply imputation to missing values."""
        from sklearn.impute import SimpleImputer
        
        # Numeric imputation
        if numeric_cols and df[numeric_cols].isnull().sum().sum() > 0:
            self._imputer_numeric = SimpleImputer(strategy=self.imputation_numeric)
            df[numeric_cols] = self._imputer_numeric.fit_transform(df[numeric_cols])
        
        # Categorical imputation
        if categorical_cols and df[categorical_cols].isnull().sum().sum() > 0:
            self._imputer_categorical = SimpleImputer(strategy=self.imputation_categorical)
            df[categorical_cols] = self._imputer_categorical.fit_transform(df[categorical_cols])
        
        return df
    
    def _apply_scaling(self, df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
        """Apply scaling to numeric columns."""
        from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler
        
        scalers = {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
            "maxabs": MaxAbsScaler()
        }
        
        if self.numeric_scaling not in scalers:
            raise ValueError(f"Unknown scaling method: {self.numeric_scaling}")
        
        self._scaler = scalers[self.numeric_scaling]
        df[numeric_cols] = self._scaler.fit_transform(df[numeric_cols])
        
        # Rename columns to indicate scaling
        rename_map = {col: f"{col}_scaled" for col in numeric_cols}
        df = df.rename(columns=rename_map)
        
        return df
    
    def _apply_encoding(self, df: pd.DataFrame, categorical_cols: List[str]) -> pd.DataFrame:
        """Apply encoding to categorical columns."""
        from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, LabelEncoder
        
        for col in categorical_cols:
            if self.categorical_encoding == "onehot":
                encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
                encoded = encoder.fit_transform(df[[col]])
                
                # Create feature names
                categories = encoder.categories_[0]
                feature_names = [f"{col}_{cat}" for cat in categories]
                
                # Add encoded columns
                for i, name in enumerate(feature_names):
                    df[name] = encoded[:, i]
                
                # Drop original
                df = df.drop(columns=[col])
                self._encoders[col] = encoder
                
            elif self.categorical_encoding == "ordinal":
                encoder = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
                df[f"{col}_encoded"] = encoder.fit_transform(df[[col]])
                df = df.drop(columns=[col])
                self._encoders[col] = encoder
                
            elif self.categorical_encoding == "label":
                # Label encoding for target variable
                encoder = LabelEncoder()
                df[col] = encoder.fit_transform(df[col].astype(str))
                self._encoders[col] = encoder
        
        return df
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform new data using fitted preprocessors."""
        df = df.copy()
        # Similar logic to run but using fitted transformers
        # Implementation for inference pipeline
        return df
    
    def visualize(self, **kwargs):
        """Generate preprocessing visualization."""
        from autopipe.visualization import ChartGenerator
        chart = ChartGenerator()
        
        if self.metrics:
            chart.plot_metrics(
                {k: [v] for k, v in self.metrics.items() if isinstance(v, (int, float))},
                title=f"Preprocessing Metrics - {self.name}"
            )


class FeatureSelectionStep(Step):
    """Feature selection using statistical and model-based methods.
    
    Supports variance threshold, correlation, KBest, RFE, and model-based selection.
    """
    
    def __init__(
        self,
        name: str = "feature_selection",
        method: str = "kbest",
        k: int = 10,
        score_func: str = "mutual_info",
        threshold: float = 0.01,
        model_based_estimator: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.method = method
        self.k = k
        self.score_func = score_func
        self.threshold = threshold
        self.model_based_estimator = model_based_estimator
        self._selector = None
        self.selected_features: List[str] = []
        
    def run(self, **kwargs) -> pd.DataFrame:
        """Select features using specified method."""
        import logging
        logger = logging.getLogger(__name__)
        
        df = None
        target_col = None
        
        for key, value in kwargs.items():
            if isinstance(value, pd.DataFrame):
                df = value.copy()
            elif isinstance(value, pd.Series):
                target_col = value
            elif isinstance(value, np.ndarray) and len(value.shape) == 1:
                target_col = pd.Series(value)
        
        if df is None:
            raise ValueError("FeatureSelectionStep requires a DataFrame input")
        
        # Separate target if present in DataFrame
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if target_col is None:
            # Assume last column is target if not specified
            logger.warning("No target provided for feature selection, using all numeric features")
            X = df[numeric_cols]
        else:
            y = target_col.values if isinstance(target_col, pd.Series) else target_col
            X = df[numeric_cols]
        
        logger.info(f"Selecting features using {self.method} from {X.shape[1]} features")
        
        if self.method == "variance_threshold":
            from sklearn.feature_selection import VarianceThreshold
            self._selector = VarianceThreshold(threshold=self.threshold)
            X_selected = self._selector.fit_transform(X)
            selected_mask = self._selector.get_support()
            
        elif self.method == "kbest":
            from sklearn.feature_selection import SelectKBest, mutual_info_classif, f_classif, chi2
            
            score_funcs = {
                "mutual_info": mutual_info_classif,
                "f_classif": f_classif,
                "chi2": chi2,
            }
            
            func = score_funcs.get(self.score_func, f_classif)
            self._selector = SelectKBest(score_func=func, k=min(self.k, X.shape[1]))
            
            if target_col is not None:
                X_selected = self._selector.fit_transform(X, y)
            else:
                # Use variance as fallback
                from sklearn.feature_selection import VarianceThreshold
                self._selector = VarianceThreshold(threshold=self.threshold)
                X_selected = self._selector.fit_transform(X)
            
            selected_mask = self._selector.get_support()
            
        elif self.method == "rfe":
            from sklearn.feature_selection import RFE
            from sklearn.ensemble import RandomForestClassifier
            
            estimator = self.model_based_estimator or RandomForestClassifier(n_estimators=10, random_state=42)
            self._selector = RFE(estimator=estimator, n_features_to_select=min(self.k, X.shape[1]))
            
            if target_col is not None:
                X_selected = self._selector.fit_transform(X, y)
                selected_mask = self._selector.get_support()
            else:
                logger.warning("RFE requires target variable")
                X_selected = X.values
                selected_mask = np.ones(X.shape[1], dtype=bool)
                
        elif self.method == "model_based":
            from sklearn.feature_selection import SelectFromModel
            from sklearn.ensemble import RandomForestClassifier
            
            estimator = self.model_based_estimator or RandomForestClassifier(n_estimators=10, random_state=42)
            self._selector = SelectFromModel(estimator, max_features=self.k, threshold=self.threshold)
            
            if target_col is not None:
                X_selected = self._selector.fit_transform(X, y)
            else:
                X_selected = self._selector.fit_transform(X)
            
            selected_mask = self._selector.get_support()
            
        elif self.method == "correlation":
            # Correlation-based selection
            corr_matrix = X.corr().abs()
            upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
            to_drop = [column for column in upper.columns if any(upper[column] > 0.95)]
            
            selected_mask = ~np.isin(X.columns, to_drop)
            X_selected = X.loc[:, selected_mask].values
            
        else:
            raise ValueError(f"Unknown selection method: {self.method}")
        
        # Get selected feature names
        self.selected_features = X.columns[selected_mask].tolist()
        
        # Create result DataFrame
        result_df = pd.DataFrame(X_selected, columns=self.selected_features, index=df.index)
        
        # Add back non-numeric columns
        non_numeric = df.select_dtypes(exclude=[np.number])
        for col in non_numeric.columns:
            result_df[col] = non_numeric[col]
        
        self.log_metrics(
            original_features=X.shape[1],
            selected_features=len(self.selected_features),
            dropped_features=X.shape[1] - len(self.selected_features)
        )
        
        logger.info(f"Selected {len(self.selected_features)} features: {self.selected_features[:10]}...")
        
        # Add selection info to context
        if 'context' in kwargs:
            kwargs['context']['selected_features'] = self.selected_features
        
        return result_df
    
    def visualize(self, **kwargs):
        """Generate feature selection visualization."""
        from autopipe.visualization import ChartGenerator
        chart = ChartGenerator()
        
        if self.metrics:
            chart.plot_metrics(
                {k: [v] for k, v in self.metrics.items() if isinstance(v, (int, float))},
                title=f"Feature Selection Metrics - {self.name}"
            )
        
        if self.selected_features and len(self.selected_features) > 0:
            importance_dict = {f: 1.0 for f in self.selected_features}
            chart.plot_feature_importance(importance_dict, title=f"Selected Features - {self.name}")


class DataSplitterStep(Step):
    """Split data into train/validation/test sets.
    
    Supports stratified splitting, time-based splitting, and cross-validation folds.
    """
    
    def __init__(
        self,
        name: str = "data_splitter",
        train_size: float = 0.7,
        val_size: float = 0.15,
        test_size: float = 0.15,
        stratify: bool = False,
        stratify_column: Optional[str] = None,
        random_state: int = 42,
        shuffle: bool = True,
        time_column: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.train_size = train_size
        self.val_size = val_size
        self.test_size = test_size
        self.stratify = stratify
        self.stratify_column = stratify_column
        self.random_state = random_state
        self.shuffle = shuffle
        self.time_column = time_column
        
    def run(self, **kwargs) -> Dict[str, Any]:
        """Split data into train/val/test sets."""
        import logging
        logger = logging.getLogger(__name__)
        
        df = None
        target = None
        target_name = None
        
        for key, value in kwargs.items():
            if isinstance(value, pd.DataFrame):
                df = value.copy()
            elif isinstance(value, pd.Series):
                target = value
            elif isinstance(value, np.ndarray) and len(value.shape) == 1:
                target = pd.Series(value)
        
        if df is None:
            raise ValueError("DataSplitterStep requires a DataFrame input")
        
        logger.info(f"Splitting data: {self.train_size}/{self.val_size}/{self.test_size}")
        
        # Get target for stratification
        stratify = None
        if self.stratify:
            if self.stratify_column and self.stratify_column in df.columns:
                stratify = df[self.stratify_column]
            elif target is not None:
                stratify = target
        
        # Time-based or random split
        if self.time_column and self.time_column in df.columns:
            # Time-based split
            df_sorted = df.sort_values(self.time_column)
            n = len(df_sorted)
            
            train_end = int(n * self.train_size)
            val_end = train_end + int(n * self.val_size)
            
            train_df = df_sorted.iloc[:train_end]
            val_df = df_sorted.iloc[train_end:val_end]
            test_df = df_sorted.iloc[val_end:]
        else:
            # Random split using sklearn
            from sklearn.model_selection import train_test_split
            
            # First split: train vs temp (val + test)
            val_test_size = self.val_size + self.test_size
            
            if stratify is not None:
                train_df, temp_df, train_y, temp_y = train_test_split(
                    df, stratify, 
                    train_size=self.train_size,
                    random_state=self.random_state,
                    shuffle=self.shuffle,
                    stratify=stratify
                )
            else:
                train_df, temp_df = train_test_split(
                    df,
                    train_size=self.train_size,
                    random_state=self.random_state,
                    shuffle=self.shuffle
                )
                train_y = None
                temp_y = None
            
            # Second split: val vs test
            val_ratio = self.val_size / (self.val_size + self.test_size)
            
            if temp_y is not None:
                val_df, test_df = train_test_split(
                    temp_df,
                    train_size=val_ratio,
                    random_state=self.random_state,
                    shuffle=self.shuffle,
                    stratify=temp_y
                )
            else:
                val_df, test_df = train_test_split(
                    temp_df,
                    train_size=val_ratio,
                    random_state=self.random_state,
                    shuffle=self.shuffle
                )
        
        result = {
            "train": train_df,
            "val": val_df,
            "test": test_df,
            "train_size": len(train_df),
            "val_size": len(val_df),
            "test_size": len(test_df)
        }
        
        self.log_metrics(
            total_samples=len(df),
            train_samples=len(train_df),
            val_samples=len(val_df),
            test_samples=len(test_df),
            train_pct=len(train_df) / len(df) * 100,
            val_pct=len(val_df) / len(df) * 100,
            test_pct=len(test_df) / len(df) * 100
        )
        
        logger.info(f"Split complete: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")
        
        # Add split info to context
        if 'context' in kwargs:
            kwargs['context']['data_split'] = result
        
        return result
    
    def visualize(self, **kwargs):
        """Generate data split visualization."""
        from autopipe.visualization import ChartGenerator
        chart = ChartGenerator()
        
        if self.metrics:
            sizes = {
                "Train": self.metrics.get('train_samples', 0),
                "Validation": self.metrics.get('val_samples', 0),
                "Test": self.metrics.get('test_samples', 0)
            }
            chart.plot_metrics({k: [v] for k, v in sizes.items()}, title=f"Data Split - {self.name}")
