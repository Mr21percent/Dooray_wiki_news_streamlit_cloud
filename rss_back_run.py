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
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time as time_module

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
    
    while is_holiday(start_time.strftime("%Y-%m-%d")):
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

# ... (생략: 기존 import 및 함수 정의 부분 동일)

def fetch_and_upload_news(setting=None, rss_df=None, progress_bar=None, status=None):
    """
    이미 수집된 뉴스 데이터를 받아 Dooray Wiki에 업로드하는 메인 함수
    """
    try:
        def update_status(step_num, total_steps, message):
            if progress_bar is not None:
                progress_bar.progress(step_num / total_steps)
            if status is not None:
                status.update(label=f"Step {step_num}/{total_steps}: {message}")

        total_steps = 5
        cur_steps = 1
        
        update_status(cur_steps, total_steps, "날짜 계산 중...")
        cur_steps += 1
        start_date, start_date_6pm, cur_date, start_time_obj = get_start_date_and_time()

        if rss_df is None or rss_df.empty:
            return False, "RSS 데이터가 없습니다."
        
        update_status(cur_steps, total_steps, "뉴스 필터링 중...")
        cur_steps += 1
        today_full_news_df = rss_df.query("published >= @start_date_6pm")
        
        if today_full_news_df.empty:
            return False, "필터링 후 뉴스가 없습니다."

        update_status(cur_steps, total_steps, "마크다운 생성 중...")
        cur_steps += 1
        markdown_output = generate_markdown(
            today_full_news_df,
            start_time_obj,
            datetime.now(ZoneInfo("Asia/Seoul")),
            False,
            ""
        )

        if setting and setting.get("wiki_id") and setting.get("page_id"):
            update_status(cur_steps, total_steps, "Dooray Wiki에 업로드 중...")
            cur_steps += 1
            user_name = setting.get("user_name")
            dooray_token = None

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
            return (True, "업로드 성공") if success else (False, "Dooray 업로드 실패")
        else:
            update_status(total_steps, total_steps, "완료!")
            return True, markdown_output

    except Exception as e:
        return False, f"오류 발생: {str(e)}"


def job():
    print("\n🕒 작업 시작:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    rss_df = fetch_rss_data(rss_url_dict)

    if rss_df.empty:
        print("❌ RSS 데이터가 비어있습니다.")
        return

    for setting in load_settings():
        print(f"📄 설정 처리 중: {setting.get('setting_name', '이름 없음')}")
        success, result = fetch_and_upload_news(setting, rss_df=rss_df)
        if success:
            print(f"✅ 업로드 성공: {result}")
        else:
            print(f"❌ 업로드 실패: {result}")


# --- APScheduler 설정 ---
if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")  # ✅ 한국 시간대 지정
    print("🔄 스케줄러 초기화됨.")
    # 매일 오후 5시 (17:00)에 실행
    trigger = CronTrigger(hour=10, minute=30)
    scheduler.add_job(job, trigger)

    scheduler.start()
    print("✅ 스케줄러 시작됨. 매일 한국시간 오후 5시에 작업이 실행됩니다.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("🛑 종료 중...")
        scheduler.shutdown()