import streamlit as st
import yfinance as yf
import google.generativeai as genai

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Ton AI Analyst", layout="wide")
st.title("📊 D.E.E.P.V AI Analyst โดย Ton")

# --- รับค่า API Key และชื่อหุ้น ---
with st.sidebar:
    api_key = st.text_input("ใส่ Google API Key ของคุณ:", type="password")
    ticker = st.text_input("ชื่อหุ้น (เช่น NVDA, AAPL):", "NVDA")
    analyze_btn = st.button("เริ่มการวิเคราะห์")

if analyze_btn:
    if not api_key:
        st.error("กรุณาใส่ API Key ก่อนนะครับเพื่อน!")
    else:
        try:
            genai.configure(api_key=api_key)
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            model = genai.GenerativeModel(models[0])
            stock = yf.Ticker(ticker)
            info = stock.info
            st.info(f"กำลังวิเคราะห์ {ticker} กรุณารอสักครู่...")
            prompt = f"วิเคราะห์หุ้น {ticker} ด้วย Framework D.E.E.P.V เป็นภาษาไทยอย่างละเอียด ข้อมูลพื้นฐาน: {info.get('longName')}"
            response = model.generate_content(prompt)
            st.markdown("### 📈 ผลการวิเคราะห์")
            st.write(response.text)
            st.balloons() 
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
