import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd

# --- 1. การตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Ton AI Analyst", layout="wide")

st.title("📊 D.E.E.P.V AI Analyst BY Ton")
st.write("แพลตฟอร์มวิเคราะห์หุ้นอัจฉริยะ (เวอร์ชันเสถียร)")

# --- 2. ส่วน Sidebar ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Google API Key:", type="password")
    ticker_input = st.text_input("ชื่อหุ้น (เช่น NVDA, PLTR):", "PLTR").upper()
    analyze_btn = st.button("🚀 เริ่มการวิเคราะห์ / ดึงข้อมูลใหม่")
    st.divider()
    st.info("คำแนะนำ: หากเปลี่ยนชื่อหุ้น ให้กดปุ่มวิเคราะห์อีกครั้งเพื่ออัปเดตข้อมูล")

# --- 3. ระบบจำค่า (Session State) ---
# ส่วนนี้สำคัญมาก! จะช่วยให้ข้อมูลไม่หายเวลาเรากดเปลี่ยนกราฟ
if 'stock_info' not in st.session_state:
    st.session_state.stock_info = None
if 'ai_analysis' not in st.session_state:
    st.session_state.ai_analysis = None

# --- 4. การดึงข้อมูล (รันเฉพาะเมื่อกดปุ่ม หรือยังไม่มีข้อมูล) ---
if analyze_btn:
    with st.spinner(f"กำลังดึงข้อมูล {ticker_input}..."):
        try:
            stock = yf.Ticker(ticker_input)
            st.session_state.stock_info = stock.info
            st.session_state.current_ticker = ticker_input
            
            # รัน AI Analysis ทันทีที่กดปุ่ม
            if api_key:
                genai.configure(api_key=api_key)
                # เลือกโมเดลสำรองเพื่อกัน Error 404
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name)
                
                prompt = f"วิเคราะห์หุ้น {ticker_input} ด้วย Framework D.E.E.P.V เป็นภาษาไทยอย่างละเอียด"
                response = model.generate_content(prompt)
                st.session_state.ai_analysis = response.text
            else:
                st.warning("ใส่ API Key เพื่อรับการวิเคราะห์จาก AI ด้วยนะ")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")

# --- 5. การแสดงผล (จะแสดงผลค้างไว้ตลอดตราบใดที่ยังมีข้อมูลใน session_state) ---
if st.session_state.stock_info:
    info = st.session_state.stock_info
    ticker = st.session_state.current_ticker
    stock = yf.Ticker(ticker)

    # Dashboard ตัวเลข
    st.header(f"📈 ข้อมูลพื้นฐาน: {info.get('longName', ticker)}")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("ราคาล่าสุด", f"{info.get('currentPrice', 'N/A')} USD")
    with col2:
        change = info.get('regularMarketChangePercent', 0) * 100
        st.metric("เปลี่ยนแปลง (24h)", f"{change:.2f}%")
    with col3:
        st.metric("Market Cap", f"{info.get('marketCap', 0)/1e12:.2f}T")
    with col4:
        st.metric("Sector", info.get('sector', 'N/A'))

    # กราฟราคา (ส่วนนี้กดเปลี่ยนได้เลย ข้อมูลอื่นจะไม่หาย)
    st.divider()
    st.subheader("กราฟราคา")
    time_period = st.radio("เลือกช่วงเวลา:", ["1d", "5d", "1mo", "6mo", "1y", "5y", "max"], horizontal=True, index=4)
    hist = stock.history(period=time_period)
    st.line_chart(hist['Close'])

    # ตารางงบการเงิน
    st.divider()
    st.subheader("📑 สรุปงบการเงิน (ล้านเหรียญ)")
    try:
        financials = stock.financials.loc[['Total Revenue', 'Net Income']]
        st.table((financials / 1e6).T)
    except:
        st.write("ไม่พบข้อมูลรายการงบการเงิน")

    # ผลวิเคราะห์ AI
    if st.session_state.ai_analysis:
        st.divider()
        st.subheader("🧠 ผลการวิเคราะห์เชิงลึก (AI Analysis)")
        st.markdown(st.session_state.ai_analysis)
        st.balloons()
