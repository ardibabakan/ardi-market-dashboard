"""
Safe extraction of scalar values from pandas objects.
Prevents the '>' not supported between dict and int errors.
"""
import pandas as pd
import numpy as np

def safe_scalar(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, dict):
        return default
    if isinstance(val, pd.Series):
        if val.empty:
            return default
        val = val.iloc[0]
    if isinstance(val, pd.DataFrame):
        if val.empty:
            return default
        val = val.iloc[0, 0]
    try:
        f = float(val)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default
