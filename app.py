# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

st.set_page_config(
    page_title="🏠 주민대피시설 통계 대시보드",
    layout="wide",
)

# ─── 환경설정 ──────────────────────────────────────────────────────────────

# Decoding된 일반 인증키
SERVICE_KEY = (
    "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ"
    "+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="
)


@st.cache_data
def load_shelter_data(year: str = "2019") -> pd.DataFrame:
    """
    행정안전부 주민대피시설 API에서 데이터를 불러와 전처리하여 반환합니다.
    실패 시 빈 DataFrame 반환.
    """
    url = "http://apis.data.go.kr/1741000/ShelterInfoOpenApi/getShelterInfo"
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": 1000,
        "type": "json",
        "bas_yy": year,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", [])
        df = pd.DataFrame(items)

        # 주요 컬럼 수치형 변환
        numeric_cols = [
            "accept_rt",            # 수용률 (%)
            "target_popl",          # 대상 인구
            "shelt_abl_popl_smry",  # 수용 가능 인구
            "lat", "lon",           # 위도·경도
            "tot_area",             # 총 면적 (㎡)
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",", "")
                    .replace("", np.nan)
                    .astype(float)
                )

        # 필수 정보가 없는 행 제거
        df = df.dropna(subset=["lat", "lon", "accept_rt"])
        return df

    except Exception as e:
        st.error(f"❌ API 호출 오류: {e}")
        return pd.DataFrame()


def main():
    # ─── 사이드바 & 제목 ────────────────────────────────────────────────
    st.title("🏠 주민대피시설 통계 대시보드")
    st.markdown(
        "행정안전부 제공 주민대피시설 데이터를 기반으로 "
        "지역별 수용률과 분포를 시각화합니다."
    )
    st.sidebar.header("🔍 필터")

    # ─── 데이터 로드 ────────────────────────────────────────────────────
    year = st.sidebar.selectbox("연도 선택", ["2019", "2020", "2021", "2022", "2023"])
    with st.spinner("데이터를 불러오는 중..."):
        df = load_shelter_data(year)

    if df.empty:
        st.warning("데이터가 없습니다. API나 연도를 확인하세요.")
        st.stop()

    # ─── 요약 지표 ────────────────────────────────────────────────────
    st.subheader("📌 전국 요약 지표")
    col1, col2, col3 = st.columns(3)
    col1.metric("🏢 총 대피시설 수", f"{len(df):,} 개")
    col2.metric("👥 대상 인구 총합", f"{int(df['target_popl'].sum()):,} 명")
    col3.metric("📈 평균 수용률", f"{df['accept_rt'].mean():.1f}%")

    # ─── 지역 필터 ────────────────────────────────────────────────────
    sido_list = ["전체"] + sorted(df["regi"].dropna().unique().tolist())
    selected_sido = st.sidebar.selectbox("시도 선택", sido_list)
    if selected_sido != "전체":
        df = df[df["regi"] == selected_sido]

    rt_min, rt_max = st.sidebar.slider(
        "수용률 범위 (%)", 0.0, 500.0, (0.0, 300.0)
    )
    df = df[(df["accept_rt"] >= rt_min) & (df["accept_rt"] <= rt_max)]

    # ─── 지도 시각화 ───────────────────────────────────────────────────
    st.subheader("🗺️ 대피시설 분포 지도")
    df["status"] = df["accept_rt"].apply(
        lambda x: "🔴 부족" if x < 100 else "🟡 보통" if x < 300 else "🟢 충분"
    )
    fig_map = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lon",
        color="status",
        hover_data=["orgnm", "target_popl", "shelt_abl_popl_smry", "accept_rt"],
        zoom=5,
        height=500,
    )
    fig_map.update_layout(mapbox_style="carto-positron", margin={"l":0,"r":0,"t":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)

    # ─── Top 10 수용률 낮은 대피시설 ────────────────────────────────────
    st.subheader("🔥 수용률 낮은 대피시설 Top 10")
    low10 = df.nsmallest(10, "accept_rt")
    st.dataframe(
        low10[["regi", "orgnm", "target_popl", "shelt_abl_popl_smry", "accept_rt"]],
        use_container_width=True,
    )

    # ─── 시도별 평균 수용률 히트맵 ────────────────────────────────────────
    st.subheader("🌡️ 시도별 평균 수용률 히트맵")
    heat = df.groupby("regi")["accept_rt"].mean().reset_index()
    fig_heat = px.density_heatmap(
        heat, x="regi", y="accept_rt",
        color_continuous_scale="RdYlGn",
        height=300,
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # ─── 면적 대비 수용 효율 ────────────────────────────────────────────
    if "tot_area" in df.columns and df["tot_area"].notna().any():
        st.subheader("📐 면적 대비 수용 가능 인구 효율 Top 10")
        df["efficiency"] = df["shelt_abl_popl_smry"] / df["tot_area"]
        eff10 = df.nlargest(10, "efficiency")
        st.dataframe(
            eff10[["regi", "orgnm", "tot_area", "shelt_abl_popl_smry", "efficiency"]],
            use_container_width=True,
        )

    # ─── 실용 정보 ────────────────────────────────────────────────────
    st.subheader("ℹ️ 실용 정보 및 참고 링크")
    st.markdown(
        "- 내 지역 대피시설 위치: 지도에서 시도 필터로 찾을 수 있습니다.\n"
        "- 비상연락처 및 행동요령: [행정안전부 재난안전포털]"
        "(https://www.safekorea.go.kr)\n"
        "- 대피 행동매뉴얼: [행동매뉴얼 바로가기]"
        "(https://www.safekorea.go.kr/idsiSFK/neo/main/main.html)"
    )


if __name__ == "__main__":
    main()
