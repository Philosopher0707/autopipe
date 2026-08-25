"""Data types for AutoPipe.

Type aliases and custom types for data handling in ML pipelines.
"""

from typing import TypeVar, Union

import numpy as np
import pandas as pd

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
    "Array",
    "DataFrame",
    "DataLike",
    "Series",
    "T",
    "TargetLike",
]
