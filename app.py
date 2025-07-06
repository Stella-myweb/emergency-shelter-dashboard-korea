import requests
import json
from urllib.parse import unquote
import urllib3

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SERVICE_KEY
SERVICE_KEY = "jUxxEMTFyxsIT2rt2P8JBO9y0EmFT9mx1zNPb31XLX27rFNH12NQ+6+ZLqqvW6k/ffQ5ZOOYzzcSo0Fq4u3Lfg=="

def test_api():
    """API 테스트 함수"""
    
    print("🔍 API 테스트 시작...")
    print(f"📅 인증키: {SERVICE_KEY[:20]}...")
    
    # 인증키 디코딩
    decoded_key = unquote(SERVICE_KEY)
    print(f"🔓 디코딩된 키: {decoded_key[:20]}...")
    
    # API URL
    url = "http://apis.data.go.kr/1741000/AirRaidShelterRegion/getAirRaidShelterRegionList"
    
    # 파라미터 (2019년 데이터로 테스트 - 확실히 존재하는 데이터)
    params = {
        'ServiceKey': decoded_key,
        'pageNo': 1,
        'numOfRows': 3,  # 작은 수로 테스트
        'type': 'json',
        'bas_yy': 2019
    }
    
    print(f"🌐 API URL: {url}")
    print(f"📋 파라미터: {params}")
    print()
    
    try:
        print("📡 API 호출 중...")
        response = requests.get(url, params=params, verify=False, timeout=10)
        
        print(f"📊 응답 코드: {response.status_code}")
        print(f"📄 응답 헤더: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            print("✅ API 호출 성공!")
            
            # 응답 내용 확인
            content_type = response.headers.get('content-type', '')
            print(f"📝 응답 타입: {content_type}")
            
            # 응답 내용 출력
            response_text = response.text
            print(f"📋 응답 길이: {len(response_text)} 문자")
            print()
            print("📄 응답 내용 (처음 1000자):")
            print("-" * 50)
            print(response_text[:1000])
            print("-" * 50)
            print()
            
            # JSON 파싱 시도
            try:
                data = response.json()
                print("✅ JSON 파싱 성공!")
                print(f"📊 JSON 구조: {list(data.keys()) if isinstance(data, dict) else 'List 형태'}")
                
                # response 키 확인
                if 'response' in data:
                    response_data = data['response']
                    print(f"📋 response 키: {list(response_data.keys())}")
                    
                    # header 확인
                    if 'header' in response_data:
                        header = response_data['header']
                        print(f"📊 header: {header}")
                        
                        result_code = header.get('resultCode', '')
                        result_msg = header.get('resultMsg', '')
                        print(f"🔍 결과 코드: {result_code}")
                        print(f"💬 결과 메시지: {result_msg}")
                    
                    # body 확인
                    if 'body' in response_data:
                        body = response_data['body']
                        print(f"📋 body 키: {list(body.keys()) if isinstance(body, dict) else 'body 형태 확인 필요'}")
                        
                        # items 확인
                        if 'items' in body:
                            items = body['items']
                            print(f"📊 items 타입: {type(items)}")
                            print(f"📊 items 내용: {items}")
                            
                            if isinstance(items, dict) and 'item' in items:
                                item_list = items['item']
                                print(f"✅ item 리스트 발견! 길이: {len(item_list) if isinstance(item_list, list) else '단일 아이템'}")
                                if isinstance(item_list, list) and len(item_list) > 0:
                                    print(f"📋 첫 번째 아이템 키: {list(item_list[0].keys())}")
                            elif isinstance(items, list):
                                print(f"✅ items가 직접 리스트! 길이: {len(items)}")
                                if len(items) > 0:
                                    print(f"📋 첫 번째 아이템 키: {list(items[0].keys())}")
                        else:
                            print("❌ items 키가 없습니다.")
                    else:
                        print("❌ body 키가 없습니다.")
                else:
                    print("❌ response 키가 없습니다.")
                    print(f"📊 실제 키들: {list(data.keys())}")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON 파싱 실패: {e}")
                print("🔍 XML 응답일 가능성이 있습니다.")
                
        else:
            print(f"❌ API 호출 실패! 상태 코드: {response.status_code}")
            print(f"📄 에러 내용: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 실패: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

if __name__ == "__main__":
    test_api()
