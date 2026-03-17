import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd

# --- 1. ตั้งค่าหน้าเว็บให้ดูพรีเมียม ---
st.set_page_config(page_title="Ton AI Analyst", layout="wide")

# ปรับ CSS ให้รองรับภาษาไทยและดูสะอาดตา
st.markdown("""
    <style>
    .stMarkdown { font-family: 'Sarabun', sans-serif; }
    .report-card {
        padding: 25px;
        border-radius: 12px;
        background-color: #1e212b;
        border: 1px solid #3e4451;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 D.E.E.P.V AI Analyst BY Ton")
st.write("แพลตฟอร์มวิเคราะห์หุ้นด้วย AI อัจฉริยะ")

# --- 2. ส่วนรับข้อมูลจากผู้ใช้ ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Google API Key ของคุณ:", type="password")
    ticker = st.text_input("ชื่อหุ้น (เช่น NVDA, TSLA, PLTR):", "PLTR").upper()
    analyze_btn = st.button("🚀 เริ่มการวิเคราะห์")

# --- 3. ส่วนประมวลผล ---
if analyze_btn:
    if not api_key:
        st.error("อย่าลืมใส่ API Key นะเพื่อน!")
    else:
        try:
            genai.configure(api_key=api_key)
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # --- ส่วนที่ 1: ข้อมูลพื้นฐาน ---
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

            # --- ส่วนที่ 2: กราฟราคาพร้อมปุ่มเลือกเวลา ---
            st.divider()
            st.subheader("กราฟราคา")
            
            # สร้างปุ่มเลือกช่วงเวลา
            time_period = st.radio(
                "เลือกช่วงเวลา:",
                ["1d", "6mo", "1y", "5y", "10y", "max"],
                horizontal=True,
                index=2 # Default ที่ 1y
            )
            
            # ดึงข้อมูลตามช่วงเวลาที่เลือก
            hist = stock.history(period=time_period)
            if not hist.empty:
                st.line_chart(hist['Close'])
            else:
                st.warning("ไม่พบข้อมูลกราฟในช่วงเวลาที่เลือก")

            # --- ส่วนที่ 3: ข้อมูลทางการเงิน (Financials) ---
            st.divider()
            st.subheader("📑 สรุปงบการเงินและตัวเลขสำคัญ")
            
            tab1, tab2 = st.tabs(["💰 งบการเงินย้อนหลัง", "📈 อัตราส่วนทางการเงิน"])
            
            with tab1:
                try:
                    # ดึงรายได้และกำไรสุทธิ
                    financials = stock.financials.loc[['Total Revenue', 'Net Income']]
                    financials_display = financials / 1e6
                    st.write("หน่วย: ล้านเหรียญ (USD)")
                    st.table(financials_display.T)
                except:
                    st.write("ไม่พบข้อมูลรายการงบการเงิน")

            with tab2:
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    st.write("**P/E Ratio:**")
                    st.write(info.get('trailingPE', 'N/A'))
                with col_r2:
                    st.write("**Forward P/E:**")
                    st.write(info.get('forwardPE', 'N/A'))
                with col_r3:
                    st.write("**PEG Ratio:**")
                    st.write(info.get('pegRatio', 'N/A'))

            # --- ส่วนที่ 4: AI Analysis ---
            st.divider()
            st.subheader("🧠 ผลการวิเคราะห์เชิงลึก (AI Analysis)")
            st.info(f"⏳ ระบบ D.E.E.P.V กำลังวิเคราะห์ข้อมูลเชิงลึกสำหรับ {ticker}...")

            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            จงวิเคราะห์หุ้น {ticker} ({info.get('longName', ticker)}) โดยใช้ Framework D.E.E.P.V อย่างละเอียด
            **คำสั่งพิเศษ:**
            1. ตอบเป็นภาษาไทย 100%
            2. ใช้ Markdown (เช่น ### และ -) เพื่อแบ่งหัวข้อให้ชัดเจน
            3. สรุปตอนท้าย (V - Verdict) ให้ชัดเจนว่าน่าลงทุนหรือไม่
            """
            
            response = model.generate_content(prompt)
            st.markdown(f'<div class="report-card">{response.text}</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
