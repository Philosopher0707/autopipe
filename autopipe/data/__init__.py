"""Data types for AutoPipe.

Type aliases and custom types for data handling in ML pipelines.
"""

from typing import TypeVar, Union

import numpy as np
import pandas as pd

from autopipe.data.types import Array, DataFrame, DataLike, Series, TargetLike

# Type variables for generic data types
T = TypeVar("T")

__all__ = [
    "Array",
    "DataFrame",
    "DataLike",
    "Series",
    "T",
    "TargetLike",
]
