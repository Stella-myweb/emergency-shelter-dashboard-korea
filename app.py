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

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="주민대피시설 현황 대시보드",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 제목 및 설명
st.title("🏢 주민대피시설 현황 대시보드")
st.markdown("---")
st.markdown("**행정안전부 통계연보 - 지역별 주민대피시설 현황을 시각화한 대시보드입니다.**")

# 사이드바 설정
st.sidebar.header("📊 데이터 설정")

# SERVICE_KEY 입력
service_key = st.sidebar.text_input(
    "🔑 SERVICE_KEY 입력",
    value="",
    type="password",
    help="공공데이터포털에서 발급받은 인증키를 입력하세요."
)

if not service_key:
    st.warning("⚠️ SERVICE_KEY를 입력해야 데이터를 조회할 수 있습니다.")
    st.info("공공데이터포털(data.go.kr)에서 '행정안전부_통계연보_지역별 주민대피시설' API의 인증키를 발급받아 입력하세요.")
    st.stop()

# 연도 선택 (2019~2025, 역순)
selected_year = st.sidebar.selectbox(
    "📅 기준 연도 선택",
    options=list(range(2025, 2018, -1)),
    index=0,
    help="조회할 기준 연도를 선택하세요."
)

# API 호출 함수
@st.cache_data(ttl=300)
def fetch_air_raid_shelter_data(service_key, year, page_no=1, num_of_rows=1000):
    """공공데이터 API에서 주민대피시설 데이터를 가져오는 함수"""
    
    # 인증키 디코딩
    decoded_key = unquote(service_key)
    
    # API 엔드포인트
    url = "https://apis.data.go.kr/1741000/AirRaidShelterRegion/getAirRaidShelterRegionList"
    
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
        response = requests.get(url, params=params, verify=False, timeout=10)
        response.raise_for_status()
        
        # JSON 응답 파싱
        data = response.json()
        
        # 응답 구조 확인 및 데이터 추출
        if 'response' in data and 'body' in data['response']:
            body = data['response']['body']
            
            # items 확인
            if 'items' in body:
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
                return []
        else:
            return []
            
    except requests.exceptions.RequestException as e:
        st.error(f"🚨 API 호출 실패: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"🚨 JSON 파싱 실패: {str(e)}")
        return None
    except Exception as e:
        st.error(f"🚨 예상치 못한 오류: {str(e)}")
        return None

# 데이터 전처리 함수
def preprocess_data(raw_data):
    """원시 데이터를 DataFrame으로 변환하고 전처리"""
    
    if not raw_data:
        return pd.DataFrame()
    
    # DataFrame 생성
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        return df
    
    # 지역 컬럼 자동 매핑
    region_col = None
    for col in df.columns:
        if 'regi' in col.lower() or '지역' in col:
            region_col = col
            break
    
    if region_col and region_col != 'regi':
        df['regi'] = df[region_col]
    
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
    
    # '합계' 행 제거 (전체 통계는 별도 처리)
    df = df[df['regi'] != '합계'].copy()
    
    return df

# 데이터 로드
with st.spinner("📡 데이터를 불러오는 중..."):
    raw_data = fetch_air_raid_shelter_data(service_key, selected_year)
    
    if raw_data is None:
        st.stop()
    
    df = preprocess_data(raw_data)
    
    if df.empty:
        st.warning("⚠️ 선택한 연도의 데이터가 없습니다.")
        st.stop()

# 사이드바 필터
st.sidebar.markdown("---")
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
else:
    rate_range = (0, 100)

# 데이터 필터링
filtered_df = df.copy()

if '전체' not in selected_regions:
    filtered_df = filtered_df[filtered_df['regi'].isin(selected_regions)]

if 'accpt_rt' in filtered_df.columns:
    filtered_df = filtered_df[
        (filtered_df['accpt_rt'] >= rate_range[0]) & 
        (filtered_df['accpt_rt'] <= rate_range[1])
    ]

# 메인 대시보드
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📍 총 지역 수",
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

# 데이터 테이블
st.markdown("---")
st.subheader("📋 데이터 테이블")

# 컬럼명 한글화
column_mapping = {
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
tab1, tab2, tab3, tab4 = st.tabs(["🏆 수용률 순위", "📈 인구 분석", "🏢 시설 분석", "🗺️ 지역별 현황"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔝 수용률 Top 10**")
        if 'accpt_rt' in filtered_df.columns:
            top10 = filtered_df.nlargest(10, 'accpt_rt')
            fig = px.bar(
                top10, 
                x='accpt_rt', 
                y='regi',
                orientation='h',
                title="수용률 상위 10개 지역",
                labels={'accpt_rt': '수용률(%)', 'regi': '지역'},
                color='accpt_rt',
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**🔻 수용률 Bottom 10**")
        if 'accpt_rt' in filtered_df.columns:
            bottom10 = filtered_df.nsmallest(10, 'accpt_rt')
            fig = px.bar(
                bottom10, 
                x='accpt_rt', 
                y='regi',
                orientation='h',
                title="수용률 하위 10개 지역",
                labels={'accpt_rt': '수용률(%)', 'regi': '지역'},
                color='accpt_rt',
                color_continuous_scale='Reds'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**👥 대상인구 vs 대피가능인구**")
        if 'target_popl' in filtered_df.columns and 'shelt_abl_popl_smry' in filtered_df.columns:
            fig = px.scatter(
                filtered_df,
                x='target_popl',
                y='shelt_abl_popl_smry',
                hover_name='regi',
                title="대상인구 vs 대피가능인구",
                labels={
                    'target_popl': '대상인구(명)',
                    'shelt_abl_popl_smry': '대피가능인구(명)'
                }
            )
            # 대각선 추가 (수용률 100% 기준선)
            max_val = max(filtered_df['target_popl'].max(), filtered_df['shelt_abl_popl_smry'].max())
            fig.add_shape(
                type="line",
                x0=0, y0=0, x1=max_val, y1=max_val,
                line=dict(color="red", width=2, dash="dash"),
                name="100% 수용률 기준선"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**📊 인구 분포**")
        if 'target_popl' in filtered_df.columns:
            fig = px.histogram(
                filtered_df,
                x='target_popl',
                nbins=20,
                title="대상인구 분포",
                labels={'target_popl': '대상인구(명)', 'count': '지역 수'}
            )
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🏢 시설 수 vs 면적**")
        if 'pub_shelts_shelts' in filtered_df.columns and 'pub_shelts_area' in filtered_df.columns:
            fig = px.scatter(
                filtered_df,
                x='pub_shelts_shelts',
                y='pub_shelts_area',
                hover_name='regi',
                title="공공용시설 수 vs 면적",
                labels={
                    'pub_shelts_shelts': '시설 수(개소)',
                    'pub_shelts_area': '면적(㎡)'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**📊 시설 유형별 비교**")
        if 'gov_shelts_shelts' in filtered_df.columns and 'pub_shelts_shelts' in filtered_df.columns:
            # 시설 유형별 합계 계산
            gov_total = filtered_df['gov_shelts_shelts'].sum()
            pub_total = filtered_df['pub_shelts_shelts'].sum()
            
            fig = px.pie(
                values=[gov_total, pub_total],
                names=['정부지원시설', '공공용시설'],
                title="시설 유형별 비율"
            )
            st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("**🗺️ 지역별 수용률 히트맵**")
    
    if 'accpt_rt' in filtered_df.columns:
        # 히트맵용 데이터 준비
        heatmap_data = filtered_df.pivot_table(
            index='regi',
            values='accpt_rt',
            aggfunc='mean'
        ).reset_index()
        
        fig = px.bar(
            heatmap_data.sort_values('accpt_rt', ascending=True),
            x='accpt_rt',
            y='regi',
            orientation='h',
            title="지역별 수용률 현황",
            labels={'accpt_rt': '수용률(%)', 'regi': '지역'},
            color='accpt_rt',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

# 추가 분석
st.markdown("---")
st.subheader("📈 추가 분석")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**🏆 수용률 통계**")
    if 'accpt_rt' in filtered_df.columns:
        stats_df = pd.DataFrame({
            '통계': ['평균', '중앙값', '최대값', '최소값', '표준편차'],
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
    if 'pub_shelts_shelts' in filtered_df.columns:
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

# 푸터
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 12px;'>
        📊 데이터 출처: 행정안전부 통계연보 (data.go.kr)<br>
        🔄 데이터 갱신주기: 연 1회<br>
        📅 대시보드 기준일: 2025년 7월 6일
    </div>
    """,
    unsafe_allow_html=True
)
