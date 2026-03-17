import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd

st.set_page_config(page_title="Ton AI Analyst", layout="wide")
st.title("📊 D.E.E.P.V AI Analyst BY Ton")

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Google API Key:", type="password")
    ticker_input = st.text_input("ชื่อหุ้น (เช่น NVDA, PLTR):", "NVDA").upper()
    analyze_btn = st.button("🚀 เริ่มการวิเคราะห์")

# ใช้ Session State จำค่าเดิมไว้ ข้อมูลจะได้ไม่หายตอนกดเปลี่ยนกราฟ
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = None
if 'ai_result' not in st.session_state:
    st.session_state.ai_result = None

if analyze_btn:
    try:
        # 1. ดึงข้อมูลหุ้น
        stock = yf.Ticker(ticker_input)
        info = stock.info
        
        # แก้จุดข้อมูลเพี้ยน: เช็กค่า % เปลี่ยนแปลงให้ชัวร์
        raw_change = info.get('regularMarketChangePercent', 0)
        # ถ้าค่าที่ได้มามันน้อยมากๆ (เช่น 0.01) ค่อยคูณ 100 แต่ถ้ามาเป็นหลักหน่วย (เช่น 1.5) คือ % อยู่แล้ว
        display_change = raw_change * 100 if abs(raw_change) < 0.1 else raw_change
        
        st.session_state.stock_data = {
            'name': info.get('longName', ticker_input),
            'price': info.get('currentPrice', 'N/A'),
            'change': display_change,
            'cap': info.get('marketCap', 0) / 1e12,
            'sector': info.get('sector', 'N/A'),
            'ticker': ticker_input
        }

        # 2. รัน AI (แบบแก้ปัญหา 404 v1beta)
        if api_key:
            genai.configure(api_key=api_key)
            # ดึงรายชื่อโมเดลที่เครื่องนี้ "รู้จัก" จริงๆ
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # พยายามใช้ 1.5-flash ถ้าไม่ได้ให้เอาตัวแรกในลิสต์
            m_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available else available[0]
            
            model = genai.GenerativeModel(m_name)
            prompt = f"วิเคราะห์หุ้น {ticker_input} ด้วย Framework D.E.E.P.V เป็นภาษาไทย"
            response = model.generate_content(prompt)
            st.session_state.ai_result = response.text
            
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: {e}")

# --- ส่วนแสดงผล (ดึงจาก Session State) ---
if st.session_state.stock_data:
    d = st.session_state.stock_data
    st.header(f"📈 ข้อมูลพื้นฐาน: {d['name']}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ราคาล่าสุด", f"{d['price']} USD")
    c2.metric("เปลี่ยนแปลง (24h)", f"{d['change']:.2f}%") # โชว์ทศนิยม 2 ตำแหน่งพอ
    c3.metric("Market Cap", f"{d['cap']:.2f}T")
    c4.metric("Sector", d['sector'])

    # กราฟราคา (เปลี่ยนช่วงเวลาได้ ข้อมูลไม่หาย)
    st.divider()
    t_period = st.radio("ช่วงเวลา:", ["1d", "1mo", "1y", "5y", "max"], horizontal=True, index=2)
    hist = yf.Ticker(d['ticker']).history(period=t_period)
    st.line_chart(hist['Close'])

    if st.session_state.ai_result:
        st.divider()
        st.subheader("🧠 ผลการวิเคราะห์เชิงลึก (AI Analysis)")
        st.markdown(st.session_state.ai_result)
        st.balloons()
