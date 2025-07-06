# -*- coding: utf-8 -*-
"""
행정안전부_통계연보_지역별 주민대피시설 통계 대시보드
— ’regi’ 컬럼 KeyError 해결판
"""
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import urllib3

# SSL 검증 비활성화 (HTTP 사용 시 불필요하지만 안전하게)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="🏠 지역별 주민대피시설 통계 대시보드",
    layout="wide"
)

# Decoding된 일반 인증키
SERVICE_KEY = (
    "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ"
    "+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="
)

@st.cache_data
def load_shelter_region(bas_yy: str) -> pd.DataFrame:
    """
    API 호출 후 JSON 구조를 안전하게 파싱하여 DataFrame 반환.
    ‘regi’ 컬럼이 누락될 때는 한글 컬럼명에 ‘지역’이 들어간 컬럼을 자동 맵핑합니다.
    """
    url = (
        "http://apis.data.go.kr/1741000/"
        "AirRaidShelterRegion/getAirRaidShelterRegionList"
    )
    params = {
        "ServiceKey": SERVICE_KEY,
        "pageNo":      1,
        "numOfRows": 1000,
        "type":     "json",
        "bas_yy":    bas_yy
    }

    try:
        resp = requests.get(url, params=params, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        return pd.DataFrame()

    # response → body → items 추출
    body       = data.get("response", {}).get("body", {})
    items_node = body.get("items", {})

    # items가 dict(item 리스트)인지, 바로 리스트인지 처리
    if isinstance(items_node, dict):
        items = items_node.get("item", [])
    elif isinstance(items_node, list):
        items = items_node
    else:
        items = []

    df = pd.DataFrame(items)
    if df.empty:
        return pd.DataFrame()

    # ‘regi’ 컬럼이 없으면 한글 컬럼명에서 ‘지역’ 키워드 찾기
    if "regi" not in df.columns:
        for col in df.columns:
            if "지역" in col:
                df = df.rename(columns={col: "regi"})
                break

    # 여전히 regi 없으면 빈 DF 반환
    if "regi" not in df.columns:
        return pd.DataFrame()

    # 숫자형 컬럼 리스트 정의
    num_cols = [
        "target_popl", "accpt_rt", "shelt_abl_popl_smry",
        "shelt_abl_popl_gov_shelts", "shelt_abl_popl_pub_shelts",
        "gov_shelts_shelts", "gov_shelts_area",
        "pub_shelts_shelts", "pub_shelts_area"
    ]
    # 천단위 콤마 제거 후 float 변환
    for c in num_cols:
        if c in df.columns:
            df[c] = (
                df[c].astype(str)
                     .str.replace(",", "")
                     .replace("", np.nan)
                     .astype(float)
            )

    # 지역명 결측치 행 제거
    df = df.dropna(subset=["regi"])
    return df

def main():
    st.title("🏠 지역별 주민대피시설 통계 대시보드")
    st.markdown(
        "기준년도별 지역별 대피시설 대상인구·수용률·시설 수·면적 통계를 제공합니다."
    )

    # 사이드바: 연도 선택 (2025 → 2019 역순)
    years = [str(y) for y in range(2025, 2018, -1)]
    year  = st.sidebar.selectbox("📅 기준년도 선택", years)
    df    = load_shelter_region(year)

    if df.empty:
        st.warning(
            "데이터를 불러올 수 없습니다.\n"
            "– API 키, 연도, 네트워크 설정을 확인하세요."
        )
        st.stop()

    # 전국 요약 지표
    st.subheader("📌 전국 요약 지표")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏢 지역 개수",          f"{len(df):,}")
    c2.metric("👥 대상 인구 총합",     f"{int(df['target_popl'].sum()):,} 명")
    c3.metric("📈 평균 수용률",       f"{df['accpt_rt'].mean():.1f}%")
    total_fac = df["gov_shelts_shelts"].sum() + df["pub_shelts_shelts"].sum()
    c4.metric("🏘️ 총 시설 수",       f"{int(total_fac):,} 개")

    # 필터: 지역, 수용률 범위
    st.sidebar.header("🔍 필터")
    regions = ["전체"] + sorted(df["regi"].unique().tolist())
    sel     = st.sidebar.selectbox("🌐 지역 선택", regions)
    if sel != "전체":
        df = df[df["regi"] == sel]

    rt_min, rt_max = st.sidebar.slider(
        "📊 수용률 범위 (%)", 0.0, 2000.0, (0.0, 500.0)
    )
    df = df[(df["accpt_rt"] >= rt_min) & (df["accpt_rt"] <= rt_max)]

    # 지역별 통계표
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

    # 수용률 Top·Bottom 10
    st.subheader("🔥 수용률 Top10 vs Bottom10")
    top10 = df.nlargest(10, "accpt_rt").assign(Group="Top10")
    bot10 = df.nsmallest(10, "accpt_rt").assign(Group="Bottom10")
    fig_tb = px.bar(
        pd.concat([top10, bot10]),
        x="regi", y="accpt_rt", color="Group",
        title="수용률 Top10 · Bottom10 비교", height=400
    )
    st.plotly_chart(fig_tb, use_container_width=True)

    # 대상인구 vs 대피 가능 인구 산점도
    st.subheader("📈 대상인구 vs 대피 가능 인구")
    df["util_rate"] = df["shelt_abl_popl_smry"] / df["target_popl"] * 100
    fig_sc = px.scatter(
        df, x="target_popl", y="shelt_abl_popl_smry",
        size="accpt_rt", color="util_rate",
        labels={
            "target_popl":        "대상인구",
            "shelt_abl_popl_smry":"대피 가능 인구",
            "util_rate":          "실제 수용률(%)"
        },
        title="대상인구 대비 실제 수용 인구"
    )
    st.plotly_chart(fig_sc, use_container_width=True)

    # 시설 수 vs 면적 산점도
    st.subheader("🏗️ 시설 수 vs 면적")
    df["total_shelts"] = df["gov_shelts_shelts"] + df["pub_shelts_shelts"]
    df["total_area"]   = df["gov_shelts_area"]   + df["pub_shelts_area"]
    fig_pa = px.scatter(
        df, x="total_shelts", y="total_area",
        size="target_popl", color="accpt_rt",
        labels={
            "total_shelts":"총 시설 수",
            "total_area":  "총 면적(㎡)"
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

    # 실용 정보 & 링크
    st.subheader("ℹ️ 참고 링크 & 실용 정보")
    st.markdown(
        "- 비상연락처: [행정안전부 재난안전포털]"
        "(https://www.safekorea.go.kr)\n"
        "- 대피 행동매뉴얼: [행동매뉴얼 바로가기]"
        "(https://www.safekorea.go.kr/idsiSFK/neo/main/main.html)"
    )

if __name__ == "__main__":
    main()
