"""
Main script for traditional market applied aggregation analysis
Calculates three metrics: MZ ratio, night activity, monthly growth rate
"""
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

from config import (
    OUTPUT_DIR, SAMPLE_DATA_DIR,
    EXPORT_METADATA, AGGREGATION_FORMULAS, SPATIAL_METADATA,
    USE_SAMPLE, DATA_SOURCE, SAMPLE_ROWS,
    FULL_DATA_DIR, FILES_PER_BATCH, RESUME_FROM_CHECKPOINT,
    COLUMN_DESCRIPTIONS, OUTPUT_COLUMN_DESCRIPTIONS
)
try:
    # Use optimized version for full data
    from spatial_analysis_optimized import (
        load_market_data as load_market_data_opt,
        load_and_process_multiple_files,
        aggregate_by_market as aggregate_by_market_opt
    )
    OPTIMIZED_AVAILABLE = True
except ImportError:
    OPTIMIZED_AVAILABLE = False

# Always import sample data functions
from spatial_analysis import (
    load_market_data,
    load_flow_data,
    spatial_join_by_distance,
    aggregate_by_market
)

from aggregation import aggregate_all_markets


def create_export_readme(data_source, timestamp, output_dir, result_df, flow_record_count):
    """
    Create README.txt for export application (반출심사서 작성용)
    """
    metadata = EXPORT_METADATA[data_source]

    # Get column descriptions for the data source
    col_desc = COLUMN_DESCRIPTIONS[data_source]

    readme_content = f"""==========================================
서울시 전통시장 MZ세대 유동인구 응용집계 결과
==========================================

생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[1] 원본 데이터 정보
--------------------
데이터명: {metadata['data_name']}
파일 경로: {metadata['file_path']}
파일 형식: {metadata['file_format']}
분석 기간: {metadata['period']}
제공 기관: {metadata['provider']}
좌표 체계: {metadata['coordinate_system']}

[2] 원본 데이터 컬럼 설명
--------------------
"""

    for col_name, col_desc_text in col_desc.items():
        readme_content += f"  - {col_name}: {col_desc_text}\n"

    readme_content += f"""
[3] 공간 분석 정보
--------------------
전통시장 데이터: {SPATIAL_METADATA['market_data']}
버퍼 거리: {SPATIAL_METADATA['buffer_distance']}
공간 단위: {SPATIAL_METADATA['spatial_unit']}
집계 과정: {SPATIAL_METADATA['aggregation_level']}

[4] 응용집계 방법 (비가역 변환)
--------------------
"""

    for key, info in AGGREGATION_FORMULAS.items():
        readme_content += f"""
{info['name']}:
  - 계산식: {info['formula']}
  - 단위: {info['unit']}
  - 유형: {info['type']}
  - 비가역성: {'원본 데이터 복원 불가능' if info['irreversible'] else '복원 가능'}
"""

    readme_content += f"""
[5] 출력 파일 컬럼 설명
--------------------
"""

    for col_name, col_desc_text in OUTPUT_COLUMN_DESCRIPTIONS.items():
        readme_content += f"  - {col_name}: {col_desc_text}\n"

    readme_content += f"""
[6] 데이터 처리 결과
--------------------
원본 레코드 수: {flow_record_count:,}건 (50m 그리드 유동인구)
집계 결과: {len(result_df)}개 전통시장
공간 단위 변환: 50m 그리드 → 500m 버퍼 → 시장별

[7] 비가역성 증명
--------------------
- 개별 50m 그리드의 유동인구 수치는 복원 불가능
- 비율, 증감율, CAGR로 변환되어 원본 절대값 추정 불가
- 공간 단위가 "블록"보다 큰 "전통시장별" 집계
- 빅데이터 캠퍼스 반출 정책상 "응용집계"에 해당

[8] 반출 유형
--------------------
반출 유형: 응용집계 (Applied Aggregation)
반출 근거: 빅데이터 캠퍼스 반출정책 p.3 "응용집계" 정의
  - 비율, 증감율 등 역변환 불가능한 통계 처리
  - 블록보다 큰 공간단위로 집계

[9] 출처 표기
--------------------
출처: 서울시 빅데이터 캠퍼스, {metadata['data_name']} ({metadata['period']})

==========================================
이 README 파일은 반출심사서 작성을 위한 참고자료입니다.
==========================================
"""

    readme_file = output_dir / f"README_{data_source}_{timestamp}.txt"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    return readme_file


def main():
    """Execute aggregation analysis"""

    print("="*80)
    print("Traditional Market Applied Aggregation Analysis")
    print("="*80)

    start_time = datetime.now()
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Load configuration from config.py
    use_sample = USE_SAMPLE
    sample_size = SAMPLE_ROWS if use_sample else None
    data_source = DATA_SOURCE
    full_data_dir = FULL_DATA_DIR
    files_per_batch = FILES_PER_BATCH
    resume_from_checkpoint = RESUME_FROM_CHECKPOINT

    # Validate configuration
    from config import MARKET_COORDS_FILE, SAMPLE_DATA_DIR
    if not MARKET_COORDS_FILE.exists():
        print(f"Error: Market coordinates file not found: {MARKET_COORDS_FILE}")
        print("Please check MARKET_COORDS_FILE path in config.py")
        return 1

    if use_sample:
        if data_source == 'B008':
            sample_file = SAMPLE_DATA_DIR / "SKT 월별 요일별 유동인구.csv"
        else:  # B009
            sample_file = SAMPLE_DATA_DIR / "KT 월별 시간대별 성연령대별 유동인구.csv"

        if not sample_file.exists():
            print(f"Error: Sample data file not found: {sample_file}")
            print("Please check SAMPLE_DATA_DIR path in config.py")
            return 1
    else:
        if not full_data_dir:
            print("Error: FULL_DATA_DIR not set. Please configure it in config.py for full data analysis")
            return 1
        if not full_data_dir.exists():
            print(f"Error: Full data directory not found: {full_data_dir}")
            return 1

    print(f"Mode: {'Sample data' if use_sample else 'Full data'}")
    print(f"Data source: {data_source}")
    if use_sample:
        print(f"Sample rows: {sample_size:,}")
    if not use_sample and OPTIMIZED_AVAILABLE:
        print(f"Batch size: {files_per_batch} files per batch")
        print(f"Checkpoint/Resume: {'Enabled' if resume_from_checkpoint else 'Disabled (fresh start)'}")

    try:
        # Step 1: Load market coordinate data
        print("\n[1/5] Loading traditional market data...")
        market_df = load_market_data()
        print(f"Loaded {len(market_df)} markets")

        # Step 2-4: Load and process flow population data
        print("\n[2/5] Loading and processing flow population data...")
        if use_sample:
            flow_data_path = SAMPLE_DATA_DIR / "SKT 월별 요일별 유동인구.csv"
        else:
            if not full_data_dir:
                print("Error: Please set full_data_dir for full data analysis")
                return 1

        # Choose processing method based on mode
        if use_sample or not OPTIMIZED_AVAILABLE:
            # Original method: load all data at once (for sample data)
            from spatial_analysis import load_flow_data, spatial_join_by_distance

            if use_sample:
                if data_source == 'B008':
                    flow_data_path = SAMPLE_DATA_DIR / "SKT 월별 요일별 유동인구.csv"
                else:  # B009
                    flow_data_path = SAMPLE_DATA_DIR / "KT 월별 시간대별 성연령대별 유동인구.csv"

            flow_df = load_flow_data(flow_data_path, sample_size=sample_size, data_source=data_source)
            print(f"Loaded {len(flow_df):,} flow records")

            print("\n[3/5] Performing spatial join...")
            joined_df = spatial_join_by_distance(market_df, flow_df)

            if len(joined_df) == 0:
                print("Error: No matches found in spatial join")
                if data_source == 'B009':
                    print("Note: B009 data uses different coordinate system (EPSG:5186)")
                    print("      Market data uses EPSG:5179 (UTMK)")
                    print("      Coordinate transformation is required for accurate matching")
                    print("      This is a known limitation with mixed coordinate systems")
                return 1

            print(f"Matched {len(joined_df):,} records to {joined_df['market_name'].nunique()} markets")

            print("\n[4/5] Grouping data by market...")
            market_data = aggregate_by_market(joined_df)
            print(f"Grouped data for {len(market_data)} markets")

            flow_record_count = len(flow_df)

        else:
            # Optimized method: file-based batch processing (for full data)
            print("Using file-based batch processing with partial results...")

            # Use optimized market data loader
            market_df = load_market_data_opt()

            print("\n[3/5] Processing TXT files in batches...")
            print("[4/5] Saving partial results...")

            result_df = load_and_process_multiple_files(
                data_dir=full_data_dir,
                market_df=market_df,
                data_source=data_source,
                files_per_batch=files_per_batch,
                resume=resume_from_checkpoint
            )

            if len(result_df) == 0:
                print("Error: No results generated")
                return 1

            print(f"\nFinal results: {len(result_df)} markets")

            # For full data processing, aggregation is already done
            # Save results directly
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = OUTPUT_DIR / f"market_aggregation_{data_source}_{timestamp}.csv"
            result_df.to_csv(output_file, index=False, encoding='utf-8-sig')

            # Create README
            readme_file = create_export_readme(
                data_source=data_source,
                timestamp=timestamp,
                output_dir=OUTPUT_DIR,
                result_df=result_df,
                flow_record_count=0  # Unknown for file-based processing
            )

            # Print summary
            end_time = datetime.now()
            elapsed = end_time - start_time

            print("\n" + "="*80)
            print("Results Summary")
            print("="*80)
            print(f"Total markets analyzed: {len(result_df)}")
            print(f"\nMZ ratio statistics:")
            print(f"  Mean: {result_df['mz_ratio'].mean():.2f}%")
            print(f"  Min: {result_df['mz_ratio'].min():.2f}%")
            print(f"  Max: {result_df['mz_ratio'].max():.2f}%")

            print(f"\nNight activity statistics:")
            print(f"  Mean: {result_df['night_activity'].mean():.2f}%")
            print(f"  Min: {result_df['night_activity'].min():.2f}%")
            print(f"  Max: {result_df['night_activity'].max():.2f}%")

            print(f"\nWeekend activity statistics:")
            print(f"  Mean: {result_df['weekend_activity'].mean():.2f}%")
            print(f"  Min: {result_df['weekend_activity'].min():.2f}%")
            print(f"  Max: {result_df['weekend_activity'].max():.2f}%")

            print(f"\nMZ weekend activity statistics:")
            print(f"  Mean: {result_df['mz_weekend_activity'].mean():.2f}%")
            print(f"  Min: {result_df['mz_weekend_activity'].min():.2f}%")
            print(f"  Max: {result_df['mz_weekend_activity'].max():.2f}%")

            print(f"\nMonthly growth rate statistics:")
            print(f"  Mean: {result_df['monthly_growth_rate'].mean():.2f}%")
            print(f"  Min: {result_df['monthly_growth_rate'].min():.2f}%")
            print(f"  Max: {result_df['monthly_growth_rate'].max():.2f}%")

            print(f"\nTop 5 markets by MZ ratio:")
            top5 = result_df.nlargest(5, 'mz_ratio')[['market_name', 'district', 'mz_ratio']]
            print(top5.to_string(index=False))

            print("\n" + "="*80)
            print("Analysis completed")
            print("="*80)
            print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Duration: {elapsed}")
            print(f"\nOutput files:")
            print(f"  - Result CSV: {output_file}")
            print(f"  - README (for export): {readme_file}")
            print(f"\nData source: {EXPORT_METADATA[data_source]['data_name']}")

            print("\nCheckpoint management:")
            print("  - Checkpoints saved to: output/checkpoints/")
            print("  - Partial results saved to: output/partial_results/")
            print("  - To resume interrupted processing: Set resume_from_checkpoint=True")
            print("  - To start fresh: Set resume_from_checkpoint=False")
            print(f"  - Batch interval: Every {files_per_batch} files")

            print("="*80)
            return 0

        # Step 5: Calculate applied aggregations
        print("\n[5/5] Calculating applied aggregations...")
        print("  - MZ ratio: (20-34 age population / total) * 100")
        print("  - Night activity: (night avg / daytime avg - 1) * 100")
        print("  - Monthly growth rate: CAGR")

        result_df = aggregate_all_markets(market_data)

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Result CSV file with data source in filename
        output_file = OUTPUT_DIR / f"market_aggregation_{data_source}_{timestamp}.csv"
        result_df.to_csv(output_file, index=False, encoding='utf-8-sig')

        # Create README.txt for export application
        readme_file = create_export_readme(
            data_source=data_source,
            timestamp=timestamp,
            output_dir=OUTPUT_DIR,
            result_df=result_df,
            flow_record_count=len(flow_df)
        )

        # Summary statistics
        print("\n" + "="*80)
        print("Results Summary")
        print("="*80)
        print(f"Total markets analyzed: {len(result_df)}")
        print(f"\nMZ ratio statistics:")
        print(f"  Mean: {result_df['mz_ratio'].mean():.2f}%")
        print(f"  Min: {result_df['mz_ratio'].min():.2f}%")
        print(f"  Max: {result_df['mz_ratio'].max():.2f}%")

        print(f"\nNight activity statistics:")
        print(f"  Mean: {result_df['night_activity'].mean():.2f}%")
        print(f"  Min: {result_df['night_activity'].min():.2f}%")
        print(f"  Max: {result_df['night_activity'].max():.2f}%")

        print(f"\nMZ night activity statistics:")
        print(f"  Mean: {result_df['mz_night_activity'].mean():.2f}%")
        print(f"  Min: {result_df['mz_night_activity'].min():.2f}%")
        print(f"  Max: {result_df['mz_night_activity'].max():.2f}%")

        print(f"\nWeekend activity statistics:")
        print(f"  Mean: {result_df['weekend_activity'].mean():.2f}%")
        print(f"  Min: {result_df['weekend_activity'].min():.2f}%")
        print(f"  Max: {result_df['weekend_activity'].max():.2f}%")

        print(f"\nMZ weekend activity statistics:")
        print(f"  Mean: {result_df['mz_weekend_activity'].mean():.2f}%")
        print(f"  Min: {result_df['mz_weekend_activity'].min():.2f}%")
        print(f"  Max: {result_df['mz_weekend_activity'].max():.2f}%")

        print(f"\nMonthly growth rate statistics:")
        print(f"  Mean: {result_df['monthly_growth_rate'].mean():.2f}%")
        print(f"  Min: {result_df['monthly_growth_rate'].min():.2f}%")
        print(f"  Max: {result_df['monthly_growth_rate'].max():.2f}%")

        print(f"\nTop 5 markets by MZ ratio:")
        top5 = result_df.nlargest(5, 'mz_ratio')[['market_name', 'district', 'mz_ratio']]
        print(top5.to_string(index=False))

        # Completion
        end_time = datetime.now()
        elapsed = end_time - start_time

        print("\n" + "="*80)
        print("Analysis completed")
        print("="*80)
        print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {elapsed}")
        print(f"\nOutput files:")
        print(f"  - Result CSV: {output_file}")
        print(f"  - README (for export): {readme_file}")
        print(f"\nData source: {EXPORT_METADATA[data_source]['data_name']}")

        if not use_sample:
            print("\nCheckpoint management:")
            print("  - Checkpoints saved to: output/checkpoints/")
            print("  - To resume interrupted processing: Set resume_from_checkpoint=True")
            print("  - To start fresh (ignore checkpoints): Set resume_from_checkpoint=False")
            print("  - Checkpoint interval: Every 50 chunks")
            print("  - Note: Checkpoints auto-deleted after successful completion")

        print("="*80)

        return 0

    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)