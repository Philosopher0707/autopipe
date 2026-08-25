"""Data types for AutoPipe.

Type aliases and custom types for data handling in ML pipelines.
"""

from typing import TypeVar, Union
import pandas as pd
import numpy as np

# Type variables for generic data types
T = TypeVar("T")

# Common data types used in ML pipelines
DataFrame = pd.DataFrame
Series = pd.Series
Array = np.ndarray

# Union types for flexible input handling
DataLike = Union[pd.DataFrame, np.ndarray]
TargetLike = Union[pd.Series, np.ndarray]

__all__ = [
    "DataFrame",
    "Series",
    "Array",
    "DataLike",
    "TargetLike",
    "T",
]
