import streamlit as st
import pandas as pd
import requests
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import urllib3
import warnings
from urllib.parse import unquote
import numpy as np
from datetime import datetime

# SSL 경고 및 인증서 검증 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="주민대피시설 현황 대시보드",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# SERVICE_KEY 설정 (인코딩된 키 - 디코딩 필요)
SERVICE_KEY = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="

# 제목 및 설명
st.title("🏢 주민대피시설 현황 대시보드")
st.markdown("---")
st.markdown("**행정안전부 통계연보 - 지역별 주민대피시설 현황을 시각화한 대시보드입니다.**")

# API 에러 코드 매핑
ERROR_CODES = {
    "290": "인증키가 유효하지 않습니다. 인증키가 없는 경우 홈페이지에서 인증키를 신청하십시오.",
    "310": "해당하는 서비스를 찾을 수 없습니다. 요청인자 중 SERVICE를 확인하십시오.",
    "333": "요청위치 값의 타입이 유효하지 않습니다. 요청위치 값은 정수를 입력하세요.",
    "336": "데이터 요청은 한번에 최대 1,000건을 넘을 수 없습니다.",
    "337": "일별 트래픽 제한을 넘은 호출입니다. 오늘은 더이상 호출할 수 없습니다.",
    "500": "서버 오류입니다. 지속적으로 발생시 홈페이지로 문의(Q&A) 바랍니다.",
    "600": "데이터베이스 연결 오류입니다. 지속적으로 발생시 홈페이지로 문의(Q&A) 바랍니다.",
    "601": "SQL 문장 오류입니다. 지속적으로 발생시 홈페이지로 문의(Q&A) 바랍니다.",
    "0": "정상 처리되었습니다.",
    "300": "관리자에 의해 인증키 사용이 제한되었습니다.",
    "200": "해당하는 데이터가 없습니다."
}

# API 호출 함수
@st.cache_data(ttl=300)
def fetch_air_raid_shelter_data(service_key, year, page_no=1, num_of_rows=1000):
    """공공데이터 API에서 주민대피시설 데이터를 가져오는 함수"""
    
    # 인증키 디코딩 (URL 디코딩 적용)
    decoded_key = unquote(service_key)
    
    # HTTP 엔드포인트 사용 (API 명세에 따르면 SSL 없음)
    url = "http://apis.data.go.kr/1741000/AirRaidShelterRegion/getAirRaidShelterRegionList"
    
    # 파라미터 설정
    params = {
        'ServiceKey': decoded_key,
        'pageNo': page_no,
        'numOfRows': num_of_rows,
        'type': 'json',
        'bas_yy': year
    }
    
    try:
        # API 호출
        response = requests.get(url, params=params, verify=False, timeout=15)
        response.raise_for_status()
        
        # JSON 응답 파싱
        try:
            data = response.json()
        except:
            st.error("🚨 JSON 파싱 실패. 서버에서 XML이나 다른 형식을 반환했을 수 있습니다.")
            return None
        
        # 응답 구조 확인
        if 'response' in data:
            # 헤더 정보 확인 (에러 체크)
            if 'header' in data['response']:
                header = data['response']['header']
                result_code = header.get('resultCode', '')
                result_msg = header.get('resultMsg', '')
                
                # 에러 코드 처리
                if result_code != '00' and result_code != '0':
                    error_msg = ERROR_CODES.get(result_code, f"알 수 없는 오류 (코드: {result_code})")
                    st.error(f"🚨 API 오류 [{result_code}]: {error_msg}")
                    return None
                
                st.success(f"✅ API 호출 성공: {result_msg}")
            
            # 바디 데이터 추출
            if 'body' in data['response']:
                body = data['response']['body']
                
                # items 확인
                if 'items' in body and body['items']:
                    items = body['items']
                    
                    # dict인 경우 item 키로 접근
                    if isinstance(items, dict) and 'item' in items:
                        return items['item']
                    # list인 경우 그대로 반환
                    elif isinstance(items, list):
                        return items
                    else:
                        return []
                else:
                    st.warning("⚠️ 응답에 데이터가 없습니다.")
                    return []
        else:
            st.error("🚨 예상과 다른 응답 구조입니다.")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"🚨 API 호출 실패: {str(e)}")
        return None
    except Exception as e:
        st.error(f"🚨 예상치 못한 오류: {str(e)}")
        return None

# 최신 데이터 자동 탐지 함수
@st.cache_data(ttl=3600)
def find_latest_data():
    """최신 연도 데이터를 자동으로 탐지"""
    current_year = datetime.now().year
    
    # 현재 연도부터 2019년까지 역순으로 검색
    for year in range(current_year, 2018, -1):
        data = fetch_air_raid_shelter_data(SERVICE_KEY, year, 1, 1)
        if data and len(data) > 0:
            return year, data
    
    return None, None

# 데이터 전처리 함수
def preprocess_data(raw_data):
    """원시 데이터를 DataFrame으로 변환하고 전처리"""
    
    if not raw_data:
        return pd.DataFrame()
    
    # DataFrame 생성
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        return df
    
    # 수치형 컬럼 리스트
    numeric_columns = [
        'target_popl', 'accpt_rt', 'shelt_abl_popl_smry',
        'shelt_abl_popl_gov_shelts', 'shelt_abl_popl_pub_shelts',
        'gov_shelts_shelts', 'gov_shelts_area',
        'pub_shelts_shelts', 'pub_shelts_area'
    ]
    
    # 수치형 컬럼 변환
    for col in numeric_columns:
        if col in df.columns:
            # 콤마 제거 및 숫자형 변환
            df[col] = df[col].astype(str).str.replace(',', '').replace('', '0')
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 결측치 처리 (0으로 채우기)
    df = df.fillna(0)
    
    # '합계' 행 저장 후 제거
    total_row = df[df['regi'] == '합계'].copy() if 'regi' in df.columns else pd.DataFrame()
    df_filtered = df[df['regi'] != '합계'].copy() if 'regi' in df.columns else df.copy()
    
    return df_filtered, total_row

# 최신 데이터 로드
with st.spinner("🔍 최신 데이터를 탐지하는 중..."):
    latest_year, sample_data = find_latest_data()
    
    if latest_year is None:
        st.error("🚨 사용 가능한 데이터를 찾을 수 없습니다. 인증키나 API 상태를 확인해주세요.")
        st.stop()
    
    st.info(f"📅 최신 데이터 연도: **{latest_year}년**")

# 전체 데이터 로드
with st.spinner(f"📡 {latest_year}년 전체 데이터를 불러오는 중..."):
    raw_data = fetch_air_raid_shelter_data(SERVICE_KEY, latest_year)
    
    if raw_data is None:
        st.error("API 호출에 실패했습니다.")
        st.stop()
    
    df, total_df = preprocess_data(raw_data)
    
    if df.empty:
        st.warning(f"⚠️ {latest_year}년도 데이터가 비어있습니다.")
        st.stop()

# 사이드바 필터
st.sidebar.header("🔍 데이터 필터")

# 지역 선택
regions = ['전체'] + sorted(df['regi'].unique().tolist())
selected_regions = st.sidebar.multiselect(
    "🏙️ 지역 선택",
    options=regions,
    default=['전체'],
    help="분석할 지역을 선택하세요."
)

# 수용률 범위 슬라이더
if 'accpt_rt' in df.columns:
    min_rate = float(df['accpt_rt'].min())
    max_rate = float(df['accpt_rt'].max())
    
    rate_range = st.sidebar.slider(
        "📊 수용률 범위 (%)",
        min_value=min_rate,
        max_value=max_rate,
        value=(min_rate, max_rate),
        help="수용률 범위를 설정하세요."
    )

# 데이터 필터링
filtered_df = df.copy()

if '전체' not in selected_regions:
    filtered_df = filtered_df[filtered_df['regi'].isin(selected_regions)]

if 'accpt_rt' in filtered_df.columns:
    filtered_df = filtered_df[
        (filtered_df['accpt_rt'] >= rate_range[0]) & 
        (filtered_df['accpt_rt'] <= rate_range[1])
    ]

# 전국 통계 (합계 행 활용)
st.markdown("### 🇰🇷 전국 통계 현황")
if not total_df.empty:
    col1, col2, col3, col4 = st.columns(4)
    
    total_row = total_df.iloc[0]
    
    with col1:
        st.metric(
            label="👥 전국 대상인구",
            value=f"{total_row['target_popl']:,.0f}명",
            help="전국 주민대피시설 대상인구"
        )
    
    with col2:
        st.metric(
            label="📊 전국 평균 수용률",
            value=f"{total_row['accpt_rt']:.1f}%",
            help="전국 평균 대피시설 수용률"
        )
    
    with col3:
        st.metric(
            label="🏢 전국 총 시설 수",
            value=f"{total_row['pub_shelts_shelts']:,.0f}개소",
            help="전국 공공용 대피시설 수"
        )
    
    with col4:
        st.metric(
            label="📐 전국 총 시설 면적",
            value=f"{total_row['pub_shelts_area']:,.0f}㎡",
            help="전국 공공용 대피시설 면적"
        )

# 필터링된 지역 통계
st.markdown("---")
st.markdown("### 📊 선택 지역 통계")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📍 선택 지역 수",
        value=len(filtered_df),
        delta=f"{len(filtered_df) - len(df)} (필터 적용)"
    )

with col2:
    total_population = filtered_df['target_popl'].sum() if 'target_popl' in filtered_df.columns else 0
    st.metric(
        label="👥 대상 인구",
        value=f"{total_population:,}명"
    )

with col3:
    avg_rate = filtered_df['accpt_rt'].mean() if 'accpt_rt' in filtered_df.columns else 0
    st.metric(
        label="📊 평균 수용률",
        value=f"{avg_rate:.1f}%"
    )

with col4:
    total_facilities = filtered_df['pub_shelts_shelts'].sum() if 'pub_shelts_shelts' in filtered_df.columns else 0
    st.metric(
        label="🏢 총 시설 수",
        value=f"{total_facilities:,}개소"
    )

# 주요 인사이트
st.markdown("---")
st.markdown("### 💡 주요 인사이트")

if not filtered_df.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        # 수용률 최고/최저 지역
        max_rate_region = filtered_df.loc[filtered_df['accpt_rt'].idxmax()]
        min_rate_region = filtered_df.loc[filtered_df['accpt_rt'].idxmin()]
        
        st.info(f"""
        **🏆 수용률 최고 지역**  
        📍 {max_rate_region['regi']}: {max_rate_region['accpt_rt']:.1f}%
        
        **📉 수용률 최저 지역**  
        📍 {min_rate_region['regi']}: {min_rate_region['accpt_rt']:.1f}%
        """)
    
    with col2:
        # 시설 현황
        high_capacity_regions = len(filtered_df[filtered_df['accpt_rt'] >= 200])
        low_capacity_regions = len(filtered_df[filtered_df['accpt_rt'] < 100])
        
        st.warning(f"""
        **⚠️ 대피시설 현황**  
        🟢 수용률 200% 이상: {high_capacity_regions}개 지역  
        🔴 수용률 100% 미만: {low_capacity_regions}개 지역
        """)

# 데이터 테이블
st.markdown("---")
st.subheader("📋 상세 데이터")

# 컬럼명 한글화
column_mapping = {
    'bas_yy': '기준년도',
    'regi': '지역',
    'target_popl': '대상인구(명)',
    'accpt_rt': '수용률(%)',
    'shelt_abl_popl_smry': '대피가능인구 계(명)',
    'shelt_abl_popl_gov_shelts': '정부지원시설 대피가능인구(명)',
    'shelt_abl_popl_pub_shelts': '공공용시설 대피가능인구(명)',
    'gov_shelts_shelts': '정부지원시설 수(개소)',
    'gov_shelts_area': '정부지원시설 면적(㎡)',
    'pub_shelts_shelts': '공공용시설 수(개소)',
    'pub_shelts_area': '공공용시설 면적(㎡)'
}

display_df = filtered_df.copy()
display_df = display_df.rename(columns=column_mapping)

# 숫자 포맷팅
numeric_cols = ['대상인구(명)', '수용률(%)', '대피가능인구 계(명)', 
                '정부지원시설 대피가능인구(명)', '공공용시설 대피가능인구(명)',
                '정부지원시설 수(개소)', '정부지원시설 면적(㎡)',
                '공공용시설 수(개소)', '공공용시설 면적(㎡)']

for col in numeric_cols:
    if col in display_df.columns:
        if col == '수용률(%)':
            display_df[col] = display_df[col].round(1)
        else:
            display_df[col] = display_df[col].astype(int)

st.dataframe(display_df, use_container_width=True)

# 시각화
st.markdown("---")
st.subheader("📊 데이터 시각화")

# 탭 생성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 수용률 분석", "👥 인구 현황", "🏢 시설 현황", "🗺️ 지역 비교", "📈 종합 분석"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔝 수용률 상위 10개 지역**")
        if len(filtered_df) > 0:
            top10 = filtered_df.nlargest(min(10, len(filtered_df)), 'accpt_rt')
            fig = px.bar(
                top10, 
                x='accpt_rt', 
                y='regi',
                orientation='h',
                title="수용률 상위 지역",
                labels={'accpt_rt': '수용률(%)', 'regi': '지역'},
                color='accpt_rt',
                color_continuous_scale='Greens',
                text='accpt_rt'
            )
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**📊 수용률 분포**")
        if len(filtered_df) > 0:
            fig = px.histogram(
                filtered_df,
                x='accpt_rt',
                nbins=20,
                title="수용률 분포",
                labels={'accpt_rt': '수용률(%)', 'count': '지역 수'},
                color_discrete_sequence=['skyblue']
            )
            fig.add_vline(x=100, line_dash="dash", line_color="red", 
                         annotation_text="100% 기준선")
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**👥 대상인구 vs 대피가능인구**")
        if len(filtered_df) > 0:
            fig = px.scatter(
                filtered_df,
                x='target_popl',
                y='shelt_abl_popl_smry',
                hover_name='regi',
                size='pub_shelts_shelts',
                title="대상인구 vs 대피가능인구",
                labels={
                    'target_popl': '대상인구(명)',
                    'shelt_abl_popl_smry': '대피가능인구(명)',
                    'pub_shelts_shelts': '시설 수'
                }
            )
            # 100% 수용률 기준선
            max_val = max(filtered_df['target_popl'].max(), filtered_df['shelt_abl_popl_smry'].max())
            fig.add_shape(
                type="line",
                x0=0, y0=0, x1=max_val, y1=max_val,
                line=dict(color="red", width=2, dash="dash"),
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**📊 지역별 대상인구 순위**")
        if len(filtered_df) > 0:
            top_pop = filtered_df.nlargest(10, 'target_popl')
            fig = px.bar(
                top_pop,
                x='target_popl',
                y='regi',
                orientation='h',
                title="대상인구 상위 10개 지역",
                labels={'target_popl': '대상인구(명)', 'regi': '지역'},
                color='target_popl',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🏢 시설 수 vs 면적 관계**")
        if len(filtered_df) > 0:
            fig = px.scatter(
                filtered_df,
                x='pub_shelts_shelts',
                y='pub_shelts_area',
                hover_name='regi',
                color='accpt_rt',
                title="공공용시설 수 vs 면적",
                labels={
                    'pub_shelts_shelts': '시설 수(개소)',
                    'pub_shelts_area': '면적(㎡)',
                    'accpt_rt': '수용률(%)'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**📐 시설당 평균 면적**")
        if len(filtered_df) > 0:
            filtered_df_calc = filtered_df[filtered_df['pub_shelts_shelts'] > 0].copy()
            if not filtered_df_calc.empty:
                filtered_df_calc['avg_area'] = filtered_df_calc['pub_shelts_area'] / filtered_df_calc['pub_shelts_shelts']
                top_avg = filtered_df_calc.nlargest(10, 'avg_area')
                
                fig = px.bar(
                    top_avg,
                    x='avg_area',
                    y='regi',
                    orientation='h',
                    title="시설당 평균 면적 상위 10개 지역",
                    labels={'avg_area': '시설당 평균 면적(㎡)', 'regi': '지역'},
                    color='avg_area',
                    color_continuous_scale='Oranges'
                )
                st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("**🗺️ 지역별 종합 현황**")
    if len(filtered_df) > 0:
        # 지역별 히트맵
        heatmap_data = filtered_df.copy().sort_values('accpt_rt', ascending=True)
        
        fig = px.bar(
            heatmap_data,
            x='accpt_rt',
            y='regi',
            orientation='h',
            title="지역별 수용률 현황",
            labels={'accpt_rt': '수용률(%)', 'regi': '지역'},
            color='accpt_rt',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=max(400, len(filtered_df) * 25))
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    # 종합 분석 대시보드
    if len(filtered_df) > 0:
        # 서브플롯 생성
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('수용률 vs 대상인구', '시설 수 분포', '면적 vs 수용률', '수용률 박스플롯'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # 1. 수용률 vs 대상인구
        fig.add_trace(
            go.Scatter(
                x=filtered_df['target_popl'],
                y=filtered_df['accpt_rt'],
                mode='markers',
                name='지역별 현황',
                text=filtered_df['regi'],
                marker=dict(size=8, color='blue', opacity=0.6)
            ),
            row=1, col=1
        )
        
        # 2. 시설 수 분포
        fig.add_trace(
            go.Histogram(
                x=filtered_df['pub_shelts_shelts'],
                name='시설 수 분포',
                marker_color='green',
                opacity=0.7
            ),
            row=1, col=2
        )
        
        # 3. 면적 vs 수용률
        fig.add_trace(
            go.Scatter(
                x=filtered_df['pub_shelts_area'],
                y=filtered_df['accpt_rt'],
                mode='markers',
                name='면적-수용률',
                text=filtered_df['regi'],
                marker=dict(size=8, color='red', opacity=0.6)
            ),
            row=2, col=1
        )
        
        # 4. 수용률 박스플롯
        fig.add_trace(
            go.Box(
                y=filtered_df['accpt_rt'],
                name='수용률 분포',
                marker_color='orange'
            ),
            row=2, col=2
        )
        
        fig.update_layout(height=600, showlegend=False, title_text="종합 분석 대시보드")
        st.plotly_chart(fig, use_container_width=True)

# 통계 요약
st.markdown("---")
st.subheader("📈 통계 요약")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**🏆 수용률 통계**")
    if len(filtered_df) > 0:
        stats_df = pd.DataFrame({
            '통계': ['평균', '중앙값', '최댓값', '최솟값', '표준편차'],
            '수용률(%)': [
                filtered_df['accpt_rt'].mean(),
                filtered_df['accpt_rt'].median(),
                filtered_df['accpt_rt'].max(),
                filtered_df['accpt_rt'].min(),
                filtered_df['accpt_rt'].std()
            ]
        })
        stats_df['수용률(%)'] = stats_df['수용률(%)'].round(2)
        st.dataframe(stats_df, use_container_width=True)

with col2:
    st.markdown("**🏢 시설 통계**")
    if len(filtered_df) > 0:
        facility_stats = pd.DataFrame({
            '통계': ['총 시설 수', '평균 시설 수', '최대 시설 수', '최소 시설 수'],
            '값': [
                filtered_df['pub_shelts_shelts'].sum(),
                filtered_df['pub_shelts_shelts'].mean(),
                filtered_df['pub_shelts_shelts'].max(),
                filtered_df['pub_shelts_shelts'].min()
            ]
        })
        facility_stats['값'] = facility_stats['값'].round(0).astype(int)
        st.dataframe(facility_stats, use_container_width=True)

# API 정보 및 도움말
with st.expander("📋 API 정보 및 도움말"):
    st.markdown(f"""
    **📊 데이터 정보**
    - **기준연도**: {latest_year}년 (최신 데이터 자동 탐지)
    - **데이터 출처**: 행정안전부 통계연보
    - **API 서비스**: AirRaidShelterRegion
    - **갱신주기**: 년 1회
    - **총 지역 수**: {len(df)}개 지역
    
    **🔍 컬럼 설명**
    - **대상인구**: 해당 지역의 대피시설 대상 인구수 (명)
    - **수용률**: (대피가능인구 ÷ 대상인구) × 100 (%)
    - **대피가능인구 계**: 실제로 대피할 수 있는 총 인구수 (명)
    - **정부지원시설**: 정부에서 지원하는 대피시설
    - **공공용시설**: 공공기관에서 운영하는 대피시설
    - **시설 수**: 대피시설의 개소 수
    - **면적**: 대피시설의 총 면적 (㎡)
    
    **📈 수용률 해석 가이드**
    - **200% 이상**: 매우 충분한 대피시설 보유
    - **100~200%**: 적정 수준의 대피시설 보유
    - **50~100%**: 대피시설 부족, 증설 필요
    - **50% 미만**: 심각한 대피시설 부족 상태
    
    **🚨 에러 코드 안내**
    """)
    
    # 에러 코드 테이블
    error_df = pd.DataFrame([
        ["290", "인증키가 유효하지 않습니다"],
        ["310", "해당하는 서비스를 찾을 수 없습니다"],
        ["333", "요청위치 값의 타입이 유효하지 않습니다"],
        ["336", "데이터 요청은 한번에 최대 1,000건을 넘을 수 없습니다"],
        ["337", "일별 트래픽 제한을 넘은 호출입니다"],
        ["500", "서버 오류입니다"],
        ["0", "정상 처리되었습니다"],
        ["200", "해당하는 데이터가 없습니다"]
    ], columns=["에러코드", "설명"])
    
    st.dataframe(error_df, use_container_width=True)

# 데이터 다운로드
st.markdown("---")
st.subheader("💾 데이터 다운로드")

col1, col2 = st.columns(2)

with col1:
    # CSV 다운로드
    csv = display_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📁 CSV 파일 다운로드",
        data=csv,
        file_name=f"주민대피시설현황_{latest_year}년.csv",
        mime="text/csv",
        help="필터링된 데이터를 CSV 파일로 다운로드합니다."
    )

with col2:
    # JSON 다운로드
    json_data = filtered_df.to_json(orient='records', force_ascii=False, indent=2)
    st.download_button(
        label="📄 JSON 파일 다운로드",
        data=json_data,
        file_name=f"주민대피시설현황_{latest_year}년.json",
        mime="application/json",
        help="필터링된 데이터를 JSON 파일로 다운로드합니다."
    )

# 추가 분석 제안
st.markdown("---")
st.subheader("🔍 추가 분석 제안")

if len(filtered_df) > 0:
    # 위험 지역 식별
    risk_analysis = []
    
    # 수용률 100% 미만 지역
    low_capacity = filtered_df[filtered_df['accpt_rt'] < 100]
    if not low_capacity.empty:
        risk_analysis.append(f"🔴 **수용률 부족 지역**: {len(low_capacity)}개 지역이 수용률 100% 미만")
    
    # 시설 밀도가 낮은 지역 (인구 대비 시설 수)
    filtered_df_temp = filtered_df.copy()
    filtered_df_temp['facility_density'] = (filtered_df_temp['pub_shelts_shelts'] / filtered_df_temp['target_popl']) * 10000
    low_density = filtered_df_temp[filtered_df_temp['facility_density'] < filtered_df_temp['facility_density'].median()]
    if not low_density.empty:
        risk_analysis.append(f"🟡 **시설 밀도 낮은 지역**: {len(low_density)}개 지역이 평균 이하의 시설 밀도")
    
    # 대상인구가 많은데 수용률이 낮은 지역
    high_pop_low_rate = filtered_df[(filtered_df['target_popl'] > filtered_df['target_popl'].median()) & 
                                   (filtered_df['accpt_rt'] < 150)]
    if not high_pop_low_rate.empty:
        risk_analysis.append(f"🟠 **고위험 지역**: {len(high_pop_low_rate)}개 지역이 인구는 많으나 수용률 부족")
    
    # 분석 결과 표시
    if risk_analysis:
        st.warning("⚠️ **주의가 필요한 지역 분석**")
        for analysis in risk_analysis:
            st.markdown(f"- {analysis}")
    else:
        st.success("✅ 선택된 지역들의 대피시설 현황이 양호합니다.")

# 권장사항
st.markdown("---")
st.subheader("💡 정책 권장사항")

recommendations = []

if len(filtered_df) > 0:
    # 전체 평균 수용률 계산
    avg_capacity = filtered_df['accpt_rt'].mean()
    
    if avg_capacity < 100:
        recommendations.append("🚨 **긴급 개선 필요**: 전체 평균 수용률이 100% 미만으로 시설 확충이 시급합니다.")
    elif avg_capacity < 150:
        recommendations.append("⚠️ **점진적 개선**: 평균 수용률이 150% 미만으로 추가 시설 검토가 필요합니다.")
    else:
        recommendations.append("✅ **양호한 상태**: 전체적으로 적정 수준의 대피시설을 보유하고 있습니다.")
    
    # 지역간 격차 분석
    capacity_std = filtered_df['accpt_rt'].std()
    if capacity_std > 100:
        recommendations.append("📊 **지역 격차 해소**: 지역간 수용률 격차가 커서 균형 발전이 필요합니다.")
    
    # 시설 효율성 분석
    if 'pub_shelts_area' in filtered_df.columns and 'pub_shelts_shelts' in filtered_df.columns:
        filtered_df_temp = filtered_df[filtered_df['pub_shelts_shelts'] > 0].copy()
        if not filtered_df_temp.empty:
            avg_facility_size = (filtered_df_temp['pub_shelts_area'] / filtered_df_temp['pub_shelts_shelts']).mean()
            if avg_facility_size < 5000:  # 5,000㎡ 미만
                recommendations.append("🏢 **시설 규모 확대**: 시설당 평균 면적이 작아 대규모 시설 건설을 검토해보세요.")

# 권장사항 표시
if recommendations:
    for i, rec in enumerate(recommendations, 1):
        st.markdown(f"{i}. {rec}")
else:
    st.info("현재 선택된 데이터로는 특별한 권장사항이 없습니다.")

# 푸터
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: #666; font-size: 12px;'>
        📊 <strong>행정안전부 주민대피시설 현황 대시보드</strong><br>
        🔄 데이터 기준: {latest_year}년 | 📅 대시보드 생성: {datetime.now().strftime('%Y년 %m월 %d일')}<br>
        📞 문의: 행정안전부 정보통계담당관 (044-205-1644)<br>
        🌐 데이터 출처: <a href="https://data.go.kr" target="_blank">공공데이터포털 (data.go.kr)</a>
    </div>
    """,
    unsafe_allow_html=True
)
