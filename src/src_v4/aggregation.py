"""
Applied aggregation functions for traditional market analysis
Three core metrics: MZ ratio, night activity, monthly growth rate
"""
import pandas as pd
import numpy as np
from typing import Dict

from config import MZ_AGE_CODES, DAYTIME_HOURS, NIGHT_HOURS


def calculate_mz_ratio(df: pd.DataFrame) -> float:
    """
    Calculate MZ generation (20-34 years) occupancy rate
    Formula: (MZ population / total population) * 100

    Parameters:
    -----------
    df : pd.DataFrame
        Flow data with AGE_GR_CD and FLOW_POP columns

    Returns:
    --------
    float
        MZ ratio percentage (0-100) or NaN if calculation not possible
    """
    if len(df) == 0:
        return np.nan

    mz_population = df[df['AGE_GR_CD'].isin(MZ_AGE_CODES)]['FLOW_POP'].sum()
    total_population = df['FLOW_POP'].sum()

    if total_population == 0:
        return np.nan

    return round((mz_population / total_population) * 100, 2)


def calculate_night_activity(df: pd.DataFrame) -> float:
    """
    Calculate night activity index (전체 유동인구 기준)
    Formula: (night average / daytime average - 1) * 100

    Parameters:
    -----------
    df : pd.DataFrame
        Flow data with TMST_CD and FLOW_POP columns

    Returns:
    --------
    float
        Night activity percentage or NaN if calculation not possible
    """
    if len(df) == 0:
        return np.nan

    daytime_avg = df[df['TMST_CD'].isin(DAYTIME_HOURS)]['FLOW_POP'].mean()
    night_avg = df[df['TMST_CD'].isin(NIGHT_HOURS)]['FLOW_POP'].mean()

    if pd.isna(daytime_avg) or daytime_avg == 0:
        return np.nan

    if pd.isna(night_avg):  # Check for missing night data
        return np.nan

    return round(((night_avg / daytime_avg) - 1) * 100, 2)


def calculate_mz_night_activity(df: pd.DataFrame) -> float:
    """
    Calculate MZ generation night activity index (MZ세대 기준)
    Formula: (MZ night average / MZ daytime average - 1) * 100

    Parameters:
    -----------
    df : pd.DataFrame
        Flow data with AGE_GR_CD, TMST_CD and FLOW_POP columns

    Returns:
    --------
    float
        MZ night activity percentage or NaN if calculation not possible
    """
    if len(df) == 0:
        return np.nan

    # MZ세대만 필터링
    mz_df = df[df['AGE_GR_CD'].isin(MZ_AGE_CODES)]

    if len(mz_df) == 0:
        return np.nan

    mz_daytime_avg = mz_df[mz_df['TMST_CD'].isin(DAYTIME_HOURS)]['FLOW_POP'].mean()
    mz_night_avg = mz_df[mz_df['TMST_CD'].isin(NIGHT_HOURS)]['FLOW_POP'].mean()

    if pd.isna(mz_daytime_avg) or mz_daytime_avg == 0:
        return np.nan

    if pd.isna(mz_night_avg):
        return np.nan

    return round(((mz_night_avg / mz_daytime_avg) - 1) * 100, 2)


def calculate_weekend_activity(df: pd.DataFrame) -> float:
    """
    Calculate weekend activity index
    Formula: (weekend average / weekday average - 1) * 100

    Parameters:
    -----------
    df : pd.DataFrame
        Flow data with DAY_CD and FLOW_POP columns

    Returns:
    --------
    float
        Weekend activity percentage or NaN if calculation not possible
    """
    if len(df) == 0:
        return np.nan

    #df_temp = df.copy()
    df['DAY_CD'] = pd.to_numeric(df['DAY_CD'], errors='coerce').astype('Int64')

    weekday_avg = df[df['DAY_CD'].isin([1, 2, 3, 4, 5])]['FLOW_POP'].mean()
    weekend_avg = df[df['DAY_CD'].isin([6, 7])]['FLOW_POP'].mean()

    if pd.isna(weekday_avg) or weekday_avg == 0:
        return np.nan

    if pd.isna(weekend_avg):
        return np.nan

    return round(((weekend_avg / weekday_avg) - 1) * 100, 2)


def calculate_mz_weekend_activity(df: pd.DataFrame) -> float:
    """
    Calculate MZ generation weekend activity index (MZ세대 기준)
    Formula: (MZ weekend average / MZ weekday average - 1) * 100

    Parameters:
    -----------
    df : pd.DataFrame
        Flow data with AGE_GR_CD, DAY_CD and FLOW_POP columns

    Returns:
    --------
    float
        MZ weekend activity percentage or NaN if calculation not possible
    """
    if len(df) == 0:
        return np.nan

    # MZ세대만 필터링
    mz_df = df[df['AGE_GR_CD'].isin(MZ_AGE_CODES)]
    
    mz_df.loc[:,'DAY_CD'] = pd.to_numeric(mz_df['DAY_CD'], errors='coerce').astype('Int64')

    if len(mz_df) == 0:
        return np.nan

    mz_weekday_avg = mz_df[mz_df['DAY_CD'].isin([1, 2, 3, 4, 5])]['FLOW_POP'].mean()
    mz_weekend_avg = mz_df[mz_df['DAY_CD'].isin([6, 7])]['FLOW_POP'].mean()

    if pd.isna(mz_weekday_avg) or mz_weekday_avg == 0:
        return np.nan

    if pd.isna(mz_weekend_avg):
        return np.nan

    return round(((mz_weekend_avg / mz_weekday_avg) - 1) * 100, 2)


def calculate_monthly_growth_rate(df: pd.DataFrame) -> float:
    """
    Calculate monthly growth rate using CAGR
    Formula: ((end_value / start_value) ^ (1 / n_months) - 1) * 100

    Parameters:
    -----------
    df : pd.DataFrame
        Flow data with STD_YM and FLOW_POP columns

    Returns:
    --------
    float
        Monthly growth rate (CAGR) percentage or NaN if calculation not possible
    """
    if len(df) == 0:
        return np.nan

    # STD_YM을 숫자로 변환 (복사 없이 직접 변환)
    df['STD_YM'] = pd.to_numeric(df['STD_YM'], errors='coerce')

    monthly = df.groupby('STD_YM')['FLOW_POP'].sum().sort_index()

    if len(monthly) < 2:
        return np.nan

    start_value = monthly.iloc[0]
    end_value = monthly.iloc[-1]
    n_months = len(monthly) - 1

    if start_value == 0 or n_months == 0:
        return np.nan

    cagr = (((end_value / start_value) ** (1 / n_months)) - 1) * 100

    return round(cagr, 2)


def aggregate_all_markets(market_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Apply all aggregations to each market

    Parameters:
    -----------
    market_data : Dict[str, pd.DataFrame]
        Dictionary mapping market names to their flow data

    Returns:
    --------
    pd.DataFrame
        Aggregated results with columns: market_name, district, mz_ratio,
        night_activity, mz_night_activity, monthly_growth_rate,
        total_records, total_population
    """
    results = []

    for market_name, df in market_data.items():
        result = {
            'market_name': market_name,
            'district': df['district'].iloc[0] if len(df) > 0 else None,
            'mz_ratio': calculate_mz_ratio(df),
            'night_activity': calculate_night_activity(df),
            'mz_night_activity': calculate_mz_night_activity(df),
            'weekend_activity': calculate_weekend_activity(df),
            'mz_weekend_activity': calculate_mz_weekend_activity(df),
            'monthly_growth_rate': calculate_monthly_growth_rate(df),
            'total_records': len(df),
            'total_population': df['FLOW_POP'].sum()
        }

        results.append(result)

    return pd.DataFrame(results)