import io

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

load_dotenv()


def get_naver_market_cap(sosok=0, pages=1):
    all_data = []

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for page in range(1, pages + 1):
        url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"

        response = requests.get(url, headers=headers)
        response.encoding = "euc-kr"

        tables = pd.read_html(response.text)
        df = tables[1]
        df = df.dropna(how="all")

        all_data.append(df)

    result = pd.concat(all_data, ignore_index=True)
    result = result.dropna(subset=["종목명"])

    return result


def clean_number(x):
    if pd.isna(x):
        return None
    return str(x).replace(",", "").replace("%", "").strip()


def summarize_market(top_df):
    market_text = top_df.to_string(index=False)

    llm = ChatOpenAI(model="gpt-5.5")

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """
너는 한국 주식시장 데이터를 요약하는 증권사 애널리스트다.
사용자가 제공하는 시가총액 상위 종목 데이터를 보고 핵심만 요약해라.

작성 기준:
1. 시가총액 상위 종목 구성을 요약
2. 특정 업종이나 종목 쏠림이 있으면 언급
3. 외국인비율, PER, ROE에서 눈에 띄는 점을 언급
4. 투자 추천처럼 쓰지 말 것
5. 단정하지 말고 데이터에서 보이는 사실 중심으로 작성
6. 한국어로 작성
            """,
        ),
        (
            "user",
            """
아래는 네이버 금융에서 가져온 시가총액 상위 종목 데이터다.

{input}

이 데이터를 바탕으로 시장 구성을 요약해줘.
            """,
        ),
    ])

    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"input": market_text})


st.set_page_config(page_title="네이버 시가총액 AI 요약", page_icon="📈", layout="wide")
st.title("📈 네이버 금융 시가총액 상위 종목 AI 요약")
st.write("네이버 금융에서 코스피 시가총액 상위 종목을 가져와 AI가 시장 구성을 요약해줍니다.")

col1, col2 = st.columns(2)
with col1:
    pages = st.number_input("가져올 페이지 수 (1페이지 = 50종목)", min_value=1, max_value=5, value=1)
with col2:
    top_n = st.number_input("시가총액 상위 몇 개 종목을 볼지", min_value=5, max_value=100, value=20)

if st.button("데이터 가져오고 분석하기"):
    with st.spinner("네이버 금융에서 데이터 가져오는 중..."):
        market_df = get_naver_market_cap(sosok=0, pages=pages)

        cols = ["종목명", "현재가", "전일비", "등락률", "시가총액", "상장주식수", "외국인비율", "PER", "ROE"]
        market_df = market_df[cols]

        for col in ["현재가", "전일비", "시가총액", "상장주식수", "외국인비율", "PER", "ROE"]:
            market_df[col] = market_df[col].apply(clean_number)
            market_df[col] = pd.to_numeric(market_df[col], errors="coerce")

        top_df = market_df.sort_values("시가총액", ascending=False).head(top_n)

    st.subheader("시가총액 상위 종목")
    st.dataframe(top_df, use_container_width=True)

    with st.spinner("AI 요약 생성 중..."):
        summary = summarize_market(top_df)

    st.subheader("AI 요약")
    st.write(summary)

    summary_df = pd.DataFrame({"구분": ["AI 요약"], "내용": [summary]})

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        top_df.to_excel(writer, sheet_name="시가총액상위", index=False)
        summary_df.to_excel(writer, sheet_name="요약", index=False)

    st.download_button(
        label="엑셀 파일 다운로드",
        data=buffer.getvalue(),
        file_name="네이버_시가총액_AI요약.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
