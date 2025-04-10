import pandas as pd
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from holidayskr import is_holiday
import feedparser
import requests
from collections import defaultdict
from bs4 import BeautifulSoup
import html
from dooray_api_client import DoorayAPIClient


rss_url_dict = {
        '금융위원회':'https://www.korea.kr/rss/dept_fsc.xml',
        '기획재정부': 'https://www.korea.kr/rss/dept_moef.xml',
        '산업통상자원부' : 'https://www.korea.kr/rss/dept_motie.xml',
        '과학기술정보통신부' : 'https://www.korea.kr/rss/dept_msit.xml',
        '중소벤처기업부' : 'https://www.korea.kr/rss/dept_mss.xml',
        '탄소중립녹색성장 위원회' : 'https://www.korea.kr/rss/dept_cnc.xml',
    }


def get_start_date_and_time():
    # 'Asia/Seoul' 타임존 정보 사용
    kst = ZoneInfo("Asia/Seoul")
    korea_time = datetime.now(kst)
    cur_date = korea_time.strftime("%Y-%m-%d")
    
    start_time = korea_time - timedelta(days=1)
    
    while is_holiday(start_time.strftime("%Y-%m-%d")):
        start_time = start_time - timedelta(days=1)
    
    start_date = start_time.strftime("%Y-%m-%d")
    start_date_6pm = datetime.combine(start_time, time(17, 30), tzinfo=kst)
    
    return start_date, start_date_6pm, cur_date


def clean_summary(summary_html):
    soup = BeautifulSoup(summary_html, 'html5lib')

    # 2. 이미지나 링크 등 불필요한 요소 제거
    for tag in soup(['a', 'img', 'figure', 'figcaption', 'div']):
        tag.decompose()

    # 3. 텍스트만 추출 + HTML entity 복호화 (&nbsp; -> 공백 등)
    clean_text = html.unescape(soup.get_text(separator=' ', strip=True))

    # 4. 공백 정리
    clean_text = ' '.join(clean_text.split())

    return clean_text


def fetch_rss_data(rss_url_dict):
    all_entries = []

    # RSS 피드를 URL 딕셔너리에서 받아 처리
    for dept_name, rss_url in rss_url_dict.items():
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            all_entries.append({
                'department': dept_name,
                'title': entry.title,
                'link': entry.link,
                'published': entry.published,
                'summary': entry.summary
            })

    # DataFrame 생성
    rss_df = pd.DataFrame(all_entries)
    rss_df['summary'] = rss_df['summary'].apply(clean_summary)

    # 한국 시간대로 변환
    kst = ZoneInfo("Asia/Seoul")
    rss_df['published'] = pd.to_datetime(rss_df['published'], utc=True).dt.tz_convert(kst)

    return rss_df


def generate_markdown(df, start_time, korea_time):
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
            markdown_output += f"  요약 추가 검토 중\n\n"
    return markdown_output

def fetch_and_upload_news():
    # Step 1: 날짜 계산
    start_date, start_date_6pm, cur_date = get_start_date_and_time()

    # Step 2: RSS 데이터 가져오기
    rss_df = fetch_rss_data(rss_url_dict)  # rss_url_dict 전달

    # Step 4: 데이터 결합
    today_full_news_df = pd.concat([
        rss_df[['department', 'title', 'link', 'published', 'summary']]
    ]).query("published >= @start_date_6pm")

    # Step 5: 마크다운 생성
    markdown_output = generate_markdown(today_full_news_df, start_date, datetime.now(ZoneInfo('Asia/Seoul')))

    # Step 6: 위키 페이지 생성
    create_wiki_page(markdown_output)