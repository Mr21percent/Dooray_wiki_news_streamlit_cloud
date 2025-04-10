import streamlit as st
import os
import json
from dooray_api_client import DoorayAPIClient

st.title("마크다운 페이지 전송 페이지")

# ----- 설정 파일 관련 함수 -----
def load_setting_names_from_json(folder="task_list"):
    """
    지정된 폴더(task_list) 내의 모든 JSON 파일에서
    세팅명(파일명에서 '_data.json'을 제거한 값) 목록을 반환합니다.
    """
    if not os.path.exists(folder):
        st.error(f"{folder} 폴더가 존재하지 않습니다.")
        st.stop()
    json_files = [f for f in os.listdir(folder) if f.endswith("_data.json")]
    if not json_files:
        st.error("저장된 세팅 파일이 존재하지 않습니다.")
        st.stop()
    return sorted([f.replace("_data.json", "") for f in json_files])

def load_setting_data(setting_name, folder="task_list"):
    """
    세팅 명(setting_name)을 바탕으로 해당 JSON 파일의 데이터를 반환합니다.
    """
    file_name = f"{setting_name}_data.json"
    file_path = os.path.join(folder, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"{file_name} 파일 로드 중 오류 발생: {str(e)}")
        st.stop()

# ----- st.secrets 기반 토큰 조회 함수 -----
def get_dooray_token_by_user_name(user_name, secrets_data):
    """
    st.secrets에 저장된 사용자 정보에서 user_name과 일치하는 사용자의 Dooray_token을 반환합니다.
    """
    for user in secrets_data.values():
        if user.get("name") == user_name:
            return user.get("Dooray_token")
    return None

# ----- 메인 실행 흐름 -----

# 1. JSON 세팅 파일 목록을 드롭다운 메뉴로 선택
setting_names = load_setting_names_from_json(folder="task_list")
selected_setting = st.selectbox("세팅 파일을 선택하세요 (세팅 명)", setting_names)

# 2. 선택된 세팅 파일의 정보 로드
setting_data = load_setting_data(selected_setting, folder="task_list")
wiki_id = setting_data.get("wiki_id")
parent_page_id = setting_data.get("page_id")   # 새 페이지를 부모 페이지 아래에 추가할 때 사용됨
user_name = setting_data.get("user_name")

# 3. st.secrets 에서 해당 사용자 토큰 조회
secrets_data = st.secrets
dooray_token = get_dooray_token_by_user_name(user_name, secrets_data)
if dooray_token is None:
    st.error("해당 사용자에 대한 토큰을 찾을 수 없습니다.")
    st.stop()

# 4. Dooray API 클라이언트 초기화
client = DoorayAPIClient(token=dooray_token)

# 5. 새 페이지 제목과 마크다운 내용 입력받기
st.subheader("새 마크다운 페이지 전송")
subject = st.text_input("새 페이지 제목", value="새 페이지 제목")
markdown_content = st.text_area("마크다운 내용", value="# 제목\n내용을 입력하세요.")

# 6. 페이지 전송 버튼 및 실행
if st.button("페이지 전송"):
    try:
        result = client.create_wiki_page(
            wiki_id=wiki_id,
            parentPageId=parent_page_id,
            subject=subject,
            content=markdown_content  # 내부적으로 "text/x-markdown" 형식으로 전송합니다.
        )
        st.success("페이지 전송이 완료되었습니다.")
        #st.json(result)
    except Exception as e:
        st.error(f"페이지 전송 중 오류 발생: {str(e)}")
