# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

st.set_page_config(
    page_title="🏠 지역별 주민대피시설 통계 대시보드",
    layout="wide"
)

# Decoding된 일반 인증키
SERVICE_KEY = (
    "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="
)

@st.cache_data
def load_region_data(year: str) -> pd.DataFrame:
    """
    행안부 지역별 주민대피시설 통계(API) 호출 후 전처리.
    """
    url = "https://apis.data.go.kr/1741000/AirRaidShelterRegion/getAirRaidShelterRegionList"
    params = {
        "ServiceKey": SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": 100,
        "type": "json",
        "bas_yy": year
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        items = r.json()["response"]["body"]["items"]
        df = pd.DataFrame(items)
    except Exception as e:
        st.error(f"API 호출 오류: {e}")
        return pd.DataFrame()

    # 숫자 형 변환
    nums = [
        "target_popl", "accpt_rt", "shelt_abl_popl_smry",
        "shelt_abl_popl_gov_shelts", "shelt_abl_popl_pub_shelts",
        "gov_shelts_shelts", "gov_shelts_area",
        "pub_shelts_shelts", "pub_shelts_area"
    ]
    for c in nums:
        if c in df:
            df[c] = (
                df[c].astype(str)
                      .str.replace(",", "")
                      .replace("", np.nan)
                      .astype(float)
            )
    return df.dropna(subset=["regi"])

def main():
    st.title("🏠 지역별 주민대피시설 통계 대시보드")
    st.markdown("기준년도별 지역별 대피시설 대상인구·수용률·시설 수·면적 통계를 제공합니다.")

    # 사이드바: 연도 선택, 필터
    year = st.sidebar.selectbox("📅 기준년도 선택", [str(y) for y in range(2019, 2026)])
    df = load_region_data(year)
    if df.empty:
        st.stop()

    st.subheader("📌 전국 요약 지표")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏢 지역 개수", f"{len(df):,}")
    c2.metric("👥 대상 인구 합계", f"{int(df['target_popl'].sum()):,} 명")
    c3.metric("📈 평균 수용률", f"{df['accpt_rt'].mean():.1f}%")
    total_fac = df["gov_shelts_shelts"].sum() + df["pub_shelts_shelts"].sum()
    c4.metric("🏘️ 총 시설 수", f"{int(total_fac):,} 개")

    # 필터: 지역, 수용률 범위
    regions = ["전체"] + sorted(df["regi"].unique().tolist())
    sel = st.sidebar.selectbox("🌐 지역 선택", regions)
    if sel != "전체":
        df = df[df["regi"] == sel]

    rt_min, rt_max = st.sidebar.slider("📊 수용률 범위 (%)", 0.0, 1000.0,
                                       (0.0, 500.0))
    df = df[(df["accpt_rt"] >= rt_min) & (df["accpt_rt"] <= rt_max)]

    # 테이블
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

    # 차트1: 수용률 Top/Bottom 10
    st.subheader("🔥 수용률 Top·Bottom 10")
    top10 = df.nlargest(10, "accpt_rt")
    bot10 = df.nsmallest(10, "accpt_rt")
    fig_tb = px.bar(
        pd.concat([top10.assign(Group="Top10"), bot10.assign(Group="Bottom10")]),
        x="regi", y="accpt_rt", color="Group",
        title="수용률 Top10·Bottom10 비교",
        height=400
    )
    st.plotly_chart(fig_tb, use_container_width=True)

    # 차트2: 대상인구 vs 수용 가능 인구
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

    # 차트3: 시설 수 대비 면적
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

    # 히트맵: 지역별 평균 수용률
    st.subheader("🌡️ 지역별 평균 수용률 히트맵")
    heat = df.groupby("regi")["accpt_rt"].mean().reset_index()
    fig_hm = px.density_heatmap(
        heat, x="regi", y="accpt_rt",
        color_continuous_scale="RdYlGn", height=300
    )
    st.plotly_chart(fig_hm, use_container_width=True)

    # 실용 정보
    st.subheader("ℹ️ 참고 & 실용 정보")
    st.markdown("""
    - 비상연락처 및 행동요령: [행정안전부 재난안전포털](https://www.safekorea.go.kr)
    - 대피 행동매뉴얼: [행동매뉴얼 바로가기](https://www.safekorea.go.kr/idsiSFK/neo/main/main.html)
    """)

if __name__ == "__main__":
    main()
