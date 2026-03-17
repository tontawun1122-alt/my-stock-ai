import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Ton AI Analyst", layout="wide")

st.title("📊 D.E.E.P.V AI Analyst BY Ton")

# --- 2. ส่วนรับข้อมูล (Sidebar) ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Google API Key ของคุณ:", type="password")
    ticker = st.text_input("ชื่อหุ้น (เช่น NVDA, PLTR):", "PLTR").upper()
    analyze_btn = st.button("🚀 เริ่มการวิเคราะห์")

# --- 3. ฟังก์ชันพิเศษ (ดัก Error) ---
def get_ai_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # ลองเรียกแบบตรงตัวที่สุดก่อน
        return genai.GenerativeModel('gemini-1.5-flash')
    except:
        # ถ้าไม่ได้ ให้หาชื่อโมเดลที่เครื่องนั้นรู้จัก
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return genai.GenerativeModel(models[0])

# --- 4. ส่วนประมวลผลหลัก ---
if ticker:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # --- กราฟราคา (แยกส่วนออกมาเพื่อให้กดเปลี่ยนเวลาได้โดยไม่พัง) ---
        st.subheader(f"📈 ข้อมูลหุ้น: {info.get('longName', ticker)}")
        
        time_period = st.radio(
            "ช่วงเวลากราฟ:",
            ["1d", "5d", "1mo", "6mo", "1y", "5y", "10y", "max"],
            horizontal=True, index=4
        )
        
        hist = stock.history(period=time_period)
        st.line_chart(hist['Close'])

        # --- ตารางงบการเงิน ---
        st.divider()
        st.subheader("📑 สรุปงบการเงิน")
        financials = stock.financials.loc[['Total Revenue', 'Net Income']]
        st.table((financials / 1e6).T)

        # --- ส่วนวิเคราะห์ AI (รันเฉพาะตอนกดปุ่ม) ---
        if analyze_btn:
            if not api_key:
                st.error("ใส่ API Key ก่อนเพื่อน!")
            else:
                st.divider()
                st.info("⌛ AI กำลังวิเคราะห์ D.E.E.P.V...")
                
                model = get_ai_model(api_key)
                prompt = f"วิเคราะห์หุ้น {ticker} ด้วย Framework D.E.E.P.V เป็นภาษาไทยอย่างละเอียด"
                
                response = model.generate_content(prompt)
                st.markdown(f"### 🧠 ผลการวิเคราะห์\n{response.text}")
                st.balloons()

    except Exception as e:
        st.error(f"ระบบขัดข้อง: {e}")
