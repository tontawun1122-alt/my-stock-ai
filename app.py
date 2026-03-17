import streamlit as st
import yfinance as yf
import google.generativeai as genai

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
    ticker = st.text_input("ชื่อหุ้น (เช่น NVDA, TSLA):", "NVDA").upper()
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
            
            st.info(f"⌛ กำลังประมวลผลหุ้น {ticker}... ระบบ D.E.E.P.V กำลังทำงาน")
            
            model = genai.GenerativeModel('gemini-1.5-flash-latest') # ใช้ตัวแรงล่าสุด
            
            # ปรับ Prompt ให้ AI จัดหน้าสวยๆ ไม่ให้ภาษาไทยเพี้ยน
            prompt = f"""
            จงวิเคราะห์หุ้น {ticker} ({info.get('longName', ticker)}) โดยใช้ Framework D.E.E.P.V อย่างละเอียด
            **คำสั่งพิเศษ:** 1. ตอบเป็นภาษาไทย 100% 
            2. ใช้ Markdown (เช่น ### และ -) เพื่อแบ่งหัวข้อให้ชัดเจน 
            3. สรุปตอนท้าย (V - Verdict) ให้ชัดเจนว่าน่าลงทุนหรือไม่
            """
            
            response = model.generate_content(prompt)
            
            # แสดงผล
            st.markdown("---")
            st.subheader(f"📈 รายงานการวิเคราะห์หุ้น: {ticker}")
            st.markdown(f'<div class="report-card">{response.text}</div>', unsafe_allow_html=True)
            
            st.balloons()
            st.success("วิเคราะห์เสร็จแล้ว! นายลองก๊อปข้อความในกล่องนี้ไปใช้ได้เลย")
            
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
