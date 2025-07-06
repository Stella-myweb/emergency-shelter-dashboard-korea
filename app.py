# -*- coding: utf-8 -*-
"""
주민대피시설 통계 대시보드 Streamlit 앱
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from datetime import datetime
import folium
from streamlit_folium import st_folium
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 설정
st.set_page_config(
    page_title="주민대피시설 통계 대시보드",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일링
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(90deg, #f0f2f6 0%, #ffffff 100%);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .warning-card {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .success-card {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 캐시 데코레이터로 API 호출 최적화
@st.cache_data(ttl=3600)  # 1시간 캐시
def fetch_shelter_data():
    """API에서 주민대피시설 데이터 가져오기"""
    
    service_key = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="
    # HTTPS를 HTTP로 변경 - 공공데이터포털 SSL 이슈 해결
    base_url = "http://apis.data.go.kr/1741000/AirRaidShelterRegion"
    
    all_data = []
    page = 1
    
    try:
        while True:
            params = {
                "serviceKey": service_key,
                "pageNo": page,
                "numOfRows": 100,  # 한 번에 가져올 데이터 수 줄임
                "type": "json"
            }
            
            # 일반 HTTP 요청으로 변경
            response = requests.get(
                base_url, 
                params=params, 
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
            )
            
            if response.status_code != 200:
                st.error(f"API 요청 실패: 상태 코드 {response.status_code}")
                st.error(f"응답 내용: {response.text[:500]}")
                break
                
            try:
                data = response.json()
                st.info(f"API 응답 구조 확인: {list(data.keys())}")  # 디버깅용
            except json.JSONDecodeError as e:
                st.error(f"JSON 응답 파싱 실패: {str(e)}")
                st.error(f"응답 내용: {response.text[:500]}")
                break
            
            # 다양한 API 응답 구조 처리
            items = []
            if 'response' in data and 'body' in data['response']:
                items = data['response']['body'].get('items', [])
                total_count = data['response']['body'].get('totalCount', 0)
            elif 'items' in data:
                items = data.get('items', [])
                total_count = len(items)
            elif isinstance(data, list):
                items = data
                total_count = len(items)
            else:
                st.error("예상과 다른 API 응답 구조")
                st.json(data)  # 실제 응답 구조 확인용
                break
            
            if not items:
                if page == 1:
                    st.warning("첫 페이지에서 데이터가 없습니다. API 응답을 확인해주세요.")
                break
                
            all_data.extend(items)
            st.info(f"페이지 {page}: {len(items)}개 데이터 수집, 총 {len(all_data)}개")
            
            # 페이지네이션 처리
            if len(items) < 100 or len(all_data) >= total_count:
                break
                
            page += 1
            
            # 최대 10페이지까지만 (과도한 요청 방지)
            if page > 10:
                st.warning("최대 페이지 수에 도달했습니다.")
                break
                
        if not all_data:
            st.error("API에서 데이터를 받아오지 못했습니다.")
            return None
            
        st.success(f"총 {len(all_data)}개의 데이터를 성공적으로 수집했습니다!")
        return pd.DataFrame(all_data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 중 네트워크 오류: {str(e)}")
        return None
    except Exception as e:
        st.error(f"데이터 로딩 중 오류 발생: {str(e)}")
        return None

@st.cache_data
def create_sample_data():
    """API 연결이 안 될 경우 사용할 샘플 데이터 생성"""
    
    sample_data = {
        'regi': ['서울특별시 종로구', '서울특별시 중구', '서울특별시 용산구', '부산광역시 중구', 
                '부산광역시 서구', '대구광역시 중구', '인천광역시 중구', '광주광역시 동구',
                '대전광역시 중구', '울산광역시 중구', '경기도 수원시', '경기도 성남시',
                '경기도 고양시', '경기도 용인시', '강원도 춘천시', '충청북도 청주시',
                '충청남도 천안시', '전라북도 전주시', '전라남도 목포시', '경상북도 포항시'],
        'target_popl': [45000, 38000, 52000, 31000, 27000, 29000, 33000, 24000,
                       41000, 35000, 67000, 58000, 63000, 71000, 22000, 34000,
                       48000, 39000, 28000, 42000],
        'shell_abl_popl_smry': [52000, 35000, 48000, 28000, 30000, 25000, 31000, 26000,
                               38000, 33000, 59000, 54000, 61000, 65000, 25000, 37000,
                               51000, 36000, 32000, 45000],
        'accpt_rt': [115.6, 92.1, 92.3, 90.3, 111.1, 86.2, 93.9, 108.3,
                    92.7, 94.3, 88.1, 93.1, 96.8, 91.5, 113.6, 108.8,
                    106.3, 92.3, 114.3, 107.1],
        'gov_shells_shells': [12, 8, 15, 7, 9, 6, 8, 5, 11, 9, 18, 16, 17, 19, 6, 10,
                             13, 11, 7, 12],
        'gov_shells_area': [8500, 6200, 11000, 4800, 6800, 4200, 5900, 3800, 7800, 6500,
                           13500, 12000, 12800, 14200, 4500, 7200, 9800, 8200, 5100, 8900],
        'pub_shells_shells': [8, 6, 10, 5, 6, 4, 6, 4, 7, 6, 12, 11, 11, 13, 4, 7,
                             9, 7, 5, 8],
        'pub_shells_area': [5200, 3800, 6800, 3200, 4200, 2800, 3900, 2600, 4900, 4200,
                           8800, 7800, 8400, 9200, 2900, 4700, 6400, 5300, 3300, 5800]
    }
    
    return pd.DataFrame(sample_data)
    """대피시설 데이터 전처리"""
    
    if df is None or df.empty:
        return None
    
    # 수치형 컬럼 변환
    numeric_columns = ['target_popl', 'accpt_rt', 'shell_abl_popl_smry', 
                      'gov_shells_shells', 'gov_shells_area', 'pub_shells_shells', 'pub_shells_area']
    
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 결측치 처리
    df = df.dropna(subset=['regi'])
    
    # 수용률 계산 (없는 경우)
    if 'accpt_rt' not in df.columns or df['accpt_rt'].isna().all():
        df['accpt_rt'] = np.where(df['target_popl'] > 0, 
                                 (df['shell_abl_popl_smry'] / df['target_popl'] * 100), 
                                 0)
    
    # 수용률 범주 생성
    df['capacity_level'] = pd.cut(df['accpt_rt'], 
                                 bins=[0, 50, 80, 100, float('inf')], 
                                 labels=['부족', '보통', '양호', '충분'])
    
    # 총 시설 수 계산
    df['total_facilities'] = df['gov_shells_shells'].fillna(0) + df['pub_shells_shells'].fillna(0)
    
    # 총 면적 계산
    df['total_area'] = df['gov_shells_area'].fillna(0) + df['pub_shells_area'].fillna(0)
    
    return df

def create_summary_metrics(df):
    """주요 지표 요약 카드"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_regions = len(df)
        st.metric("전체 지역 수", f"{total_regions:,}개")
    
    with col2:
        avg_capacity = df['accpt_rt'].mean()
        st.metric("전국 평균 수용률", f"{avg_capacity:.1f}%")
    
    with col3:
        total_facilities = df['total_facilities'].sum()
        st.metric("총 대피시설 수", f"{total_facilities:,}개")
    
    with col4:
        total_population = df['target_popl'].sum()
        st.metric("총 대상인구", f"{total_population:,}명")

def create_capacity_map(df):
    """수용률 기반 지도 생성"""
    
    st.subheader("🗺️ 지역별 수용률 분포 지도")
    
    # 색상 매핑
    color_map = {
        '부족': 'red',
        '보통': 'orange', 
        '양호': 'yellow',
        '충분': 'green'
    }
    
    # 지도 데이터 준비 (실제 좌표가 없으므로 임의로 생성)
    # 실제로는 API에서 좌표 데이터를 가져와야 함
    map_data = df.copy()
    
    if len(map_data) > 0:
        # 수용률별 색상 차트
        fig = px.bar(
            df['capacity_level'].value_counts().reset_index(),
            x='index',
            y='capacity_level',
            color='index',
            title="수용률 등급별 지역 분포",
            labels={'index': '수용률 등급', 'capacity_level': '지역 수'},
            color_discrete_map=color_map
        )
        
        st.plotly_chart(fig, use_container_width=True)

def create_regional_analysis(df):
    """지역별 상세 분석"""
    
    st.subheader("📊 지역별 상세 분석")
    
    # 상위/하위 지역 분석
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🔴 수용률 부족 지역 Top 10**")
        low_capacity = df.nsmallest(10, 'accpt_rt')[['regi', 'accpt_rt', 'target_popl', 'shell_abl_popl_smry']]
        low_capacity.columns = ['지역', '수용률(%)', '대상인구', '수용가능인구']
        st.dataframe(low_capacity, use_container_width=True)
    
    with col2:
        st.write("**🟢 수용률 우수 지역 Top 10**")
        high_capacity = df.nlargest(10, 'accpt_rt')[['regi', 'accpt_rt', 'target_popl', 'shell_abl_popl_smry']]
        high_capacity.columns = ['지역', '수용률(%)', '대상인구', '수용가능인구']
        st.dataframe(high_capacity, use_container_width=True)

def create_statistical_charts(df):
    """통계 차트 생성"""
    
    st.subheader("📈 통계 분석")
    
    # 차트 선택
    chart_type = st.selectbox(
        "차트 유형 선택",
        ["수용률 분포", "인구 대비 시설 분석", "면적 효율성 분석"]
    )
    
    if chart_type == "수용률 분포":
        fig = px.histogram(
            df, 
            x='accpt_rt', 
            nbins=20,
            title="지역별 수용률 분포",
            labels={'accpt_rt': '수용률(%)', 'count': '지역 수'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
    elif chart_type == "인구 대비 시설 분석":
        fig = px.scatter(
            df.head(100),  # 상위 100개 지역만 표시
            x='target_popl',
            y='total_facilities',
            size='accpt_rt',
            color='capacity_level',
            hover_data=['regi'],
            title="대상인구 대비 시설 수 분석",
            labels={'target_popl': '대상인구', 'total_facilities': '총 시설 수'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
    elif chart_type == "면적 효율성 분석":
        # 1인당 면적 계산
        df['area_per_person'] = df['total_area'] / df['shell_abl_popl_smry']
        df['area_per_person'] = df['area_per_person'].replace([np.inf, -np.inf], np.nan)
        
        fig = px.box(
            df,
            y='area_per_person',
            title="1인당 대피시설 면적 분포",
            labels={'area_per_person': '1인당 면적(㎡)'}
        )
        st.plotly_chart(fig, use_container_width=True)

def create_emergency_info():
    """비상연락처 및 대피요령"""
    
    st.subheader("🚨 비상연락처 및 대피요령")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **📞 비상연락처**
        - 종합상황실: 119
        - 경찰서: 112  
        - 소방서: 119
        - 군부대: 지역별 상이
        - 시·군·구청: 지역별 상이
        """)
        
    with col2:
        st.markdown("""
        **🏃‍♂️ 대피요령**
        1. 경보 발령 시 즉시 대피
        2. 가장 가까운 대피시설로 이동
        3. 개인 신분증 및 최소 생필품 지참
        4. 질서를 지키며 안전하게 대피
        5. 대피시설 내 안전수칙 준수
        """)

def main():
    """메인 함수"""
    
    # 제목
    st.markdown('<h1 class="main-header">🏠 주민대피시설 통계 대시보드</h1>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    <div class="success-card">
        <strong>📍 서비스 소개</strong><br>
        전국 주민대피시설의 통계 정보를 한눈에 확인할 수 있는 대시보드입니다.
        지역별 수용률, 시설 현황, 대상인구 등을 시각화하여 제공합니다.
    </div>
    """, unsafe_allow_html=True)
    
    # 데이터 로딩
    with st.spinner("🔄 데이터를 불러오는 중..."):
        raw_data = fetch_shelter_data()
        
    if raw_data is None:
        st.warning("⚠️ API에서 실시간 데이터를 가져올 수 없어 샘플 데이터를 사용합니다.")
        st.info("실제 서비스에서는 API 연결을 확인해주세요.")
        raw_data = create_sample_data()
        
        if raw_data is None:
            st.error("샘플 데이터도 생성할 수 없습니다.")
            st.stop()
    
    # 데이터 전처리
    with st.spinner("⚙️ 데이터를 분석하는 중..."):
        processed_data = process_shelter_data(raw_data)
        
    if processed_data is None:
        st.error("데이터 처리 중 오류가 발생했습니다.")
        st.stop()
    
    # 사이드바 필터
    st.sidebar.header("🔍 필터 옵션")
    
    # 지역 필터
    regions = ['전체'] + sorted(processed_data['regi'].unique().tolist())
    selected_region = st.sidebar.selectbox("지역 선택", regions)
    
    # 수용률 필터
    min_capacity, max_capacity = st.sidebar.slider(
        "수용률 범위 (%)",
        min_value=0,
        max_value=int(processed_data['accpt_rt'].max()),
        value=(0, int(processed_data['accpt_rt'].max()))
    )
    
    # 데이터 필터링
    filtered_data = processed_data.copy()
    if selected_region != '전체':
        filtered_data = filtered_data[filtered_data['regi'] == selected_region]
    
    filtered_data = filtered_data[
        (filtered_data['accpt_rt'] >= min_capacity) & 
        (filtered_data['accpt_rt'] <= max_capacity)
    ]
    
    # 메인 대시보드
    st.header("📊 주요 통계")
    create_summary_metrics(filtered_data)
    
    # 지도 및 분석
    create_capacity_map(filtered_data)
    create_regional_analysis(filtered_data)
    create_statistical_charts(filtered_data)
    
    # 원본 데이터 보기
    with st.expander("📋 원본 데이터 보기"):
        st.dataframe(filtered_data, use_container_width=True)
        
        # 데이터 다운로드
        csv = filtered_data.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 CSV 다운로드",
            data=csv,
            file_name=f'shelter_data_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
    
    # 비상정보
    create_emergency_info()
    
    # 푸터
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666; font-size: 0.9em;">
            📊 데이터 출처: 공공데이터포털 - 지역별 주민대피시설 통계 조회<br>
            🔄 데이터 갱신: 매일 자동 업데이트<br>
            💡 문의사항이 있으시면 관련 기관에 연락하세요.
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
