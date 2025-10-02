"""
Memory-efficient spatial analysis with chunk-based processing
Includes checkpoint/resume functionality
"""
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime

from config import BUFFER_DISTANCE, MARKET_COORDS_FILE
from config import B008_DELIMITER, B008_ENCODING, B008_COLUMN_NAMES
from config import B009_DELIMITER, B009_ENCODING, B009_COLUMN_NAMES_WLK
from config import CHECKPOINT_DIR, PARTIAL_RESULTS_DIR
from config import MZ_AGE_CODES, MERGE_ONLY
from aggregation import aggregate_all_markets


def convert_epsg5186_to_epsg5179(x_5186, y_5186):
    """
    Convert coordinates from EPSG:5186 (GRS80 TM Central) to EPSG:5179 (UTMK)

    Simple approximation using known transformation parameters:
    - EPSG:5186: False Easting=200000, False Northing=600000, Central Meridian=127
    - EPSG:5179: False Easting=1000000, False Northing=2000000, Central Meridian=127.5

    Both use GRS80 ellipsoid and Transverse Mercator projection.
    This approximation is accurate enough for 500m buffer analysis.

    Parameters:
    -----------
    x_5186, y_5186 : float or array-like
        Coordinates in EPSG:5186

    Returns:
    --------
    tuple
        (x_5179, y_5179) coordinates in EPSG:5179
    """
    # Approximate conversion (tested with Seoul area coordinates)
    # Based on the relationship: UTMK = GRS80_TM + offset
    x_5179 = x_5186 + 755000  # Approximately 755km offset in X
    y_5179 = y_5186 + 1390000  # Approximately 1390km offset in Y

    return x_5179, y_5179


def transform_b009_to_long_format(df):
    """
    Transform B009 wide format to long format for aggregation

    B009 structure: 셀id, x좌표, y좌표, 요일, 시간대, 남자00-04세, ..., 여자70세이상, 합계, 행정동코드, 기준년월
    Output: X_COORD, Y_COORD, DAY_CD, TMST_CD, AGE_GR_CD, GNDR_CD, FLOW_POP, STD_YM
    """
    # Age group mapping (B009 → B008 format)
    # TXT format uses: 00-04세, CSV format uses: 00~04세 or (M00)
    age_mapping = {
        '00-04': 4, '05-09': 9, '10-14': 1014, '15-19': 1519,
        '20-24': 2024, '25-29': 2529, '30-34': 3034,
        '35-39': 3539, '40-44': 4044, '45-49': 4549,
        '50-54': 5054, '55-59': 5559, '60-64': 6064,
        '65-69': 6569, '70': 70  # 70세이상 or 70세이상
    }

    # Rename base columns (handle both TXT and CSV formats)
    df_transformed = df.rename(columns={
        # TXT format
        'x좌표': 'X_COORD',
        'y좌표': 'Y_COORD',
        '요일코드': 'DAY_CD',
        '시간대': 'TMST_CD',
        '기준년월': 'STD_YM',
        # CSV format (with parentheses)
        'x좌표(X_COORD)': 'X_COORD',
        'y좌표(Y_COORD)': 'Y_COORD',
        '요일(YOIL)': 'DAY_CD',
        '시간대(TIMEZN_CD)': 'TMST_CD',
        '기준년월(ETL_YM)': 'STD_YM'
    })

    # Convert B009 coordinates (EPSG:5186) to EPSG:5179 (UTMK) to match market data
    df_transformed['X_COORD'], df_transformed['Y_COORD'] = convert_epsg5186_to_epsg5179(
        df_transformed['X_COORD'].values,
        df_transformed['Y_COORD'].values
    )

    # Melt age/gender columns
    records = []

    # Note: Using iterrows() for readability with wide format transformation
    # Performance impact is acceptable as B009 data is pre-aggregated (fewer rows)
    for idx, row in df_transformed.iterrows():
        for gender in ['남자', '여자']:
            gndr_cd = 1 if gender == '남자' else 2
            gender_csv_prefix = 'M' if gender == '남자' else 'F'

            for age_str, age_code in age_mapping.items():
                # Try multiple column naming conventions
                possible_names = [
                    f'{gender}{age_str}세',  # TXT: 남자00-04세
                    f'{gender}{age_str.replace("-", "~")}세({gender_csv_prefix}{age_str[:2]})',  # CSV: 남자00~04세(M00)
                    f'{gender}{age_str[:2]}세이상',  # TXT: 남자70세이상 (only for 70)
                    f'{gender}70세이상({gender_csv_prefix}70)',  # CSV: 남자70세이상(M70)
                ]

                flow_pop = None
                for col_name in possible_names:
                    if col_name in df_transformed.columns:
                        flow_pop = row[col_name]
                        break

                # Skip zero or missing values
                if flow_pop is not None and pd.notna(flow_pop) and flow_pop > 0:
                    records.append({
                        'X_COORD': row['X_COORD'],
                        'Y_COORD': row['Y_COORD'],
                        'DAY_CD': row['DAY_CD'],
                        'TMST_CD': row['TMST_CD'],
                        'STD_YM': row['STD_YM'],
                        'AGE_GR_CD': age_code,
                        'GNDR_CD': gndr_cd,
                        'FLOW_POP': flow_pop
                    })

    return pd.DataFrame(records)


def load_market_data():
    """Load traditional market coordinate data"""
    df = pd.read_excel(MARKET_COORDS_FILE)

    market_df = pd.DataFrame({
        'market_id': df.iloc[:, 0],
        'district': df.iloc[:, 1],
        'market_name': df.iloc[:, 2],
        'X': df['X'],
        'Y': df['Y']
    })

    return market_df.dropna(subset=['X', 'Y', 'district', 'market_name'])


def calculate_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points"""
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)


def get_market_bounding_boxes(market_df, buffer_distance=BUFFER_DISTANCE):
    """
    Calculate bounding box for each market (for spatial filtering)
    """
    market_df = market_df.copy()
    market_df['x_min'] = market_df['X'] - buffer_distance
    market_df['x_max'] = market_df['X'] + buffer_distance
    market_df['y_min'] = market_df['Y'] - buffer_distance
    market_df['y_max'] = market_df['Y'] + buffer_distance

    return market_df


def process_chunk_spatial_join(chunk, market_df, buffer_distance=BUFFER_DISTANCE):
    """
    Process one chunk of flow data with spatial join
    Memory-efficient version
    """
    results = []

    # Quick spatial filter using bounding box
    for _, market in market_df.iterrows():
        # Filter by bounding box first (fast)
        mask = (
            (chunk['X_COORD'] >= market['x_min']) &
            (chunk['X_COORD'] <= market['x_max']) &
            (chunk['Y_COORD'] >= market['y_min']) &
            (chunk['Y_COORD'] <= market['y_max'])
        )

        candidate_points = chunk[mask]

        if len(candidate_points) == 0:
            continue

        # Precise distance calculation (only for candidates)
        distances = calculate_distance(
            market['X'], market['Y'],
            candidate_points['X_COORD'].values,
            candidate_points['Y_COORD'].values
        )

        # Filter by exact distance
        within_buffer = distances <= buffer_distance
        matched = candidate_points[within_buffer].copy()

        if len(matched) > 0:
            matched['market_name'] = market['market_name']
            matched['district'] = market['district']
            results.append(matched)

    if results:
        return pd.concat(results, ignore_index=True)
    else:
        return pd.DataFrame()


def save_checkpoint(checkpoint_data, checkpoint_file):
    """Save checkpoint to disk"""
    with open(checkpoint_file, 'wb') as f:
        pickle.dump(checkpoint_data, f)
    print(f"  [Checkpoint saved: {checkpoint_file.name}]")


def load_checkpoint(checkpoint_file):
    """Load checkpoint from disk"""
    if checkpoint_file.exists():
        with open(checkpoint_file, 'rb') as f:
            return pickle.load(f)
    return None


def aggregate_by_market(market_data_dict):
    """
    Convert dict of market DataFrames to standard format
    (compatibility function)
    """
    return market_data_dict


def get_checkpoint_filename_batch(data_source, data_dir):
    """Generate checkpoint filename for batch processing"""
    dir_hash = hash(str(data_dir))
    timestamp = datetime.now().strftime('%Y%m%d')
    return CHECKPOINT_DIR / f"checkpoint_batch_{data_source}_{timestamp}_{dir_hash}.pkl"


def load_and_process_multiple_files(
    data_dir,
    market_df,
    data_source='B008',
    files_per_batch=10,
    resume=True
):
    """
    Process multiple TXT files in batches with partial result saving

    Parameters:
    -----------
    data_dir : str or Path
        Directory containing TXT files
    market_df : DataFrame
        Market data with bounding boxes
    data_source : str
        'B008' or 'B009'
    files_per_batch : int
        Number of files to process in one batch
    resume : bool
        Resume from checkpoint if available

    Returns:
    --------
    DataFrame
        Final aggregated results by market
    """
    data_dir = Path(data_dir)

    # Get all TXT files
    txt_files = sorted(data_dir.glob("*.txt"))
    total_files = len(txt_files)

    # MERGE_ONLY 모드: TXT 처리 건너뛰고 PKL 병합만 수행
    if MERGE_ONLY:
        print("=" * 80)
        print("MERGE_ONLY mode enabled: Skipping TXT processing")
        print("=" * 80)
        # PKL 병합으로 바로 이동 (Line 462 이후)
        txt_files = []
        total_files = 0
    elif total_files == 0:
        raise ValueError(f"No TXT files found in {data_dir}")
    else:
        print(f"Found {total_files} TXT files in {data_dir.name}")

    # Checkpoint file
    checkpoint_file = get_checkpoint_filename_batch(data_source, data_dir)

    # Load checkpoint if exists
    processed_files = []
    start_batch = 0

    if resume and checkpoint_file.exists():
        print(f"Found checkpoint: {checkpoint_file.name}")
        checkpoint = load_checkpoint(checkpoint_file)
        if checkpoint:
            processed_files = checkpoint['processed_files']
            start_batch = checkpoint['last_batch_num'] + 1
            print(f"Resuming from batch {start_batch} ({len(processed_files)}/{total_files} files already processed)")

    # Prepare market bounding boxes
    market_df = get_market_bounding_boxes(market_df, BUFFER_DISTANCE)

    # Determine delimiter and column names
    if data_source == 'B008':
        delimiter = B008_DELIMITER
        encoding = B008_ENCODING
        column_names = B008_COLUMN_NAMES
    else:
        delimiter = B009_DELIMITER
        encoding = B009_ENCODING
        column_names = B009_COLUMN_NAMES_WLK

    # MERGE_ONLY 모드가 아닐 때만 처리
    if not MERGE_ONLY:
        print(f"Processing in batches of {files_per_batch} files...")
        print(f"Partial results will be saved to: {PARTIAL_RESULTS_DIR}/")

    # Process files in batches
    batch_num = start_batch

    try:
        for i in range(start_batch * files_per_batch, total_files, files_per_batch):
            batch_files = txt_files[i:i+files_per_batch]
            batch_num = i // files_per_batch

            print(f"\n[Batch {batch_num + 1}] Processing files {i+1}-{min(i+files_per_batch, total_files)}/{total_files}")

            # Initialize market aggregated data for this batch
            market_aggregated_data = {name: [] for name in market_df['market_name']}
            total_matched = 0

            # Process each file in the batch
            for file_idx, file_path in enumerate(batch_files, 1):
                print(f"  [{file_idx}/{len(batch_files)}] {file_path.name}...", end=' ')

                # Load file
                try:
                    df = pd.read_csv(
                        file_path,
                        sep=delimiter,
                        encoding=encoding,
                        names=column_names,
                        header=None,
                        dtype=str,  # 모든 컬럼을 문자열로 읽고 나중에 숫자로 변환
                        low_memory=False
                    )
                except Exception as e:
                    print(f"Error reading {file_path.name}: {str(e)}, skipping")
                    continue

                # Transform data based on source
                if data_source == 'B008':
                    # B008: Simple rename
                    df = df.rename(columns={
                        '기준년월': 'STD_YM',
                        'X좌표': 'X_COORD',
                        'Y좌표': 'Y_COORD',
                        '성별코드': 'GNDR_CD',
                        '연령대구분코드': 'AGE_GR_CD',
                        '요일코드': 'DAY_CD',
                        '시간대코드': 'TMST_CD',
                        '유동인구수': 'FLOW_POP',
                        '자치구': 'SIGUNGU'
                    })

                    # Convert to numeric (문자열 → 숫자 변환)
                    df['X_COORD'] = pd.to_numeric(df['X_COORD'], errors='coerce')
                    df['Y_COORD'] = pd.to_numeric(df['Y_COORD'], errors='coerce')
                    df['FLOW_POP'] = pd.to_numeric(df['FLOW_POP'], errors='coerce')
                    df['AGE_GR_CD'] = pd.to_numeric(df['AGE_GR_CD'], errors='coerce')
                    df['TMST_CD'] = pd.to_numeric(df['TMST_CD'], errors='coerce')

                else:
                    # B009: Wide to long transformation
                    df = transform_b009_to_long_format(df)

                # Drop missing values
                df = df.dropna(subset=['X_COORD', 'Y_COORD', 'FLOW_POP'])

                if len(df) == 0:
                    print("no valid data, skipping")
                    continue

                # Spatial join
                matched = process_chunk_spatial_join(df, market_df, BUFFER_DISTANCE)

                # Remove duplicate records (전체 행 기준)
                if len(matched) > 0:
                    try:
                        original_count = len(matched)
                        matched = matched.drop_duplicates(keep='first')
                        removed = original_count - len(matched)
                        if removed > 0:
                            print(f"matched: {len(matched):,} (중복 제거: {removed:,}건)")
                        else:
                            print(f"matched: {len(matched):,}")
                    except Exception as e:
                        # 중복 제거 오류 시 그냥 진행 (비율 계산에는 영향 없음)
                        print(f"matched: {len(matched):,} (중복 제거 오류, 무시하고 진행)")

                # Aggregate by market
                if len(matched) > 0:
                    for market_name in matched['market_name'].unique():
                        market_data = matched[matched['market_name'] == market_name]
                        market_aggregated_data[market_name].append(market_data)

                    total_matched += len(matched)

                # Update processed files list
                processed_files.append(file_path.name)

            # Combine chunks for each market in this batch (batch = 1 file)
            batch_market_data = {}
            for market_name, chunks in market_aggregated_data.items():
                if chunks:
                    batch_market_data[market_name] = pd.concat(chunks, ignore_index=True)

            # Save file-specific RAW data (파일 1개 = 배치 1개)
            if batch_market_data:
                try:
                    # Use original filename for tracking
                    file_name = batch_files[0].stem  # Remove .txt extension

                    # ⚠️ WARNING: PKL saving disabled for speed
                    # This means:
                    # 1. Memory will accumulate across all files (50GB+ needed)
                    # 2. No recovery possible if interrupted
                    # 3. Final merge step will be impossible without sufficient RAM
                    # partial_data_file = PARTIAL_RESULTS_DIR / f"{file_name}_raw_data.pkl"
                    # with open(partial_data_file, 'wb') as f:
                    #     pickle.dump(batch_market_data, f)
                    # print(f"  [Saved] {file_name}_raw_data.pkl")

                    # Also save aggregated result for this file
                    batch_result_df = aggregate_all_markets(batch_market_data)
                    partial_result_file = PARTIAL_RESULTS_DIR / f"{file_name}_result.csv"
                    batch_result_df.to_csv(partial_result_file, index=False, encoding='utf-8-sig')
                    print(f"  [Saved] {file_name}_result.csv")
                except Exception as e:
                    print(f"  [Warning] Failed to save results: {str(e)}")

            print(f"  File completed: {batch_files[0].name}, {total_matched:,} matched records")

            # Save checkpoint
            checkpoint_data = {
                'processed_files': processed_files,
                'last_batch_num': batch_num,
                'total_files': total_files
            }
            save_checkpoint(checkpoint_data, checkpoint_file)

    except KeyboardInterrupt:
        print(f"\n[Interrupted] Saving checkpoint at batch {batch_num}...")
        checkpoint_data = {
            'processed_files': processed_files,
            'last_batch_num': batch_num,
            'total_files': total_files
        }
        save_checkpoint(checkpoint_data, checkpoint_file)
        print("Checkpoint saved. You can resume later with resume=True")
        raise

    except Exception as e:
        print(f"\n[Error] Saving checkpoint at batch {batch_num}...")
        checkpoint_data = {
            'processed_files': processed_files,
            'last_batch_num': batch_num,
            'total_files': total_files
        }
        save_checkpoint(checkpoint_data, checkpoint_file)
        raise

    # MERGE_ONLY 모드가 아닐 때만 출력
    if not MERGE_ONLY:
        print(f"\nAll files processed: {len(processed_files)}/{total_files}")

        # Delete checkpoint after successful completion
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            print(f"Checkpoint deleted (processing completed)")

    # Combine all file-specific RAW data and re-aggregate
    print("\n=== Combining all file results for final aggregation ===")
    partial_raw_files = sorted(PARTIAL_RESULTS_DIR.glob(f"*_raw_data.pkl"))

    if partial_raw_files:
        print(f"Found {len(partial_raw_files)} file results to combine")

        # Step 1: 모든 시장 이름 수집 (메모리 최소 사용)
        print("  Step 1: Collecting market names...")
        all_markets = set()
        for partial_file in partial_raw_files:
            try:
                with open(partial_file, 'rb') as f:
                    file_data = pickle.load(f)
                    all_markets.update(file_data.keys())
                    del file_data  # 즉시 메모리 해제
            except Exception as e:
                print(f"  [Warning] Failed to load {partial_file.name}: {str(e)}, skipping")
                continue

        import gc
        gc.collect()
        print(f"  Found {len(all_markets)} unique markets")

        # 시장이 없으면 빈 결과 반환
        if len(all_markets) == 0:
            print("  No markets found in PKL files")
            return pd.DataFrame()

        # Step 2: 시장별로 순차 처리 (메모리 안전)
        print("  Step 2: Processing markets sequentially...")
        final_results = []

        for idx, market_name in enumerate(sorted(all_markets), 1):
            print(f"  [{idx}/{len(all_markets)}] Processing {market_name}...")

            market_dfs = []

            # 해당 시장 데이터만 로드
            for partial_file in partial_raw_files:
                try:
                    with open(partial_file, 'rb') as f:
                        file_data = pickle.load(f)
                        if market_name in file_data:
                            market_dfs.append(file_data[market_name])
                        del file_data  # 즉시 메모리 해제
                except Exception as e:
                    print(f"    [Warning] Failed to load from {partial_file.name}: {str(e)}")
                    continue

            # 병합 및 집계
            if market_dfs:
                try:
                    combined_df = pd.concat(market_dfs, ignore_index=True)

                    # 개별 시장 집계
                    from aggregation import (
                        calculate_mz_ratio, calculate_night_activity,
                        calculate_mz_night_activity, calculate_weekend_activity,
                        calculate_mz_weekend_activity, calculate_monthly_growth_rate
                    )

                    result = {
                        'market_name': market_name,
                        'district': combined_df['district'].iloc[0] if len(combined_df) > 0 else None,
                        'mz_ratio': calculate_mz_ratio(combined_df),
                        'night_activity': calculate_night_activity(combined_df),
                        'mz_night_activity': calculate_mz_night_activity(combined_df),
                        'weekend_activity': calculate_weekend_activity(combined_df),
                        'mz_weekend_activity': calculate_mz_weekend_activity(combined_df),
                        'monthly_growth_rate': calculate_monthly_growth_rate(combined_df),
                        'total_records': len(combined_df),
                        'total_population': combined_df['FLOW_POP'].sum()
                    }

                    final_results.append(result)

                    # 메모리 해제
                    del combined_df
                except Exception as e:
                    print(f"    [Error] Failed to process {market_name}: {str(e)}")

            # 메모리 해제
            del market_dfs
            gc.collect()

        # DataFrame 생성
        final_df = pd.DataFrame(final_results)

        print(f"\n=== Final aggregation completed: {len(final_df)} markets ===")
        return final_df
    else:
        print("  No partial data found, returning empty result")
        return pd.DataFrame()
