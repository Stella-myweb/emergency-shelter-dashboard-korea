# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

st.set_page_config(page_title="🏠 주민대피시설 통계 대시보드", layout="wide")

# ✅ Decoding된 일반 인증키
service_key = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="

@st.cache_data
def load_shelter_data(year="2019"):
    """주민대피시설 통계 API 데이터 로드"""
    url = "http://apis.data.go.kr/1741000/ShelterInfoOpenApi/getShelterInfo"
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 1000,
        "type": "json",
        "bas_yy": year,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        items = data.get("response", {}).get("body", {}).get("items", [])
        df = pd.DataFrame(items)

        # 수치형 변환 및 정리
        num_cols = ["accept_rt", "target_popl", "shelt_abl_popl_smry", "lat", "lon", "tot_area"]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        df = df.dropna(subset=["lat", "lon", "accept_rt"])

        return df
    except Exception as e:
        st.error(f"❌ API 호출 실패: {e}")
        return None

# 🎯 앱 타이틀
st.title("🏠 주민대피시설 통계 대시보드")
st.markdown("**행정안전부 제공 데이터를 활용하여 지역별 대피시설의 수용률과 분포를 시각화합니다.**")

# 📦 데이터 불러오기
with st.spinner("📡 대피시설 데이터를 불러오는 중입니다..."):
    df = load_shelter_data()

if df is None or df.empty:
    st.warning("데이터를 불러올 수 없습니다.")
    st.stop()

# 📊 요약 지표
st.subheader("📌 전국 통계 요약")
col1, col2, col3 = st.columns(3)
col1.metric("🏢 총 대피시설 수", len(df))
col2.metric("👥 대상 인구 총합", f"{int(df['target_popl'].sum()):,} 명")
col3.metric("📈 평균 수용률", f"{df['accept_rt'].mean():.1f}%")

# 🎛️ 필터
st.sidebar.header("🔍 지역 필터")
sido_options = ["전체"] + sorted(df["regi"].dropna().unique())
selected_sido = st.sidebar.selectbox("시도 선택", sido_options)

if selected_sido != "전체":
    df = df[df["regi"] == selected_sido]

rt_range = st.sidebar.slider("수용률 범위 설정 (%)", 0.0, 500.0, (0.0, 300.0))
df = df[(df["accept_rt"] >= rt_range[0]) & (df["accept_rt"] <= rt_range[1])]

# 🗺️ 지도 시각화
st.subheader("🗺️ 대피시설 지도")
color_map = df["accept_rt"].apply(
    lambda x: "🔴 부족" if x < 100 else "🟡 보통" if x < 300 else "🟢 충분"
)

fig = px.scatter_mapbox(
    df,
    lat="lat",
    lon="lon",
    color=color_map,
    hover_data=["orgnm", "target_popl", "shelt_abl_popl_smry", "accept_rt"],
    zoom=5,
    height=500
)
fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig, use_container_width=True)

# 🔥 수용률 낮은 지역 Top 10
st.subheader("🔥 수용률 낮은 대피시설 Top 10")
low_top10 = df.sort_values(by="accept_rt").head(10)
st.dataframe(low_top10[["regi", "orgnm", "target_popl", "shelt_abl_popl_smry", "accept_rt"]])

# 🌡️ 히트맵 (시도별 평균 수용률)
st.subheader("🌡️ 시도별 평균 수용률 히트맵")
heat_df = df.groupby("regi")["accept_rt"].mean().reset_index()
fig2 = px.density_heatmap(heat_df, x="regi", y="accept_rt", color_continuous_scale="RdYlGn", height=300)
st.plotly_chart(fig2, use_container_width=True)

# 📊 면적 대비 효율 분석
if "tot_area" in df.columns and df["tot_area"].notna().sum() > 0:
    st.subheader("📐 시설면적 대비 수용 가능 인구")
    df["면적당_인구수용력"] = df["shelt_abl_popl_smry"] / df["tot_area"]
    top_eff = df[df["면적당_인구수용력"].notna()].sort_values(by="면적당_인구수용력", ascending=False).head(10)
    st.dataframe(top_eff[["regi", "orgnm", "tot_area", "shelt_abl_popl_smry", "면적당_인구수용력"]])

# ℹ️ 실용 정보
st.subheader("ℹ️ 실용 정보 안내")
st.markdown("""
- **내 지역 대피소 위치 확인**: 지도에서 시도 필터로 확인 가능
- **가장 가까운 대피소 거리 계산**: 향후 업데이트 예정
- **비상연락처 및 대피요령**: [행안부 재난안전포털](https://www.safekorea.go.kr)
- **대피 행동요령**: [행동매뉴얼 바로가기](https://www.safekorea.go.kr/idsiSFK/neo/main/main.html)
""")
