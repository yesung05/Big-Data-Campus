"""
Configuration for traditional market applied aggregation analysis
"""
from pathlib import Path

# ============================================
# 사용자 설정 (여기를 수정하세요!)
# ============================================

# 1. 실행 모드
USE_SAMPLE = False  # True: 샘플 데이터 테스트, False: 원본 데이터 처리

# 2. 데이터 소스
DATA_SOURCE = 'B008'  # 'B008' (SKT, pipe) 또는 'B009' (KT, comma)
# B009 좌표계(EPSG:5186)는 자동으로 EPSG:5179로 변환됩니다

# 3. 샘플 모드 설정
SAMPLE_ROWS = 1000  # 샘플 데이터에서 읽을 행 수

# 4. 원본 데이터 경로 (USE_SAMPLE=False일 때 필수)
# 예시: FULL_DATA_DIR = Path("D:/빅데이터캠퍼스/008.../201601-201612")
FULL_DATA_DIR = Path("E:/B008/1. 요일별_유동인구/2016")  # TXT 파일들이 있는 폴더 경로

# 5. 배치 처리 설정
FILES_PER_BATCH = 1  # 파일 1개씩 처리하여 개별 결과 저장

# 6. 체크포인트/재개 설정
RESUME_FROM_CHECKPOINT = True  # True: 중단된 작업 이어서, False: 처음부터 다시

# 7. PKL 병합 전용 모드
MERGE_ONLY = False  # True: PKL 병합만 수행 (TXT 처리 건너뛰기), False: 정상 처리

# ============================================
# 시스템 설정 (일반적으로 수정 불필요)
# ============================================

# Project paths
# 옵션 1: 자동 경로 (추천) - 프로젝트 위치에 상관없이 작동
PROJECT_ROOT = Path(__file__).parent.parent

# 옵션 2: 수동 경로 - 특정 경로를 강제하고 싶을 때 주석 해제하고 수정
# PROJECT_ROOT = Path("C:/Users/asus/DMU/BigData_Campus")

MARKET_COORDS_FILE = PROJECT_ROOT / "서울시 전통시장 현황_좌표추가.xlsx"
SAMPLE_DATA_DIR = PROJECT_ROOT / "Sample_data"
OUTPUT_DIR = PROJECT_ROOT / "output_v4"
OUTPUT_DIR.mkdir(exist_ok=True)

# Spatial analysis settings
BUFFER_DISTANCE = 500  # meters
CRS_UTMK = "EPSG:5179"

# B008 file specifications (SKT data)
B008_DELIMITER = '|'  # pipe delimiter
B008_ENCODING = 'utf-8'
B008_COLUMN_NAMES = ['기준년월', 'X좌표', 'Y좌표', '성별코드', '연령대구분코드', '요일코드', '시간대코드', '유동인구수', '자치구']

# B009 file specifications (KT data)
B009_DELIMITER = ','  # comma delimiter
B009_ENCODING = 'utf-8'
# B009 has different structure - 38 columns for wlk file
B009_COLUMN_NAMES_WLK = ['셀ID', 'X좌표', 'Y좌표', '요일', '시간대'] + \
                        [f'남자{age}' for age in ['0004', '0509', '1014', '1519', '2024', '2529', '3034',
                                                  '3539', '4044', '4549', '5054', '5559', '6064', '6569', '70이상']] + \
                        [f'여자{age}' for age in ['0004', '0509', '1014', '1519', '2024', '2529', '3034',
                                                  '35-39세', '40-44세', '45-49세', '50-54세', '55-59세', '60-64세', '65-69세', '70세이상']] + \
                        ['합계', '행정동코드', '기준년월']

# Column descriptions for documentation
COLUMN_DESCRIPTIONS = {
    'B008': {
        '기준년월': '데이터 기준 년월 (YYYYMM)',
        'X좌표': 'UTMK 좌표계 X 좌표 (EPSG:5179)',
        'Y좌표': 'UTMK 좌표계 Y 좌표 (EPSG:5179)',
        '성별코드': '성별 (1: 남자, 2: 여자)',
        '연령대구분코드': '연령대 (예: 2024 = 20-24세, 3034 = 30-34세)',
        '요일코드': '요일 (1: 월요일 ~ 7: 일요일)',
        '시간대코드': '시간대 (0 ~ 23시)',
        '유동인구수': '해당 조건의 유동인구 수 (명)',
        '자치구': '서울시 자치구명'
    },
    'B009': {
        '셀id': '50m 격자 셀 ID',
        'x좌표': 'GRS80 TM 중부원점 X 좌표 (EPSG:5186)',
        'y좌표': 'GRS80 TM 중부원점 Y 좌표 (EPSG:5186)',
        '요일': '요일 (1: 월요일 ~ 7: 일요일)',
        '시간대': '시간대 (0 ~ 23시)',
        '남자/여자 연령대': '성별 + 연령대별 유동인구 수 (15개 연령대 × 2 성별 = 30개 컬럼)',
        '합계': '전체 유동인구 합계',
        '행정동코드': '행정동 코드',
        '기준년월': '데이터 기준 년월 (YYYYMM)'
    }
}

# Output CSV column descriptions
OUTPUT_COLUMN_DESCRIPTIONS = {
    'market_name': '전통시장 이름',
    'district': '소재 자치구',
    'mz_ratio': 'MZ세대(20-34세) 점유율 (%, 전체 대비 MZ세대 비율)',
    'night_activity': '전체 야간 활성도 (%, 주간 대비 야간 유동인구 증감율)',
    'mz_night_activity': 'MZ세대 야간 활성도 (%, MZ 주간 대비 MZ 야간 유동인구 증감율)',
    'weekend_activity': '주말 활성도 (%, 평일 대비 주말 유동인구 증감율)',
    'mz_weekend_activity': 'MZ세대 주말 활성도 (%, MZ 평일 대비 MZ 주말 유동인구 증감율)',
    'monthly_growth_rate': '월별 성장률 (%, CAGR - 복리 연평균 성장률)',
    'total_records': '매칭된 원본 레코드 수 (건)',
    'total_population': '총 유동인구 수 (명, 분석 기간 전체 합계)'
}

# Age group codes for MZ generation (20-34 years old)
MZ_AGE_CODES = [2024, 2529, 3034]

# Time codes for day/night analysis
DAYTIME_HOURS = list(range(10, 18))  # 10:00-17:59
NIGHT_HOURS = list(range(20, 24))    # 20:00-23:59

# Export metadata for 반출심사서 (Export Application Form)
EXPORT_METADATA = {
    'B008': {
        'data_name': 'B008 - 서울시 50m간격 월별 SKT 유동인구',
        'file_path': '2.빅데이터 캠퍼스 데이터 / 008.서울시 50m간격 월별 SKT 유동인구 / 2.파일데이터 / 1.원본 / 201601-201612',
        'file_format': 'TXT (파이프 구분자)',
        'period': '2016.01 ~ 2016.12',
        'provider': 'SKT',
        'coordinate_system': 'EPSG:5179 (UTMK)'
    },
    'B009': {
        'data_name': 'B009 - 서울시 50m간격 월별 KT 유동인구',
        'file_path': '2.빅데이터 캠퍼스 데이터 / 009.서울시 50m간격 월별 KT 유동인구 / 2.파일데이터 / 1.원본 / 201601-201801',
        'file_format': 'TXT (콤마 구분자)',
        'period': '2016.01 ~ 2018.01',
        'provider': 'KT',
        'coordinate_system': 'EPSG:5186 (GRS80 TM 중부원점)'
    }
}

# Aggregation formulas for export documentation
AGGREGATION_FORMULAS = {
    'MZ_ratio': {
        'name': 'MZ세대 점유율',
        'formula': '(20-34세 유동인구 합계 / 전체 유동인구 합계) × 100',
        'unit': '%',
        'type': '응용집계 (비율)',
        'irreversible': True
    },
    'night_activity': {
        'name': '전체 야간 활성도',
        'formula': '(야간(20-23시) 평균 / 주간(10-17시) 평균 - 1) × 100',
        'unit': '%',
        'type': '응용집계 (증감율)',
        'irreversible': True
    },
    'mz_night_activity': {
        'name': 'MZ세대 야간 활성도',
        'formula': '(MZ 야간 평균 / MZ 주간 평균 - 1) × 100',
        'unit': '%',
        'type': '응용집계 (증감율)',
        'irreversible': True
    },
    'weekend_activity': {
        'name': '주말 활성도',
        'formula': '(주말(토/일) 평균 / 평일(월~금) 평균 - 1) × 100',
        'unit': '%',
        'type': '응용집계 (증감율)',
        'irreversible': True
    },
    'mz_weekend_activity': {
        'name': 'MZ세대 주말 활성도',
        'formula': '(MZ 주말 평균 / MZ 평일 평균 - 1) × 100',
        'unit': '%',
        'type': '응용집계 (증감율)',
        'irreversible': True
    },
    'monthly_growth_rate': {
        'name': '월별 성장률',
        'formula': '((마지막월 / 첫월) ^ (1/개월수) - 1) × 100',
        'unit': '%',
        'type': '응용집계 (CAGR)',
        'irreversible': True
    }
}

# Spatial analysis metadata
SPATIAL_METADATA = {
    'market_data': '서울시 전통시장 현황 (433개 시장)',
    'buffer_distance': '500m (전통시장 중심점 기준)',
    'spatial_unit': '전통시장별 (블록보다 큰 공간단위)',
    'aggregation_level': '50m 그리드 → 500m 버퍼 → 시장별 집계'
}

# Checkpoint settings for resumable processing
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)
PARTIAL_RESULTS_DIR = OUTPUT_DIR / "partial_results"
PARTIAL_RESULTS_DIR.mkdir(exist_ok=True)