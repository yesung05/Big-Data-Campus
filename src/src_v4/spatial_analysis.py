"""
Spatial analysis functions for traditional market and flow population data
Uses simple distance calculation without heavy geospatial libraries
"""
import pandas as pd
import numpy as np

from config import BUFFER_DISTANCE, MARKET_COORDS_FILE
from spatial_analysis_optimized import transform_b009_to_long_format


def load_market_data():
    """Load traditional market coordinate data"""
    df = pd.read_excel(MARKET_COORDS_FILE)

    # Extract needed columns
    market_df = pd.DataFrame({
        'market_id': df.iloc[:, 0],
        'district': df.iloc[:, 1],
        'market_name': df.iloc[:, 2],
        'X': df['X'],
        'Y': df['Y']
    })

    return market_df.dropna(subset=['X', 'Y', 'district', 'market_name'])


def load_flow_data(filepath, sample_size=None, data_source='B008'):
    """
    Load flow population data from TXT/CSV file

    Parameters:
    -----------
    filepath : str or Path
        Path to TXT or CSV file
    sample_size : int, optional
        Number of rows to load (for testing)
    data_source : str
        'B008' for SKT data (pipe delimiter) or 'B009' for KT data (comma delimiter)
    """
    from config import B008_DELIMITER, B008_ENCODING, B008_COLUMN_NAMES
    from config import B009_DELIMITER, B009_ENCODING, B009_COLUMN_NAMES_WLK
    from pathlib import Path

    # Determine delimiter and column names based on data source
    if data_source == 'B008':
        delimiter = B008_DELIMITER
        encoding = B008_ENCODING
        column_names = B008_COLUMN_NAMES
    else:  # B009
        delimiter = B009_DELIMITER
        encoding = B009_ENCODING
        column_names = B009_COLUMN_NAMES_WLK

    # Check if file is CSV (sample data) or TXT (original data)
    filepath = Path(filepath)
    is_csv = filepath.suffix.lower() == '.csv'

    # Load file with appropriate settings
    if is_csv:
        # Sample CSV file: has header, use comma delimiter
        if sample_size:
            df = pd.read_csv(filepath, encoding='utf-8-sig', nrows=sample_size)
        else:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
    else:
        # Original TXT file: no header, use specified delimiter
        if sample_size:
            df = pd.read_csv(filepath, sep=delimiter, encoding=encoding,
                            names=column_names, nrows=sample_size, header=None)
        else:
            df = pd.read_csv(filepath, sep=delimiter, encoding=encoding,
                            names=column_names, header=None)

    # Transform data based on source
    if data_source == 'B008':
        # B008: Simple rename (handle both CSV and TXT column names)
        df = df.rename(columns={
            # TXT format (한글만, 괄호 없음)
            '기준년월': 'STD_YM',
            'X좌표': 'X_COORD',
            'Y좌표': 'Y_COORD',
            '성별코드': 'GNDR_CD',
            '연령대구분코드': 'AGE_GR_CD',  # TXT 파일
            '요일코드': 'WKDY_CD',
            '시간대코드': 'TMST_CD',
            '유동인구수': 'FLOW_POP',
            '자치구': 'SIGUNGU',
            # CSV format (괄호 포함)
            '기준년월(STD_YM)': 'STD_YM',
            'X좌표(X_COORD)': 'X_COORD',
            'Y좌표(Y_COORD)': 'Y_COORD',
            '성별코드(GNDR_CD)': 'GNDR_CD',
            '연령대코드(AGE_GR_SCTN_CD)': 'AGE_GR_CD',  # CSV 샘플 파일
            '요일코드(WKDY_CD)': 'WKDY_CD',
            '시간대코드(TMST_CD)': 'TMST_CD',
            '유동인구수(FLOW_POP_CNT)': 'FLOW_POP',
            '자치구(SIGUNGU)': 'SIGUNGU'
        })
    else:
        # B009: Wide to long transformation
        df = transform_b009_to_long_format(df)

    return df.dropna(subset=['X_COORD', 'Y_COORD', 'FLOW_POP'])


def calculate_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points"""
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)


def spatial_join_by_distance(market_df, flow_df, buffer_distance=BUFFER_DISTANCE):
    """
    Join flow population data to markets within buffer distance
    Simple implementation using distance calculation
    """
    results = []

    for _, market in market_df.iterrows():
        # Calculate distance from market to all flow points
        distances = calculate_distance(
            market['X'], market['Y'],
            flow_df['X_COORD'].values, flow_df['Y_COORD'].values
        )

        # Filter flow points within buffer distance
        mask = distances <= buffer_distance
        matched_flow = flow_df[mask].copy()

        if len(matched_flow) > 0:
            # Add market information to flow data
            matched_flow['market_name'] = market['market_name']
            matched_flow['district'] = market['district']
            results.append(matched_flow)

    if results:
        return pd.concat(results, ignore_index=True)
    else:
        return pd.DataFrame()


def aggregate_by_market(joined_df):
    """Group flow data by market"""
    market_groups = {}

    for market_name in joined_df['market_name'].unique():
        market_groups[market_name] = joined_df[
            joined_df['market_name'] == market_name
        ].copy()

    return market_groups