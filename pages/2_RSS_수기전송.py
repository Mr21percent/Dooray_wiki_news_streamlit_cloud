import pandas as pd
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from holidayskr import is_holiday
import feedparser
import requests
from collections import defaultdict
from bs4 import BeautifulSoup
import html
import json
import os
import glob
import streamlit as st
from dooray_api_client import DoorayAPIClient

# RSS URL 딕셔너리
rss_url_dict = {
    '금융위원회':'https://www.korea.kr/rss/dept_fsc.xml',
    '기획재정부': 'https://www.korea.kr/rss/dept_moef.xml',
    '산업통상자원부' : 'https://www.korea.kr/rss/dept_motie.xml',
    '과학기술정보통신부' : 'https://www.korea.kr/rss/dept_msit.xml',
    '중소벤처기업부' : 'https://www.korea.kr/rss/dept_mss.xml',
    '탄소중립녹색성장 위원회' : 'https://www.korea.kr/rss/dept_cnc.xml',
}

# JSON 설정 파일 로드 함수
def load_settings(folder="task_list"):
    """
    task_list 폴더에서 모든 JSON 설정 파일을 로드합니다.
    """
    settings = []
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
            return settings
            
        json_files = glob.glob(os.path.join(folder, "*.json"))
        for file_path in json_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                setting = json.load(f)
                setting_name = os.path.basename(file_path).replace("_data.json", "")
                setting["setting_name"] = setting_name
                settings.append(setting)
        return settings
    except Exception as e:
        print(f"설정 파일 로딩 중 오류 발생: {e}")
        return []

def get_start_date_and_time():
    """
    시작 날짜와 시간 계산 함수
    """
    # 'Asia/Seoul' 타임존 정보 사용
    kst = ZoneInfo("Asia/Seoul")
    korea_time = datetime.now(kst)
    cur_date = korea_time.strftime("%Y-%m-%d")
    
    start_time = korea_time - timedelta(days=1)
    
    while start_time.weekday() >= 5 or is_holiday(start_time.strftime("%Y-%m-%d")):
        start_time = start_time - timedelta(days=1)
    
    start_date = start_time.strftime("%Y-%m-%d")
    start_date_6pm = datetime.combine(start_time, time(17, 30), tzinfo=kst)
    
    return start_date, start_date_6pm, cur_date, start_time

def clean_summary(summary_html):
    """
    HTML 요약 정보를 정리하는 함수
    """
    try:
        soup = BeautifulSoup(summary_html, 'html5lib')

        # 이미지나 링크 등 불필요한 요소 제거
        for tag in soup(['a', 'img', 'figure', 'figcaption', 'div']):
            tag.decompose()

        # 텍스트만 추출 + HTML entity 복호화
        clean_text = html.unescape(soup.get_text(separator=' ', strip=True))

        # 공백 정리
        clean_text = ' '.join(clean_text.split())

        return clean_text
    except Exception as e:
        print(f"요약 정리 중 오류 발생: {e}")
        return summary_html

def fetch_rss_data(rss_url_dict):
    """
    RSS 피드에서 데이터를 가져오는 함수
    """
    all_entries = []

    # RSS 피드를 URL 딕셔너리에서 받아 처리
    for dept_name, rss_url in rss_url_dict.items():
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                all_entries.append({
                    'department': dept_name,
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published,
                    'summary': entry.summary if hasattr(entry, 'summary') else ''
                })
        except Exception as e:
            print(f"{dept_name} RSS 처리 중 오류 발생: {e}")

    # DataFrame 생성
    if not all_entries:
        return pd.DataFrame()
        
    rss_df = pd.DataFrame(all_entries)
    rss_df['summary'] = rss_df['summary'].apply(clean_summary)

    # 한국 시간대로 변환
    kst = ZoneInfo("Asia/Seoul")
    rss_df['published'] = pd.to_datetime(rss_df['published'], utc=True).dt.tz_convert(kst)

    return rss_df


def generate_markdown(df, start_time, korea_time, use_gpt=False, gpt_prompt=""):
    """
    수집한 데이터를 마크다운으로 변환하는 함수
    """
    markdown_output = f"# {start_time.strftime('%y%m%d')}~{korea_time.strftime('%y%m%d')} 보도자료\n\n"

    grouped = defaultdict(list)
    for _, row in df.iterrows():
        grouped[row['department']].append(row)

    for dept, items in grouped.items():
        markdown_output += f"## {dept}\n"
        for row in items:
            pub_time = pd.to_datetime(row['published']).strftime('%Y-%m-%d %H시')
            markdown_output += f"- **{row['title']}** [[링크]]({row['link']})  \n"
            markdown_output += f"  <sub>({pub_time})</sub>\n\n"
            
            summary = row['summary']
            if use_gpt and summary and gpt_prompt:
                #summary = apply_gpt_summary(summary, gpt_prompt)
                pass
            if summary:
                markdown_output += f"  {summary}\n\n"
            else:
                markdown_output += f"  요약 정보 없음\n\n"
                
    return markdown_output


def fetch_and_upload_news(setting=None, progress_bar=None, status=None):
    """
    뉴스를 가져와 Dooray Wiki에 업로드하는 메인 함수
    """
    try:
        # 상태 업데이트 함수
        def update_status(step_num, total_steps, message):
            if progress_bar is not None:
                progress_bar.progress(step_num / total_steps)
            if status is not None:
                status.update(label=f"Step {step_num}/{total_steps}: {message}")

        # 총 단계 수
        total_steps = 6
        cur_steps = 1
        
        # Step 1: 날짜 계산
        update_status(cur_steps, total_steps, "날짜 데이터 계산 중...")
        cur_steps += 1  # 수정된 부분
        start_date, start_date_6pm, cur_date, start_time_obj = get_start_date_and_time()

        # 데이터 프레임 리스트
        news_dfs = []
        
        # Step 2: RSS 데이터 가져오기
        update_status(cur_steps, total_steps, "RSS 데이터 가져오는 중...")
        cur_steps += 1  # 수정된 부분
        rss_df = fetch_rss_data(rss_url_dict)
        if not rss_df.empty:
            news_dfs.append(rss_df[['department', 'title', 'link', 'published', 'summary']])
        
        # Step 3 & 4: 데이터 결합 및 필터링
        update_status(cur_steps, total_steps, "데이터 결합 및 필터링 중...")
        cur_steps += 1  # 수정된 부분
        if not news_dfs:
            print("수집된 뉴스가 없습니다.")
            return False, "수집된 뉴스가 없습니다."
            
        today_full_news_df = pd.concat(news_dfs).query("published >= @start_date_6pm")
        
        if today_full_news_df.empty:
            print("필터링 후 표시할 뉴스가 없습니다.")
            return False, "필터링 후 표시할 뉴스가 없습니다."

        # Step 5: 마크다운 생성
        update_status(cur_steps, total_steps, "마크다운 생성 중...")
        cur_steps += 1  # 수정된 부분
        markdown_output = generate_markdown(
            today_full_news_df, 
            start_time_obj, 
            datetime.now(ZoneInfo('Asia/Seoul')),
            False,
            ""
        )

        # Step 6: 위키 페이지 생성 (설정이 있는 경우)
        if setting and setting.get("wiki_id") and setting.get("page_id"):
            update_status(cur_steps, total_steps, "Dooray Wiki에 페이지 생성 중...")
            cur_steps += 1  # 수정된 부분
            # 사용자 정보에서 Dooray 토큰 가져오기
            user_name = setting.get("user_name")
            dooray_token = None

            # st.secrets에서 사용자 이름으로 토큰 찾기
            if hasattr(st, "secrets"):
                for user_info in st.secrets.values():
                    if isinstance(user_info, dict) and user_info.get("name") == user_name:
                        dooray_token = user_info.get("Dooray_token")
                        break

            if not dooray_token:
                return False, f"'{user_name}' 사용자의 Dooray 토큰을 찾을 수 없습니다."
           
            client = DoorayAPIClient(token=dooray_token)
            success, page_id = client.create_wiki_page(
                setting["wiki_id"],
                setting["page_id"],
                f"뉴스 업데이트 {cur_date}",
                markdown_output

            )
            
            update_status(total_steps, total_steps, "완료!")
            if success:
                return True, f"위키 페이지가 성공적으로 생성되었습니다."
            else:
                return False, "위키 페이지 생성에 실패했습니다."
        else:
            update_status(total_steps, total_steps, "완료!")
            # 설정이 없는 경우 마크다운만 반환
            return True, markdown_output
            
    except Exception as e:
        print(f"뉴스 처리 중 오류 발생: {e}")
        return False, f"뉴스 처리 중 오류 발생: {str(e)}"

# Streamlit UI 구성 함수
def streamlit_ui():
    """
    Streamlit UI를 구성하는 함수
    """
    st.title("Dooray! Wiki News 발송")
    st.subheader("저장된 설정을 선택하여 뉴스를 발송하세요")
    
    # 저장된 설정 불러오기
    settings = load_settings()
    
    if not settings:
        st.warning("저장된 설정이 없습니다. 먼저 설정을 저장해주세요.")
        return
    
    # 설정 선택 드롭다운
    setting_names = [setting["setting_name"] for setting in settings]
    selected_name = st.selectbox("설정 선택", setting_names)
    
    # 선택한 설정 찾기
    selected_setting = next((s for s in settings if s["setting_name"] == selected_name), None)
    
    if selected_setting:
        st.write(f"**위키 페이지**: {selected_setting.get('page_title', '알 수 없음')}")
        #st.write(f"**검색어**: {selected_setting.get('naver_news_search_term', '없음')}")
        
        if st.button("뉴스 발송하기"):
            # 진행 상황을 표시할 컴포넌트 생성
            progress_bar = st.progress(0)
            status_container = st.empty()
            
            with st.status("뉴스 처리 시작...") as status:
                success, result = fetch_and_upload_news(
                    selected_setting, 
                    progress_bar=progress_bar, 
                    status=status
                )
                
                if success:
                    status.update(label="뉴스 발송 성공!", state="complete")
                    st.success("뉴스 발송 성공!")
                    if isinstance(result, str) and result.startswith("위키 페이지"):
                        st.info(result)
                    else:
                        st.text_area("생성된 마크다운", result, height=300)
                else:
                    status.update(label=f"오류 발생: {result}", state="error")
                    st.error(f"뉴스 발송 실패: {result}")
            
            # 진행 완료 후 프로그레스 바를 완료 상태로 설정
            progress_bar.progress(1.0)

# Streamlit 앱 실행 시 호출되는 메인 함수
if __name__ == "__main__":
    streamlit_ui()