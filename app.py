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
        color: white;
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
            # ตั้งค่า API
            genai.configure(api_key=api_key)
            
            # ดึงข้อมูลหุ้น
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # ตรวจสอบว่ามีข้อมูลหุ้นจริงไหม
            if not info or 'longName' not in info:
                st.warning(f"ไม่พบข้อมูลหุ้น {ticker} กรุณาเช็กตัวสะกดอีกทีนะเพื่อน")
                st.stop()

            st.info(f"⌛ กำลังประมวลผลหุ้น {ticker}... ระบบ D.E.E.P.V กำลังทำงาน")
            
            # บรรทัดสำคัญ: แก้ไขชื่อโมเดลให้เป็นเวอร์ชันมาตรฐาน
            model = genai.GenerativeModel('models/gemini-1.5-flash') 
            
            # ปรับ Prompt ให้ดึงข้อมูลจาก info มาใช้ด้วย AI จะได้วิเคราะห์แม่นๆ
            prompt = f"""
            จงวิเคราะห์หุ้น {ticker} ({info.get('longName')}) 
            ข้อมูลปัจจุบัน: ราคาล่าสุด {info.get('currentPrice', 'N/A')} {info.get('currency', '')}, 
            ธุรกิจ: {info.get('longBusinessSummary', 'N/A')[:500]}...

            โดยใช้ Framework D.E.E.P.V อย่างละเอียด:
            - D (Data/Details): พื้นฐานบริษัท
            - E (Earnings/Economy): งบการเงินและภาพรวมเศรษฐกิจ
            - E (Expectation): ความคาดหวังของตลาด
            - P (Price/Psychology): กราฟและจิตวิทยาการลงทุน
            - V (Verdict): สรุปความน่าลงทุน

            **คำสั่งพิเศษ:** 1. ตอบเป็นภาษาไทย 100% 
            2. ใช้ Markdown (### และ -) แบ่งหัวข้อให้ชัดเจน
            3. สรุปตอนท้าย (Verdict) ให้ชัดเจนว่าน่าลงทุนหรือไม่
            """
            
            # สั่ง AI ให้ทำงาน
            response = model.generate_content(prompt)
            
            # แสดงผล
            st.markdown("---")
            st.subheader(f"📈 รายงานการวิเคราะห์หุ้น: {ticker}")
            st.markdown(f'<div class="report-card">{response.text}</div>', unsafe_allow_html=True)
            
            st.balloons()
            st.success("วิเคราะห์เสร็จแล้ว! ลองอ่านข้อมูลดูนะเพื่อน")
            
        except Exception as e:
            # ถ้ายังติด 404 หรือ Error อื่นๆ มันจะโชว์ตรงนี้
            st.error(f"เกิดข้อผิดพลาด: {e}")
            st.info("คำแนะนำ: ลองเช็กว่า API Key ถูกต้อง และ GitHub อัปเดตไฟล์ requirements.txt หรือยัง")
