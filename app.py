# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="주민대피시설 통계 대시보드",
    page_icon="🏠",
    layout="wide"
)

# 스타일
st.markdown("<h1 style='text-align: center; color: black;'>🏠 주민대피시설 통계 대시보드</h1>", unsafe_allow_html=True)

# 샘플 데이터 (API 대체)
@st.cache_data
def load_data():
    data = pd.DataFrame({
        'regi': ['서울특별시 종로구', '부산광역시 중구'],
        'lat': [37.572, 35.105],
        'lon': [126.976, 129.033],
        'target_popl': [45000, 31000],
        'shell_abl_popl_smry': [52000, 28000],
        'gov_shells_shells': [12, 7],
        'gov_shells_area': [8500, 4800],
        'pub_shells_shells': [8, 5],
        'pub_shells_area': [5200, 3200]
    })
    data["accpt_rt"] = (data["shell_abl_popl_smry"] / data["target_popl"]) * 100
    data["capacity_level"] = pd.cut(data["accpt_rt"], bins=[0, 50, 80, 100, float("inf")],
                                     labels=["부족", "보통", "양호", "충분"])
    data["total_facilities"] = data["gov_shells_shells"] + data["pub_shells_shells"]
    data["total_area"] = data["gov_shells_area"] + data["pub_shells_area"]
    return data

df = load_data()

# 사이드바 필터
st.sidebar.header("🔍 필터 옵션")
regions = ["전체"] + sorted(df["regi"].unique().tolist())
selected_region = st.sidebar.selectbox("지역 선택", regions)

min_rt, max_rt = st.sidebar.slider("수용률 범위 (%)", 0, 200, (0, 200))
filtered_df = df.copy()

if selected_region != "전체":
    filtered_df = filtered_df[filtered_df["regi"] == selected_region]
filtered_df = filtered_df[(filtered_df["accpt_rt"] >= min_rt) & (filtered_df["accpt_rt"] <= max_rt)]

# ✅ 요약 통계 카드
st.markdown("## 📊 주요 통계")
col1, col2, col3, col4 = st.columns(4)
col1.metric("총 지역 수", f"{len(filtered_df)}개")
col2.metric("총 대피시설 수", f"{filtered_df['total_facilities'].sum():,}개")
col3.metric("전국 평균 수용률", f"{filtered_df['accpt_rt'].mean():.1f}%")
col4.metric("총 대상 인구", f"{filtered_df['target_popl'].sum():,}명")

# 🗺️ 지도 시각화
st.markdown("## 🗺️ 지역별 대피시설 지도")
m = folium.Map(location=[36.5, 127.9], zoom_start=6)

color_map = {
    "부족": "red",
    "보통": "orange",
    "양호": "yellow",
    "충분": "green"
}

for _, row in filtered_df.iterrows():
    popup_text = f"""
    <b>{row['regi']}</b><br>
    대상 인구: {row['target_popl']}명<br>
    수용 가능: {row['shell_abl_popl_smry']}명<br>
    수용률: {row['accpt_rt']:.1f}%
    """
    folium.CircleMarker(
        location=(row["lat"], row["lon"]),
        radius=10,
        color=color_map[row["capacity_level"]],
        fill=True,
        fill_opacity=0.7,
        popup=popup_text
    ).add_to(m)

st_folium(m, width=900)

# 수용률 분포 히트맵
st.markdown("## 🔥 수용률 등급별 지역 분포")
fig = px.histogram(filtered_df, x="capacity_level", color="capacity_level",
                   color_discrete_map=color_map,
                   labels={"capacity_level": "수용률 등급"}, title="수용률 분포")
st.plotly_chart(fig, use_container_width=True)

# 상세 분석
st.markdown("## 🔍 지역별 상세 분석")
col5, col6 = st.columns(2)

with col5:
    st.subheader("🔴 수용률 부족 지역 Top 10")
    low_df = filtered_df.nsmallest(10, "accpt_rt")[["regi", "accpt_rt", "target_popl", "shell_abl_popl_smry"]]
    st.dataframe(low_df.rename(columns={"regi": "지역", "accpt_rt": "수용률(%)", 
                                        "target_popl": "대상인구", "shell_abl_popl_smry": "수용가능"}))

with col6:
    st.subheader("🟢 수용률 우수 지역 Top 10")
    high_df = filtered_df.nlargest(10, "accpt_rt")[["regi", "accpt_rt", "target_popl", "shell_abl_popl_smry"]]
    st.dataframe(high_df.rename(columns={"regi": "지역", "accpt_rt": "수용률(%)", 
                                         "target_popl": "대상인구", "shell_abl_popl_smry": "수용가능"}))

# 비상연락처 및 대피요령
st.markdown("## 🚨 비상연락처 및 대피요령")
col7, col8 = st.columns(2)

with col7:
    st.markdown("""
    **📞 비상연락처**
    - 종합상황실: 119  
    - 경찰서: 112  
    - 소방서: 119  
    - 군부대/구청: 지역별 상이
    """)

with col8:
    st.markdown("""
    **🏃 대피요령**
    1. 경보 발령 시 즉시 대피  
    2. 가까운 대피시설로 이동  
    3. 신분증 및 생필품 지참  
    4. 질서 있게 이동  
    5. 시설 내 안전 수칙 준수  
    """)

st.markdown("---")
st.markdown("<div style='text-align: center; font-size: 0.9em;'>📊 데이터 출처: 공공데이터포털 | ⏱️ 자동 갱신 예정</div>", unsafe_allow_html=True)
