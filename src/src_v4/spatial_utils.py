"""
Common spatial analysis utility functions
Shared between spatial_analysis.py and spatial_analysis_optimized.py
"""
import pandas as pd
import numpy as np
from pathlib import Path


def load_market_data(market_coords_file: Path) -> pd.DataFrame:
    """
    Load traditional market coordinate data

    Parameters:
    -----------
    market_coords_file : Path
        Path to market coordinates Excel file

    Returns:
    --------
    pd.DataFrame
        Market data with columns: market_id, district, market_name, X, Y
    """
    if not market_coords_file.exists():
        raise FileNotFoundError(
            f"Market coordinates file not found: {market_coords_file}\n"
            f"Please check the MARKET_COORDS_FILE path in config.py"
        )

    df = pd.read_excel(market_coords_file)

    market_df = pd.DataFrame({
        'market_id': df.iloc[:, 0],
        'district': df.iloc[:, 1],
        'market_name': df.iloc[:, 2],
        'X': df['X'],
        'Y': df['Y']
    })

    return market_df.dropna(subset=['X', 'Y', 'district', 'market_name'])


def calculate_distance(x1: float, y1: float, x2, y2) -> np.ndarray:
    """
    Calculate Euclidean distance between two points

    Parameters:
    -----------
    x1, y1 : float
        Coordinates of first point
    x2, y2 : array-like
        Coordinates of second point(s)

    Returns:
    --------
    np.ndarray
        Distance(s) between points
    """
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
