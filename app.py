# -*- coding: utf-8 -*-
"""
주민대피시설 통계 대시보드 Streamlit 앱
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime
import json
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
</style>
""", unsafe_allow_html=True)

# 🔧 전처리 함수 먼저 정의
@st.cache_data
def process_shelter_data(df):
    """대피시설 데이터 전처리"""
    if df is None or df.empty:
        return None

    numeric_columns = [
        'target_popl', 'accpt_rt', 'shell_abl_popl_smry',
        'gov_shells_shells', 'gov_shells_area', 'pub_shells_shells', 'pub_shells_area'
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['regi'])

    if 'accpt_rt' not in df.columns or df['accpt_rt'].isna().all():
        df['accpt_rt'] = np.where(df['target_popl'] > 0,
                                  (df['shell_abl_popl_smry'] / df['target_popl'] * 100), 0)

    df['capacity_level'] = pd.cut(
        df['accpt_rt'],
        bins=[0, 50, 80, 100, float('inf')],
        labels=['부족', '보통', '양호', '충분']
    )

    df['total_facilities'] = df['gov_shells_shells'].fillna(0) + df['pub_shells_shells'].fillna(0)
    df['total_area'] = df['gov_shells_area'].fillna(0) + df['pub_shells_area'].fillna(0)

    return df

def process_api_response(data):
    """API 응답 데이터 처리"""
    items = []
    if 'response' in data and 'body' in data['response']:
        items = data['response']['body'].get('items', [])
    elif 'items' in data:
        items = data.get('items', [])
    elif isinstance(data, list):
        items = data
    return pd.DataFrame(items) if items else None

@st.cache_data
def create_sample_data():
    """API 연결이 안 될 경우 사용할 샘플 데이터 생성"""
    sample_data = {
        'regi': ['서울특별시 종로구', '부산광역시 중구'],
        'target_popl': [45000, 31000],
        'shell_abl_popl_smry': [52000, 28000],
        'accpt_rt': [115.6, 90.3],
        'gov_shells_shells': [12, 7],
        'gov_shells_area': [8500, 4800],
        'pub_shells_shells': [8, 5],
        'pub_shells_area': [5200, 3200]
    }
    return pd.DataFrame(sample_data)

@st.cache_data(ttl=3600)
def fetch_shelter_data():
    """API에서 주민대피시설 데이터 가져오기"""
    api_configs = [
        {
            "url": "http://apis.data.go.kr/1741000/AirRaidShelterRegion",
            "key": "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ%2B6%2BZLqqvW6k%2FffQ5ZOOYzzcSo0Fq4u3Lfg%3D"
        }
    ]

    for config in api_configs:
        try:
            params = {
                "serviceKey": config["key"],
                "pageNo": 1,
                "numOfRows": 50,
                "type": "json"
            }

            response = requests.get(config["url"], params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return process_api_response(data)
        except Exception:
            continue

    return None

# 📊 메인 실행 함수
def main():
    st.markdown('<h1 class="main-header">🏠 주민대피시설 통계 대시보드</h1>', unsafe_allow_html=True)

    with st.spinner("🔄 데이터를 불러오는 중..."):
        raw_data = fetch_shelter_data()

    if raw_data is None:
        st.warning("API 호출 실패. 샘플 데이터를 사용합니다.")
        raw_data = create_sample_data()

    processed_data = process_shelter_data(raw_data)

    if processed_data is None:
        st.error("데이터 처리 실패")
        return

    st.write("✅ 데이터 샘플 미리보기")
    st.dataframe(processed_data.head())

if __name__ == "__main__":
    main()
