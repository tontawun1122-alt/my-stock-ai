import streamlit as st
import yfinance as yf
import google.generativeai as genai

st.set_page_config(page_title="Ton AI Analyst", layout="wide")
st.title("📊 D.E.E.P.V AI Analyst BY Ton")

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Google API Key ของคุณ:", type="password")
    ticker = st.text_input("ชื่อหุ้น:", "PLTR").upper()
    analyze_btn = st.button("🚀 เริ่มการวิเคราะห์")

# ส่วนแสดงผลข้อมูลหุ้น (แยกจากปุ่ม AI เพื่อไม่ให้หลุดเวลาเปลี่ยนกราฟ)
if ticker:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        st.subheader(f"📈 ข้อมูลหุ้น: {info.get('longName', ticker)}")
        
        # ปุ่มเลือกเวลากราฟ
        period = st.radio("ช่วงเวลา:", ["1d", "1mo", "1y", "5y", "max"], horizontal=True, index=2)
        st.line_chart(stock.history(period=period)['Close'])

        if analyze_btn:
            if not api_key:
                st.error("ใส่ API Key ก่อนเพื่อน!")
            else:
                genai.configure(api_key=api_key)
                # ค้นหาโมเดลที่ใช้งานได้จริงในขณะนั้น
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                
                # พยายามใช้ flash ถ้าไม่มีให้ใช้ตัวแรกที่เจอ
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name)
                
                st.info(f"⌛ ใช้โมเดล {model_name} วิเคราะห์...")
                response = model.generate_content(f"วิเคราะห์หุ้น {ticker} ด้วย D.E.E.P.V เป็นภาษาไทย")
                st.write(response.text)
    except Exception as e:
        st.error(f"Error: {e}")
