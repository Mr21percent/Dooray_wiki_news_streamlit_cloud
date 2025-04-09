import streamlit as st
import os
import json
from dooray_api_client import DoorayAPIClient

st.title("Dooray! Wiki News 설정 페이지")


# ----- 사용자 관련 함수 -----
def get_user_names(secrets_dict):
    """st.secrets에서 사용자 이름 리스트를 추출합니다."""
    return [user["name"] for user in secrets_dict.values()]


def get_selected_user(secrets_dict, selected_name):
    """선택한 이름에 해당하는 사용자 정보를 반환합니다."""
    for user in secrets_dict.values():
        if user["name"] == selected_name:
            return user
    return None


# ----- 위키/페이지 데이터 관련 함수 -----
def load_wiki_data(client):
    """
    Dooray API를 통해 위키 목록을 가져온 후,
    선택한 위키에서 최상위 페이지와 하위 페이지 정보를 로드합니다.
    
    반환값:
        - selected_wiki_id: 선택한 위키의 ID
        - selected_page_id: 선택한 페이지의 ID
        - selected_page_title: 선택한 페이지의 제목
    """
    # 위키 목록 로드 및 체크
    wikis = client.get_wikis()
    if not wikis.get("result"):
        st.error("사용 가능한 위키가 없습니다.")
        st.stop()

    # 위키 제목 및 ID 매핑
    wiki_titles = [wiki["name"] for wiki in wikis["result"]]
    wiki_ids = {wiki["name"]: wiki["id"] for wiki in wikis["result"]}
    
    # 위키 선택: 드롭다운 메뉴 제공
    selected_wiki_title = st.selectbox("Select a Project", wiki_titles)
    selected_wiki_id = wiki_ids[selected_wiki_title]

    # 최상위 페이지 불러오기
    top_pages = client.get_wiki_pages(wiki_id=selected_wiki_id)
    if len(top_pages.get("result", [])) != 1:
        st.error("최상위 페이지를 찾을 수 없습니다.")
        st.stop()
    top_page = top_pages["result"][0]
    top_page_title = top_page["subject"]
    top_page_id = top_page["id"]

    # 하위 페이지 불러오기
    sub_pages_data = client.get_wiki_pages(wiki_id=selected_wiki_id, parentPageId=top_page_id)
    sub_page_titles = [page["subject"] for page in sub_pages_data.get("result", [])]

    # 최상위와 하위 페이지를 포함한 드롭다운 메뉴 생성
    all_page_titles = [top_page_title] + [f"{top_page_title} > {sub_title}" for sub_title in sub_page_titles]
    selected_page_title = st.selectbox("Select a Parent Wiki Page", all_page_titles)

    # 선택한 페이지의 ID 추출
    if selected_page_title == top_page_title:
        return selected_wiki_id, top_page_id, top_page_title
    else:
        selected_sub_title = selected_page_title.split(" > ")[-1]
        selected_page = next((page for page in sub_pages_data.get("result", [])
                              if page["subject"] == selected_sub_title), None)
        if selected_page is None:
            st.error("선택한 하위 페이지를 찾을 수 없습니다.")
            st.stop()
        return selected_wiki_id, selected_page["id"], selected_page["subject"]


# ----- 설정 저장 관련 함수 -----
def save_setting(selected_data, setting_name, folder="task_list"):
    """
    설정 데이터(selected_data)를 JSON 파일로 저장합니다.
    파일은 지정한 폴더 (기본 "task_list")에 setting_name을 이용해 생성합니다.
    """
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f'{setting_name}_data.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(selected_data, f, ensure_ascii=False, indent=4)
    return file_path


# ----- 메인 실행 흐름 -----
# st.secrets에서 사용자 정보 불러오기
st.subheader("어떤 페이지에 연동할지 선택하세요.")
users = st.secrets
if not users:
    st.error("Secrets가 로드되지 않았습니다. .streamlit/secrets.toml 파일을 확인하세요.")
    st.stop()

# 사용자 이름 선택
user_names = get_user_names(users)
selected_name = st.selectbox("사용자 이름을 선택하세요:", user_names)

# 선택한 사용자 정보 확인
selected_user = get_selected_user(users, selected_name)
if not selected_user or not selected_user.get("Dooray_token"):
    st.error("선택한 사용자의 Dooray_token 정보가 없습니다.")
    st.stop()
dooray_token = selected_user["Dooray_token"]

# Dooray API 클라이언트 초기화 및 위키 데이터 로드
try:
    client = DoorayAPIClient(token=dooray_token)
    selected_wiki_id, selected_page_id, selected_page_title = load_wiki_data(client)
    # (선택된 위키 정보는 UI에 노출할 필요에 따라 주석 해제 가능)
    # st.write("선택한 위키 ID:", selected_wiki_id)
    # st.write("선택한 페이지 ID:", selected_page_id)
    # st.write("선택한 페이지 제목:", selected_page_title)
except Exception as e:
    st.error(f"API 호출 중 에러 발생: {str(e)}")
    st.stop()

# ----- 검색어 입력 및 설정 저장 UI -----
st.subheader("어떤 검색어로 검색할지 입력하세요.")

# 링크 버튼: st.link_button이 제공되지 않을 경우 markdown 링크 사용
if hasattr(st, "link_button"):
    st.link_button("네이버_상세검색_가이드", "https://help.naver.com/service/5626/contents/959?lang=ko")
else:
    st.markdown("[네이버_상세검색_가이드](https://help.naver.com/service/5626/contents/959?lang=ko)")

naver_news_search_term = st.text_input("네이버 뉴스 검색 연산자를 입력하세요", key="naver_news_search_term")

# GPT 활용 여부 체크박스 및 프롬프트 입력
use_gpt = st.checkbox("GPT 활용하기", key="use_gpt")
gpt_prompt = ""
if use_gpt:
    gpt_prompt = st.text_area(" 본문을 요약하기 위한 GPT 프롬프트를 입력하세요", key="gpt_prompt")

if naver_news_search_term:
    setting_name = st.text_input("세팅 명을 입력하세요", key="setting_name")
    
    if st.button("저장"):
        try:
            # 저장할 데이터 구성 (선택한 사용자 이름과 GPT 프롬프트 포함)
            selected_data = {
                "user_name": selected_name,
                "wiki_id": selected_wiki_id,
                "page_id": selected_page_id,
                "page_title": selected_page_title,
                "naver_news_search_term": naver_news_search_term,
                "use_gpt": use_gpt,
                "gpt_prompt": gpt_prompt
            }
            saved_path = save_setting(selected_data, setting_name, folder="task_list")
            st.success(f"세팅이 저장되었습니다. 파일 경로: {saved_path}")
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {str(e)}")
else:
    st.info("뉴스 검색 연산자를 먼저 입력해주세요.")
