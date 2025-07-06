import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

# -------------------------------
# 🔐 API 설정
# -------------------------------
API_KEY = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="
API_URL = f"http://apis.data.go.kr/1741000/EmergencyShelter2/getEmergencyShelterList2?serviceKey={API_KEY}&pageNo=1&numOfRows=1000&type=json"

# -------------------------------
# 🧹 수용률 계산 함수
# -------------------------------
def compute_acceptance_rate(row):
    try:
        return round((int(row["shel_av"])/int(row["peop_cnt"]))*100, 1)
    except:
        return None

# -------------------------------
# 📡 API 호출 함수
# -------------------------------
@st.cache_data(ttl=3600)
def fetch_data():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data['EmergencyShelter'][1:])  # [0]은 메타 정보
            df["shel_av"] = df["shel_av"].astype(int)
            df["peop_cnt"] = df["peop_cnt"].astype(int)
            df["acceptance_rate"] = df.apply(compute_acceptance_rate, axis=1)
            df["lat"] = df["lat"].astype(float)
            df["lon"] = df["lon"].astype(float)
            return df
        else:
            st.warning("❌ API 호출 실패, 샘플 데이터를 사용합니다.")
            return None
    except Exception as e:
        st.error(f"API 연동 중 오류 발생: {e}")
        return None

# -------------------------------
# 🎨 지도 생성 함수
# -------------------------------
def create_map(df):
    m = folium.Map(location=[36.5, 127.8], zoom_start=7)
    for _, row in df.iterrows():
        rate = row["acceptance_rate"]
        color = "green" if rate >= 100 else "orange" if rate >= 70 else "red"
        popup_text = f"""
        📍 {row['shel_nm']}<br>
        📌 {row['address']}<br>
        👥 대상 인구: {row['peop_cnt']}명<br>
        🛏️ 수용 가능 인원: {row['shel_av']}명<br>
        📊 수용률: {rate}%
        """
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=popup_text
        ).add_to(m)
    return m

# -------------------------------
# 🖼️ Streamlit UI 시작
# -------------------------------
st.set_page_config(page_title="주민대피시설 통계 대시보드", layout="wide")
st.title("🏠 주민대피시설 통계 대시보드")

# 데이터 불러오기
data = fetch_data()

if data is not None:
    # 지역 필터링
    regions = data["sido"].dropna().unique().tolist()
    selected_region = st.sidebar.selectbox("📍 시도 선택", ["전체"] + regions)

    if selected_region != "전체":
        filtered_data = data[data["sido"] == selected_region]
    else:
        filtered_data = data

    # 지도 시각화
    st.subheader("🗺️ 대피시설 지도 보기")
    folium_map = create_map(filtered_data)
    st_folium(folium_map, width=1000, height=600)

    # 요약 통계
    st.subheader("📊 통계 요약")
    col1, col2, col3 = st.columns(3)
    col1.metric("🧍‍ 인구 총합", f"{filtered_data['peop_cnt'].sum():,} 명")
    col2.metric("🛌 수용 가능 인원", f"{filtered_data['shel_av'].sum():,} 명")
    col3.metric("📈 평균 수용률", f"{filtered_data['acceptance_rate'].mean():.1f}%")

    # 데이터 미리보기
    with st.expander("🔎 데이터 미리보기"):
        st.dataframe(filtered_data[["sido", "gugun", "shel_nm", "peop_cnt", "shel_av", "acceptance_rate", "address"]])
else:
    st.warning("API 연동에 실패하여 대체 데이터를 사용할 수 없습니다.")
