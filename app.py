import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd

# --- 1. ตั้งค่าหน้าเว็บแบบกว้าง ---
st.set_page_config(page_title="Ton AI Analyst", layout="wide")

# ปรับ CSS เล็กน้อยให้ดูพรีเมียม
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e212b; padding: 15px; border-radius: 10px; border: 1px solid #3e4451; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 D.E.E.P.V AI Analyst โดย Ton")
st.caption("ระบบวิเคราะห์หุ้นอัจฉริยะด้วย AI และข้อมูล Real-time")

# --- 2. Sidebar สำหรับ Input ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Google API Key ของคุณ:", type="password")
    ticker = st.text_input("ชื่อหุ้น (เช่น NVDA, AAPL):", "NVDA").upper()
    analyze_btn = st.button("🚀 เริ่มการวิเคราะห์")
    st.divider()
    st.write("สร้างโดย Ton - นักลงทุนยุค AI")

# --- 3. ส่วนประมวลผลหลัก ---
if analyze_btn:
    if not api_key:
        st.error("กรุณาใส่ API Key ก่อนนะครับเพื่อน!")
    else:
        try:
            # ดึงข้อมูลจาก yfinance ก่อนเพื่อให้หน้าเว็บดูมีอะไร
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if not info or 'longName' not in info:
                st.error("ไม่พบข้อมูลหุ้นตัวนี้ ลองเช็กตัวสะกดอีกทีนะ")
                st.stop()

            # --- ส่วนที่ 1: Dashboard สรุปตัวเลข ---
            st.subheader(f"📈 ข้อมูลพื้นฐาน: {info.get('longName')}")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("ราคาล่าสุด", f"{info.get('currentPrice', 'N/A')} {info.get('currency')}")
            with col2:
                # คำนวณ % เปลี่ยนแปลง (ถ้ามีข้อมูล)
                change = info.get('regularMarketChangePercent', 0)
                st.metric("เปลี่ยนแปลง (24h)", f"{change:.2f}%")
            with col3:
                mkt_cap = info.get('marketCap', 0) / 1e12 # แปลงเป็น Trillion
                st.metric("Market Cap", f"{mkt_cap:.2f}T")
            with col4:
                st.metric("Sector", info.get('sector', 'N/A'))

            # --- ส่วนที่ 2: กราฟราคาย้อนหลัง (ทำให้ดูโปรขึ้น 100%) ---
            st.write("### กราฟราคาย้อนหลัง (1 ปี)")
            hist = stock.history(period="1y")
            st.line_chart(hist['Close'])

            # --- ส่วนที่ 3: การวิเคราะห์ด้วย AI ---
            st.divider()
            st.info(f"⌛ ระบบ D.E.E.P.V กำลังวิเคราะห์ข้อมูลเชิงลึกสำหรับ {ticker}...")
            
            # ตั้งค่า AI (ใช้เทคนิค list_models ที่นายทำไว้ เพราะมันเวิร์ก!)
            genai.configure(api_key=api_key)
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # เลือกใช้ gemini-1.5-flash ถ้ามีในลิสต์ ถ้าไม่มีค่อยเอาตัวแรก
            target_model = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in models else models[0]
            model = genai.GenerativeModel(target_model)

            prompt = f"""
            จงวิเคราะห์หุ้น {ticker} ({info.get('longName')}) โดยใช้ Framework D.E.E.P.V อย่างละเอียด:
            - D (Data): พื้นฐานบริษัทและธุรกิจหลัก
            - E (Earnings): แนวโน้มกำไรและงบการเงินล่าสุด
            - E (Expectation): ความคาดหวังของตลาดและเป้าหมายราคา
            - P (Price/Psychology): จิตวิทยาตลาดและเทคนิคเบื้องต้น
            - V (Verdict): สรุปความน่าลงทุนในระยะยาว
            
            ข้อมูลเสริม: {info.get('longBusinessSummary', '')[:1000]}
            ตอบเป็นภาษาไทย 100% ใช้ Markdown หัวข้อให้ชัดเจน และใช้ Bullet points เพื่อให้อ่านง่าย
            """
            
            response = model.generate_content(prompt)
            
            st.markdown("### 🧠 ผลการวิเคราะห์เชิงลึก (AI Analysis)")
            st.write(response.text)
            st.balloons() 

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
