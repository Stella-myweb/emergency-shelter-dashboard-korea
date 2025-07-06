# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import urllib3

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="🏠 지역별 주민대피시설 통계 대시보드",
    layout="wide"
)

# Decoding된 일반 인증키

SERVICE_KEY = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="
@st.cache_data
def load_region_data(year: str) -> pd.DataFrame:
    """
    행안부 지역별 주민대피시설 통계(API) 호출 후 전처리.
    HTTP + verify=False로 SSL 에러 우회, JSON 구조에 안전하게 대응.
    """
    url = "http://apis.data.go.kr/1741000/AirRaidShelterRegion/getRestFrequentzoneFreezing"
    params = {
        "ServiceKey": SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": 100,
        "type": "json",
        "bas_yy": year
    }

    try:
        resp = requests.get(url, params=params, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        return pd.DataFrame()

    # 안전한 JSON 파싱
    body = data.get("response", {}).get("body", {})
    items_node = body.get("items", {})
    if isinstance(items_node, dict):
        # items가 dict인 경우 'item' 키에 실제 리스트가 들어있음
        items = items_node.get("item", [])
    else:
        # 이미 리스트 형태
        items = items_node

    df = pd.DataFrame(items)

    if df.empty or "regi" not in df.columns:
        # 컬럼 없거나 빈 DataFrame
        return pd.DataFrame()

    # 숫자형 컬럼 변환
    num_cols = [
        "target_popl", "accpt_rt", "shelt_abl_popl_smry",
        "shelt_abl_popl_gov_shelts", "shelt_abl_popl_pub_shelts",
        "gov_shelts_shelts", "gov_shelts_area",
        "pub_shelts_shelts", "pub_shelts_area"
    ]
    for c in num_cols:
        df[c] = (
            df[c].astype(str)
                 .str.replace(",", "")
                 .replace("", np.nan)
                 .astype(float)
        )

    # 'regi' 결측치 있는 행 제거
    df = df.dropna(subset=["regi"])
    return df

def main():
    st.title("🏠 지역별 주민대피시설 통계 대시보드")
    st.markdown(
        "기준년도별 지역별 대피시설 대상인구·수용률·시설 수·면적 통계를 제공합니다."
    )

    # 사이드바: 연도 선택 (2019~2025)
    years = [str(y) for y in range(2019, 2026)]
    year = st.sidebar.selectbox("📅 기준년도 선택", years)
    df = load_region_data(year)
    if df.empty:
        st.warning("데이터를 불러올 수 없습니다.\n(연도, API 키, 네트워크 설정을 확인하세요.)")
        st.stop()

    # 전국 요약 지표
    st.subheader("📌 전국 요약 지표")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 지역 개수", f"{len(df):,}")
    col2.metric("👥 대상 인구 합계", f"{int(df['target_popl'].sum()):,} 명")
    col3.metric("📈 평균 수용률", f"{df['accpt_rt'].mean():.1f}%")
    total_fac = df["gov_shelts_shelts"].sum() + df["pub_shelts_shelts"].sum()
    col4.metric("🏘️ 총 시설 수", f"{int(total_fac):,} 개")

    # 필터: 지역, 수용률 범위
    st.sidebar.header("🔍 필터")
    regions = ["전체"] + sorted(df["regi"].unique().tolist())
    sel_region = st.sidebar.selectbox("🌐 지역 선택", regions)
    if sel_region != "전체":
        df = df[df["regi"] == sel_region]

    rt_min, rt_max = st.sidebar.slider(
        "📊 수용률 범위 (%)", 0.0, 2000.0, (0.0, 500.0)
    )
    df = df[(df["accpt_rt"] >= rt_min) & (df["accpt_rt"] <= rt_max)]

    # 통계표
    st.subheader("📋 지역별 통계표")
    st.dataframe(
        df[[
            "regi", "target_popl", "accpt_rt",
            "shelt_abl_popl_smry", "gov_shelts_shelts",
            "pub_shelts_shelts", "gov_shelts_area",
            "pub_shelts_area"
        ]],
        use_container_width=True
    )

    # 수용률 Top/Bottom 10
    st.subheader("🔥 수용률 Top·Bottom 10")
    top10 = df.nlargest(10, "accpt_rt").assign(Group="Top10")
    bot10 = df.nsmallest(10, "accpt_rt").assign(Group="Bottom10")
    fig_tb = px.bar(
        pd.concat([top10, bot10]),
        x="regi", y="accpt_rt", color="Group",
        title="수용률 Top10 vs Bottom10", height=400
    )
    st.plotly_chart(fig_tb, use_container_width=True)

    # 대상인구 vs 대피 가능 인구
    st.subheader("📈 대상인구 vs 대피 가능 인구")
    df["util_rate"] = df["shelt_abl_popl_smry"] / df["target_popl"] * 100
    fig_sc = px.scatter(
        df, x="target_popl", y="shelt_abl_popl_smry",
        size="accpt_rt", color="util_rate",
        labels={
            "target_popl": "대상인구",
            "shelt_abl_popl_smry": "대피 가능 인구",
            "util_rate": "실제 수용률(%)"
        },
        title="대상인구 대비 실제 수용 인구"
    )
    st.plotly_chart(fig_sc, use_container_width=True)

    # 시설 수 vs 면적
    st.subheader("🏗️ 시설 수 vs 면적")
    df["total_shelts"] = df["gov_shelts_shelts"] + df["pub_shelts_shelts"]
    df["total_area"] = df["gov_shelts_area"] + df["pub_shelts_area"]
    fig_pa = px.scatter(
        df, x="total_shelts", y="total_area",
        size="target_popl", color="accpt_rt",
        labels={
            "total_shelts": "총 시설 수",
            "total_area": "총 면적(㎡)"
        },
        title="시설 수 대비 면적 규모"
    )
    st.plotly_chart(fig_pa, use_container_width=True)

    # 지역별 평균 수용률 히트맵
    st.subheader("🌡️ 지역별 평균 수용률 히트맵")
    heat = df.groupby("regi")["accpt_rt"].mean().reset_index()
    fig_hm = px.density_heatmap(
        heat, x="regi", y="accpt_rt",
        color_continuous_scale="RdYlGn", height=300
    )
    st.plotly_chart(fig_hm, use_container_width=True)

    # 실용 정보
    st.subheader("ℹ️ 참고 & 실용 정보")
    st.markdown(
        "- 비상연락처: [행정안전부 재난안전포털]"
        "(https://www.safekorea.go.kr)\n"
        "- 대피 행동매뉴얼: [행동매뉴얼 바로가기]"
        "(https://www.safekorea.go.kr/idsiSFK/neo/main/main.html)"
    )

if __name__ == "__main__":
    main()
