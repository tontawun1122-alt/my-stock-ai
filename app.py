import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="D.E.E.P.V AI Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0e1117; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #1c1f26;
        border: 1px solid #2d313d;
        border-radius: 12px;
        padding: 16px 20px;
    }
    [data-testid="metric-container"] label {
        font-size: 0.75rem !important;
        color: #8b92a5 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #e8eaf0 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #13161e;
        border-right: 1px solid #2d313d;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #4f7cff, #7c4fff);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        width: 100%;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }

    /* Divider */
    hr { border-color: #2d313d !important; }

    /* AI result box */
    .ai-box {
        background: #1c1f26;
        border: 1px solid #2d313d;
        border-left: 3px solid #4f7cff;
        border-radius: 12px;
        padding: 24px;
        margin-top: 8px;
    }

    /* Section headers */
    .section-header {
        font-size: 0.7rem;
        font-weight: 600;
        color: #8b92a5;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 12px;
    }

    /* Status badge */
    .badge-up   { background:#0d2b1d; color:#34d399; border:1px solid #065f46;
                  border-radius:6px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
    .badge-down { background:#2b0d0d; color:#f87171; border:1px solid #7f1d1d;
                  border-radius:6px; padding:2px 10px; font-size:0.8rem; font-weight:600; }

    /* Radio buttons */
    .stRadio > div { flex-direction: row; gap: 8px; }
    .stRadio label { font-size: 0.8rem !important; }

    /* Hide streamlit default elements */
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────
def fmt_large(value: float) -> str:
    """Format large numbers: T / B / M"""
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    elif value >= 1e9:
        return f"${value/1e9:.2f}B"
    elif value >= 1e6:
        return f"${value/1e6:.2f}M"
    return f"${value:,.0f}"


def safe_pct_change(info: dict) -> float:
    """Return regularMarketChangePercent always as a proper % value."""
    raw = info.get("regularMarketChangePercent", 0) or 0
    # yfinance returns decimals (0.0596) or whole % (5.96) — normalise to %
    return raw * 100 if abs(raw) < 1.0 else raw


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock(ticker: str) -> dict | None:
    """Fetch stock info with caching (5 min TTL)."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            return None
        return {
            "name":        info.get("longName") or info.get("shortName") or ticker,
            "price":       info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "change":      safe_pct_change(info),
            "cap":         info.get("marketCap") or 0,
            "sector":      info.get("sector", "—"),
            "industry":    info.get("industry", "—"),
            "pe":          info.get("trailingPE"),
            "eps":         info.get("trailingEps"),
            "revenue":     info.get("totalRevenue"),
            "gross_margin":info.get("grossMargins"),
            "52w_high":    info.get("fiftyTwoWeekHigh"),
            "52w_low":     info.get("fiftyTwoWeekLow"),
            "ticker":      ticker,
        }
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(ticker: str, period: str) -> pd.DataFrame:
    """Fetch price history with caching."""
    return yf.Ticker(ticker).history(period=period)


def get_ai_analysis(api_key: str, ticker: str, stock_data: dict) -> str:
    """Run Gemini analysis with structured DEEPV prompt."""
    genai.configure(api_key=api_key)

    # Pick best available model
    try:
        available = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        preferred = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-pro"]
        model_name = next((m for m in preferred if m in available), available[0] if available else None)
        if not model_name:
            return "❌ ไม่พบโมเดล AI ที่ใช้งานได้"
    except Exception as e:
        return f"❌ ตรวจสอบ API Key ไม่สำเร็จ: {e}"

    prompt = f"""คุณเป็น AI Analyst ผู้เชี่ยวชาญด้านการวิเคราะห์หุ้นเชิงปัจจัยพื้นฐาน
วิเคราะห์หุ้น **{ticker}** ({stock_data['name']}) โดยใช้ Framework **D.E.E.P.V** เป็นภาษาไทย

ข้อมูลปัจจุบัน:
- ราคา: ${stock_data['price']}
- เปลี่ยนแปลง: {stock_data['change']:.2f}%
- Market Cap: {fmt_large(stock_data['cap'])}
- Sector: {stock_data['sector']} / {stock_data['industry']}
- P/E: {stock_data.get('pe', 'N/A')} | EPS: {stock_data.get('eps', 'N/A')}

วิเคราะห์ทีละหัวข้อ:

## D — Durability (ความทนทานของธุรกิจ)
วิเคราะห์ความสามารถในการแข่งขัน, moat, และความยั่งยืนของโมเดลธุรกิจ

## E — Earnings Quality (คุณภาพกำไร)
วิเคราะห์ revenue growth, margins, EPS trend, และความสม่ำเสมอของกำไร

## E — Execution (การบริหารจัดการ)
วิเคราะห์ผู้บริหาร, กลยุทธ์, allocation of capital

## P — Pricing Power (อำนาจการตั้งราคา)
วิเคราะห์ความสามารถในการขึ้นราคา, brand moat, switching cost

## V — Valuation (ราคาเหมาะสม)
วิเคราะห์ว่าราคาปัจจุบันแพงหรือถูก เทียบ P/E, EV/EBITDA กับ peers

## สรุปภาพรวม
ให้ Rating: 🟢 น่าสนใจ / 🟡 ระวัง / 🔴 หลีกเลี่ยง พร้อมเหตุผลสั้นๆ
"""
    try:
        model    = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาดในการวิเคราะห์: {e}"


# ─── Session State Init ──────────────────────────────────────────────────────────
for key in ("stock_data", "ai_result", "last_ticker"):
    if key not in st.session_state:
        st.session_state[key] = None


# ─── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 D.E.E.P.V Analyst")
    st.markdown('<p class="section-header">Configuration</p>', unsafe_allow_html=True)

    api_key      = st.text_input("Google Gemini API Key", type="password", placeholder="AIza...")
    ticker_input = st.text_input("Ticker Symbol", value="NVDA", placeholder="เช่น NVDA, AAPL, PTT.BK").upper().strip()

    analyze_btn  = st.button("🚀 วิเคราะห์หุ้น")

    st.divider()
    st.markdown('<p class="section-header">About</p>', unsafe_allow_html=True)
    st.caption(
        "D.E.E.P.V เป็น framework วิเคราะห์หุ้นเชิงคุณภาพ "
        "ครอบคลุม Durability, Earnings Quality, Execution, Pricing Power, และ Valuation"
    )


# ─── Main Logic ──────────────────────────────────────────────────────────────────
if analyze_btn and ticker_input:
    # Reset AI result if ticker changed
    if st.session_state.last_ticker != ticker_input:
        st.session_state.ai_result  = None
        st.session_state.last_ticker = ticker_input

    with st.spinner(f"กำลังโหลดข้อมูล {ticker_input}..."):
        data = fetch_stock(ticker_input)

    if data is None:
        st.error(f"❌ ไม่พบข้อมูลสำหรับ **{ticker_input}** — ตรวจสอบชื่อหุ้นอีกครั้ง")
    else:
        st.session_state.stock_data = data

        if api_key:
            with st.spinner("🧠 AI กำลังวิเคราะห์ DEEPV..."):
                st.session_state.ai_result = get_ai_analysis(api_key, ticker_input, data)
        else:
            st.warning("⚠️ ใส่ Google API Key ใน Sidebar เพื่อดูผลวิเคราะห์ AI")


# ─── Display ─────────────────────────────────────────────────────────────────────
if st.session_state.stock_data:
    d = st.session_state.stock_data

    # Header
    change_badge = (
        f'<span class="badge-up">▲ {d["change"]:.2f}%</span>'
        if d["change"] >= 0
        else f'<span class="badge-down">▼ {abs(d["change"]):.2f}%</span>'
    )
    st.markdown(f"## {d['name']} &nbsp; {change_badge}", unsafe_allow_html=True)
    st.caption(f"{d['ticker']} · {d['sector']} · {d['industry']}")

    # Metric row 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ราคาล่าสุด", f"${d['price']:,.2f}")
    c2.metric("Market Cap", fmt_large(d["cap"]))
    c3.metric("P/E Ratio", f"{d['pe']:.1f}x" if d.get("pe") else "—")
    c4.metric("EPS", f"${d['eps']:.2f}" if d.get("eps") else "—")

    # Metric row 2
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("52W High", f"${d['52w_high']:,.2f}" if d.get("52w_high") else "—")
    c6.metric("52W Low",  f"${d['52w_low']:,.2f}"  if d.get("52w_low")  else "—")
    c7.metric("Revenue",  fmt_large(d["revenue"])   if d.get("revenue") else "—")
    gm = d.get("gross_margin")
    c8.metric("Gross Margin", f"{gm*100:.1f}%" if gm else "—")

    st.divider()

    # Chart
    t_period = st.radio(
        "ช่วงเวลา",
        ["1d", "5d", "1mo", "3mo", "1y", "5y", "max"],
        index=4,
        horizontal=True,
    )

    with st.spinner("กำลังโหลดกราฟ..."):
        hist = fetch_history(d["ticker"], t_period)

    if not hist.empty:
        price_color = "#34d399" if hist["Close"].iloc[-1] >= hist["Close"].iloc[0] else "#f87171"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index, y=hist["Close"],
            mode="lines",
            line=dict(color=price_color, width=1.8),
            fill="tozeroy",
            fillcolor=price_color.replace(")", ", 0.08)").replace("rgb", "rgba") if "rgb" in price_color
                       else f"rgba(52, 211, 153, 0.08)" if "#34" in price_color else "rgba(248, 113, 113, 0.08)",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#13161e",
            margin=dict(l=0, r=0, t=16, b=0),
            height=320,
            xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5", size=11)),
            yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5", size=11),
                       tickprefix="$"),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("ไม่สามารถโหลดข้อมูลกราฟได้")

    # AI Result
    if st.session_state.ai_result:
        st.divider()
        st.markdown("### 🧠 ผลวิเคราะห์ D.E.E.P.V")
        st.markdown(
            f'<div class="ai-box">{st.session_state.ai_result}</div>',
            unsafe_allow_html=True,
        )
        st.balloons()

elif not analyze_btn:
    # Empty state
    st.markdown("""
    <div style="text-align:center; padding: 80px 0; color:#8b92a5;">
        <div style="font-size:3rem; margin-bottom:16px;">📊</div>
        <h3 style="color:#e8eaf0;">D.E.E.P.V AI Stock Analyst</h3>
        <p>ใส่ Ticker และกด "วิเคราะห์หุ้น" เพื่อเริ่มต้น</p>
        <p style="font-size:0.8rem; margin-top:24px;">
            Durability · Earnings Quality · Execution · Pricing Power · Valuation
        </p>
    </div>
    """, unsafe_allow_html=True)
