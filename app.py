import streamlit as st
import pandas as pd
import requests
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import urllib3
import warnings
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

# SERVICE_KEY 설정 (디코딩된 키)
SERVICE_KEY = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="

# 제목 및 설명
st.title("🏢 주민대피시설 현황 대시보드")
st.markdown("---")
st.markdown("**행정안전부 통계연보 - 지역별 주민대피시설 현황을 시각화한 대시보드입니다.**")

# API 호출 함수
@st.cache_data(ttl=300)
def fetch_air_raid_shelter_data(service_key, year, page_no=1, num_of_rows=1000):
    """공공데이터 API에서 주민대피시설 데이터를 가져오는 함수"""
    
    # API 엔드포인트
    url = "http://apis.data.go.kr/1741000/AirRaidShelterRegion/getAirRaidShelterRegionList"
    
    # 파라미터 설정
    params = {
        'ServiceKey': service_key,
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
        data = response.json()
        
        # JSON 구조에 따른 파싱
        if "AirRaidShelterRegion" in data:
            arr = data["AirRaidShelterRegion"]
            
            # 실제 레코드 데이터 추출
            rows = None
            for block in arr:
                if "row" in block:
                    rows = block["row"]
                    break
            
            if rows:
                st.success(f"✅ {year}년 데이터 로드 성공 ({len(rows)}개 지역)")
                return rows
            else:
                st.warning(f"⚠️ {year}년 데이터가 없습니다.")
                return None
        else:
            st.error("🚨 예상과 다른 API 응답 구조입니다.")
            return None
            
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
        return pd.DataFrame(), pd.DataFrame()
    
    # DataFrame 생성
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        return df, pd.DataFrame()
    
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
    
    # '합계' 행 저장 후 제거 (컬럼 존재 확인)
    total_row = pd.DataFrame()
    if 'regi' in df.columns:
        total_row = df[df['regi'] == '합계'].copy()
        df_filtered = df[df['regi'] != '합계'].copy()
    else:
        df_filtered = df.copy()
    
    return df_filtered, total_row

# 사이드바 설정
st.sidebar.header("🔍 데이터 설정")

# 연도 선택 (2025부터 2019까지 역순)
years = list(range(2025, 2018, -1))
selected_year = st.sidebar.selectbox(
    "📅 기준연도 선택",
    options=years,
    index=0,  # 기본값: 2025
    help="분석할 연도를 선택하세요."
)

# 데이터 로드
with st.spinner(f"📡 {selected_year}년 데이터를 불러오는 중..."):
    raw_data = fetch_air_raid_shelter_data(SERVICE_KEY, selected_year)
    
    if raw_data is None:
        st.error(f"❌ {selected_year}년 데이터를 불러올 수 없습니다. 다른 연도를 선택해주세요.")
        st.stop()
    
    df, total_df = preprocess_data(raw_data)
    
    if df.empty:
        st.warning(f"⚠️ {selected_year}년도 데이터가 비어있습니다.")
        st.stop()

# 사이드바 필터
st.sidebar.header("🔍 데이터 필터")

# 지역 선택 (컬럼 존재 확인)
if 'regi' in df.columns:
    regions = ['전체'] + sorted(df['regi'].unique().tolist())
    selected_region = st.sidebar.selectbox(
        "🏙️ 지역 선택",
        options=regions,
        index=0,
        help="분석할 지역을 선택하세요."
    )
else:
    selected_region = '전체'
    st.sidebar.warning("지역 정보가 없습니다.")

# 수용률 범위 슬라이더
if 'accpt_rt' in df.columns and not df['accpt_rt'].isna().all():
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
    st.sidebar.warning("수용률 정보가 없습니다.")

# 데이터 필터링
filtered_df = df.copy()

if selected_region != '전체' and 'regi' in df.columns:
    filtered_df = filtered_df[filtered_df['regi'] == selected_region]

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
        target_popl = total_row.get('target_popl', 0)
        st.metric(
            label="👥 전국 대상인구",
            value=f"{target_popl:,.0f}명",
            help="전국 주민대피시설 대상인구"
        )
    
    with col2:
        accpt_rt = total_row.get('accpt_rt', 0)
        st.metric(
            label="📊 전국 평균 수용률",
            value=f"{accpt_rt:.1f}%",
            help="전국 평균 대피시설 수용률"
        )
    
    with col3:
        pub_shelts = total_row.get('pub_shelts_shelts', 0)
        st.metric(
            label="🏢 전국 총 시설 수",
            value=f"{pub_shelts:,.0f}개소",
            help="전국 공공용 대피시설 수"
        )
    
    with col4:
        pub_area = total_row.get('pub_shelts_area', 0)
        st.metric(
            label="📐 전국 총 시설 면적",
            value=f"{pub_area:,.0f}㎡",
            help="전국 공공용 대피시설 면적"
        )
else:
    # 합계 행이 없는 경우 필터링된 데이터로 계산
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_population = filtered_df.get('target_popl', pd.Series([0])).sum()
        st.metric(
            label="👥 대상인구 합계",
            value=f"{total_population:,.0f}명"
        )
    
    with col2:
        avg_rate = filtered_df.get('accpt_rt', pd.Series([0])).mean()
        st.metric(
            label="📊 평균 수용률",
            value=f"{avg_rate:.1f}%"
        )
    
    with col3:
        total_facilities = filtered_df.get('pub_shelts_shelts', pd.Series([0])).sum()
        st.metric(
            label="🏢 총 시설 수",
            value=f"{total_facilities:,.0f}개소"
        )
    
    with col4:
        total_area = filtered_df.get('pub_shelts_area', pd.Series([0])).sum()
        st.metric(
            label="📐 총 시설 면적",
            value=f"{total_area:,.0f}㎡"
        )

# 필터링된 지역 통계
st.markdown("---")
st.markdown("### 📊 선택 지역 통계")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📍 총 지역 수",
        value=len(filtered_df),
        delta=f"{len(filtered_df) - len(df)} (필터 적용)" if len(filtered_df) != len(df) else None
    )

with col2:
    total_population = filtered_df.get('target_popl', pd.Series([0])).sum()
    st.metric(
        label="👥 대상 인구",
        value=f"{total_population:,}명"
    )

with col3:
    avg_rate = filtered_df.get('accpt_rt', pd.Series([0])).mean()
    st.metric(
        label="📊 평균 수용률",
        value=f"{avg_rate:.1f}%"
    )

with col4:
    total_facilities = filtered_df.get('pub_shelts_shelts', pd.Series([0])).sum()
    st.metric(
        label="🏢 총 시설 수",
        value=f"{total_facilities:,}개소"
    )

# 데이터 테이블
st.markdown("---")
st.subheader("📋 상세 데이터")

if not filtered_df.empty:
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
    
    # 존재하는 컬럼만 매핑
    existing_columns = {k: v for k, v in column_mapping.items() if k in display_df.columns}
    display_df = display_df.rename(columns=existing_columns)

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
else:
    st.warning("표시할 데이터가 없습니다.")

# 시각화
if not filtered_df.empty and 'accpt_rt' in filtered_df.columns:
    st.markdown("---")
    st.subheader("📊 데이터 시각화")

    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 수용률 분석", "👥 인구 현황", "🏢 시설 현황", "📈 종합 분석"])

    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🔝 수용률 상위 10개 지역**")
            if len(filtered_df) > 0:
                top10 = filtered_df.nlargest(min(10, len(filtered_df)), 'accpt_rt')
                if 'regi' in top10.columns:
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
            if 'target_popl' in filtered_df.columns and 'shelt_abl_popl_smry' in filtered_df.columns:
                hover_name = 'regi' if 'regi' in filtered_df.columns else None
                size_col = 'pub_shelts_shelts' if 'pub_shelts_shelts' in filtered_df.columns else None
                
                fig = px.scatter(
                    filtered_df,
                    x='target_popl',
                    y='shelt_abl_popl_smry',
                    hover_name=hover_name,
                    size=size_col,
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
            if 'target_popl' in filtered_df.columns and 'regi' in filtered_df.columns:
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
            if 'pub_shelts_shelts' in filtered_df.columns and 'pub_shelts_area' in filtered_df.columns:
                hover_name = 'regi' if 'regi' in filtered_df.columns else None
                
                fig = px.scatter(
                    filtered_df,
                    x='pub_shelts_shelts',
                    y='pub_shelts_area',
                    hover_name=hover_name,
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
            if 'pub_shelts_shelts' in filtered_df.columns and 'pub_shelts_area' in filtered_df.columns and 'regi' in filtered_df.columns:
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
        st.markdown("**📈 종합 분석**")
        if 'regi' in filtered_df.columns:
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

# 통계 요약
st.markdown("---")
st.subheader("📈 통계 요약")

if not filtered_df.empty and 'accpt_rt' in filtered_df.columns:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🏆 수용률 통계**")
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

# 데이터 다운로드
st.markdown("---")
st.subheader("💾 데이터 다운로드")

if not filtered_df.empty:
    col1, col2 = st.columns(2)

    with col1:
        # CSV 다운로드
        if 'display_df' in locals():
            csv = display_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📁 CSV 파일 다운로드",
                data=csv,
                file_name=f"주민대피시설현황_{selected_year}년.csv",
                mime="text/csv",
                help="필터링된 데이터를 CSV 파일로 다운로드합니다."
            )

    with col2:
        # JSON 다운로드
        json_data = filtered_df.to_json(orient='records', force_ascii=False, indent=2)
        st.download_button(
            label="📄 JSON 파일 다운로드",
            data=json_data,
            file_name=f"주민대피시설현황_{selected_year}년.json",
            mime="application/json",
            help="필터링된 데이터를 JSON 파일로 다운로드합니다."
        )

# 푸터
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: #666; font-size: 12px;'>
        📊 <strong>행정안전부 주민대피시설 현황 대시보드</strong><br>
        🔄 데이터 기준: {selected_year}년 | 📅 대시보드 생성: {datetime.now().strftime('%Y년 %m월 %d일')}<br>
        📞 문의: 행정안전부 정보통계담당관 (044-205-1644)<br>
        🌐 데이터 출처: <a href="https://data.go.kr" target="_blank">공공데이터포털 (data.go.kr)</a>
    </div>
    """,
    unsafe_allow_html=True
)
