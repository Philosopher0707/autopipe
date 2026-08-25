"""Data types for AutoPipe.

Type aliases and custom types for data handling in ML pipelines.
"""

from typing import TypeVar, Union
import pandas as pd
import numpy as np
from autopipe.data.types import DataFrame, Series, Array, DataLike, TargetLike

# Type variables for generic data types
T = TypeVar("T")

__all__ = [
    "DataFrame",
    "Series",
    "Array",
    "DataLike",
    "TargetLike",
    "T",
]
