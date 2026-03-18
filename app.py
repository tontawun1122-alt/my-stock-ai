import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json, re
from datetime import datetime

st.set_page_config(page_title="D.E.E.P.V AI Analyst", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    [data-testid="metric-container"] {
        background: #1c1f26; border: 1px solid #2d313d;
        border-radius: 12px; padding: 14px 18px;
    }
    [data-testid="metric-container"] label {
        font-size: 0.72rem !important; color: #8b92a5 !important;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.25rem !important; font-weight: 700 !important; color: #e8eaf0 !important;
    }
    [data-testid="stSidebar"] { background: #13161e; border-right: 1px solid #2d313d; }
    .stButton > button {
        background: linear-gradient(135deg, #4f7cff, #7c4fff);
        color: white; border: none; border-radius: 8px;
        padding: 10px 20px; font-weight: 600; width: 100%;
    }
    hr { border-color: #2d313d !important; }
    .deepv-card { background: #1c1f26; border: 1px solid #2d313d; border-radius: 12px; padding: 20px; margin-bottom: 12px; }
    .section-label { font-size: 0.68rem; color: #8b92a5; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; margin-top: 4px; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    /* Mobile responsive */
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem; }
    }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────
def fmt_large(v):
    if not v or v == 0: return "—"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e12: return f"{sign}${v/1e12:.2f}T"
    if v >= 1e9:  return f"{sign}${v/1e9:.2f}B"
    if v >= 1e6:  return f"{sign}${v/1e6:.2f}M"
    return f"{sign}${v:,.0f}"

def calc_pct(info):
    cur  = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    prev = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
    return ((cur - prev) / prev * 100) if prev else 0.0

def sc(s): return "#34d399" if s>=70 else "#fbbf24" if s>=40 else "#f87171"
def ll(l): return {"green":"🟢 เสี่ยงต่ำ","yellow":"🟡 เสี่ยงกลาง","red":"🔴 เสี่ยงสูง"}.get(l,"—")
def pct(v):  return f"{v*100:.1f}%" if v else "—"
def usd(v):  return f"${v:,.2f}" if v else "—"
def xf(v):   return f"{v:.1f}x" if v else "—"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        if not info or (not info.get("currentPrice") and not info.get("regularMarketPrice")):
            return None
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "ticker": ticker,
            "change": calc_pct(info),
            "sector": info.get("sector","—"), "industry": info.get("industry","—"),
            "website": info.get("website",""),
            "description": info.get("longBusinessSummary",""),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country","—"),
            "founded": info.get("founded"),
            "price": info.get("currentPrice") or info.get("regularMarketPrice",0),
            "prev_close": info.get("previousClose"),
            "open": info.get("open"), "day_high": info.get("dayHigh"), "day_low": info.get("dayLow"),
            "52w_high": info.get("fiftyTwoWeekHigh"), "52w_low": info.get("fiftyTwoWeekLow"),
            "target_price": info.get("targetMeanPrice"),
            "cap": info.get("marketCap",0),
            "pe": info.get("trailingPE"), "fwd_pe": info.get("forwardPE"),
            "peg": info.get("pegRatio"), "pb": info.get("priceToBook"),
            "ps": info.get("priceToSalesTrailing12Months"), "ev_ebitda": info.get("enterpriseToEbitda"),
            "eps": info.get("trailingEps"), "fwd_eps": info.get("forwardEps"),
            "revenue": info.get("totalRevenue"), "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "gross_margin": info.get("grossMargins"), "op_margin": info.get("operatingMargins"),
            "net_margin": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"), "roa": info.get("returnOnAssets"),
            "fcf": info.get("freeCashflow"), "ebitda": info.get("ebitda"),
            "total_cash": info.get("totalCash"), "total_debt": info.get("totalDebt"),
            "debt_equity": info.get("debtToEquity"), "current_ratio": info.get("currentRatio"),
            "dividend_yield": info.get("dividendYield"), "beta": info.get("beta"),
            "short_ratio": info.get("shortRatio"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "analyst_rating": info.get("recommendationKey","").upper(),
        }
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(ticker, period):
    return yf.Ticker(ticker).history(period=period)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financials(ticker):
    t = yf.Ticker(ticker)
    try:
        inc = t.financials
        return inc
    except:
        return None


def get_deepv_analysis(api_key, ticker, d) -> dict:
    genai.configure(api_key=api_key)
    try:
        available = [m.name for m in genai.list_models()
                     if "generateContent" in m.supported_generation_methods]
        preferred = ["models/gemini-1.5-pro","models/gemini-1.5-flash","models/gemini-pro"]
        mn = next((m for m in preferred if m in available), available[0] if available else None)
        if not mn: return {"error":"ไม่พบโมเดล AI"}
    except Exception as e:
        return {"error": str(e)}

    prompt = f"""วิเคราะห์หุ้น {ticker} ({d['name']}) ด้วย D.E.E.P.V Framework
ข้อมูล: ราคา ${d['price']} | {d['change']:.2f}% | MCap {fmt_large(d['cap'])}
P/E {d.get('pe','N/A')} | Fwd P/E {d.get('fwd_pe','N/A')} | PEG {d.get('peg','N/A')}
Revenue {fmt_large(d.get('revenue'))} | Rev Growth {pct(d.get('revenue_growth'))}
GM {pct(d.get('gross_margin'))} | Op Margin {pct(d.get('op_margin'))} | Net {pct(d.get('net_margin'))}
ROE {pct(d.get('roe'))} | FCF {fmt_large(d.get('fcf'))} | D/E {d.get('debt_equity','N/A')} | Beta {d.get('beta','N/A')}
Sector: {d['sector']} / {d['industry']}

ตอบ JSON เท่านั้น ไม่มี backtick:
{{"dimensions":{{"D":{{"name":"Durability","score":0,"level":"green","summary":"","analysis":""}},"E1":{{"name":"Earnings Quality","score":0,"level":"green","summary":"","analysis":""}},"E2":{{"name":"Execution","score":0,"level":"green","summary":"","analysis":""}},"P":{{"name":"Pricing Power","score":0,"level":"green","summary":"","analysis":""}},"V":{{"name":"Valuation","score":0,"level":"green","summary":"","analysis":""}}}},"overall_score":0,"overall_level":"green","recommendation":"BUY","summary":"","risks":"","catalysts":""}}
level: 70-100=green, 40-69=yellow, 0-39=red | recommendation: BUY/HOLD/AVOID"""

    try:
        resp = genai.GenerativeModel(mn).generate_content(prompt)
        text = re.sub(r'^```json\s*|\s*```$','', resp.text.strip())
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error":"parse_failed","raw": resp.text}
    except Exception as e:
        return {"error": str(e)}


def generate_html_report(ticker, d, ai) -> str:
    dims=ai.get("dimensions",{}); overall=ai.get("overall_score",0)
    rec=ai.get("recommendation","—"); rc={"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
    oc=sc(overall); now=datetime.now().strftime("%d %b %Y %H:%M")
    rows="".join([f"""<div style="margin-bottom:14px;padding:16px;background:#1c1f26;border-radius:10px;border-left:3px solid {sc(dim.get('score',0))}">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="font-size:1.2rem;font-weight:800;color:{sc(dim.get('score',0))}">{k}</span>
        <span style="font-size:0.9rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</span>
        <span style="margin-left:auto;color:{sc(dim.get('score',0))};font-weight:700">{dim.get('score',0)}/100</span>
        <span style="background:{sc(dim.get('score',0))}22;color:{sc(dim.get('score',0))};border:1px solid {sc(dim.get('score',0))}44;border-radius:5px;padding:1px 8px;font-size:0.72rem">{ll(dim.get('level',''))}</span>
      </div>
      <div style="background:#2d313d;border-radius:999px;height:4px;margin-bottom:8px;overflow:hidden">
        <div style="background:{sc(dim.get('score',0))};width:{dim.get('score',0)}%;height:100%;border-radius:999px"></div></div>
      <p style="color:#8b92a5;margin:0 0 4px;font-size:0.78rem">{dim.get('summary','')}</p>
      <p style="color:#c5c9d6;margin:0;font-size:0.85rem;line-height:1.6">{dim.get('analysis','')}</p></div>""" for k,dim in dims.items()])
    return f"""<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DEEPV: {ticker}</title><style>body{{font-family:'Segoe UI',sans-serif;background:#0e1117;color:#e8eaf0;margin:0;padding:24px;max-width:860px;margin:0 auto}}
.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}}.c{{background:#1c1f26;border-radius:8px;padding:12px}}
.cl{{font-size:0.68rem;color:#8b92a5;text-transform:uppercase}}.cv{{font-size:1.05rem;font-weight:700}}
@media(max-width:600px){{.g{{grid-template-columns:repeat(2,1fr)}}}}</style></head><body>
<div style="border-bottom:1px solid #2d313d;padding-bottom:16px;margin-bottom:18px">
  <div style="font-size:0.7rem;color:#8b92a5">DEEPV AI Analyst · {now}</div>
  <h1 style="margin:4px 0 0;font-size:1.5rem">{d.get('name',ticker)} <span style="color:#8b92a5;font-size:0.85rem">({ticker})</span></h1>
  <div style="margin-top:8px;display:flex;flex-wrap:wrap;align-items:center;gap:16px">
    <span style="font-size:1.3rem;font-weight:700">${d.get('price',0):,.2f}</span>
    <div style="text-align:center"><div style="font-size:1.8rem;font-weight:800;color:{oc}">{overall}</div><div style="font-size:0.6rem;color:#8b92a5">DEEPV SCORE</div></div>
    <div style="text-align:center"><div style="font-size:1.2rem;font-weight:800;color:{rc}">{rec}</div><div style="font-size:0.6rem;color:#8b92a5">SIGNAL</div></div>
  </div>
</div>
<div class="g">
  <div class="c"><div class="cl">Market Cap</div><div class="cv">{fmt_large(d.get('cap',0))}</div></div>
  <div class="c"><div class="cl">Forward P/E</div><div class="cv">{xf(d.get('fwd_pe'))}</div></div>
  <div class="c"><div class="cl">Gross Margin</div><div class="cv">{pct(d.get('gross_margin'))}</div></div>
  <div class="c"><div class="cl">Revenue</div><div class="cv">{fmt_large(d.get('revenue'))}</div></div>
  <div class="c"><div class="cl">ROE</div><div class="cv">{pct(d.get('roe'))}</div></div>
  <div class="c"><div class="cl">Beta</div><div class="cv">{d.get('beta','—')}</div></div>
</div>
{rows}
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
  <div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid #34d399">
    <div style="font-size:0.66rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">✅ ปัจจัยบวก</div>
    <p style="margin:0;color:#c5c9d6;font-size:0.85rem;line-height:1.6">{ai.get('catalysts','')}</p></div>
  <div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid #f87171">
    <div style="font-size:0.66rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">⚠️ ความเสี่ยง</div>
    <p style="margin:0;color:#c5c9d6;font-size:0.85rem;line-height:1.6">{ai.get('risks','')}</p></div>
</div>
<div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid {rc}">
  <div style="font-size:0.66rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">🧠 สรุปภาพรวม</div>
  <p style="margin:0;line-height:1.7;color:#c5c9d6">{ai.get('summary','')}</p></div>
</body></html>"""


# ─── Session State ───────────────────────────────────────────────────────────────
for k in ("results","portfolio"):
    if k not in st.session_state:
        st.session_state[k] = {} if k=="results" else []


# ─── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 D.E.E.P.V")
    st.markdown('<p style="font-size:0.7rem;color:#8b92a5;margin-top:-8px">AI Stock Analyst</p>', unsafe_allow_html=True)
    api_key = st.text_input("Google Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")
    st.markdown("**🔍 วิเคราะห์หุ้น**")
    st.caption("รองรับ US (NVDA) และไทย (PTT.BK)")
    t1 = st.text_input("หุ้นตัวที่ 1", value="NVDA").upper().strip()
    t2 = st.text_input("หุ้นตัวที่ 2", value="").upper().strip()
    t3 = st.text_input("หุ้นตัวที่ 3", value="").upper().strip()
    btn = st.button("🚀 วิเคราะห์หุ้น")
    st.divider()
    st.caption("D · Durability\nE · Earnings Quality\nE · Execution\nP · Pricing Power\nV · Valuation")


# ─── Run Analysis ────────────────────────────────────────────────────────────────
tickers_input = [t for t in [t1,t2,t3] if t]
if btn and tickers_input:
    st.session_state.results = {}
    for ticker in tickers_input:
        with st.spinner(f"กำลังโหลด {ticker}..."):
            data = fetch_stock(ticker)
        if data is None:
            st.error(f"❌ ไม่พบข้อมูล {ticker}")
            continue
        ai = None
        if api_key:
            with st.spinner(f"🧠 AI วิเคราะห์ {ticker}..."):
                ai = get_deepv_analysis(api_key, ticker, data)
        st.session_state.results[ticker] = {"data": data, "ai": ai}


# ─── Main Display ────────────────────────────────────────────────────────────────
results = st.session_state.results

# ═══ LANDING PAGE (ถ้ายังไม่ได้วิเคราะห์) ════════════════════════════════════════
if not results:
    st.markdown("""
    <div style="padding: 48px 0 32px; text-align:center">
        <div style="font-size:0.75rem;color:#4f7cff;text-transform:uppercase;letter-spacing:.15em;margin-bottom:12px">
            AI-Powered Fundamental Analysis
        </div>
        <h1 style="font-size:2.8rem;font-weight:800;color:#e8eaf0;margin:0 0 12px">
            D.E.E.P.V <span style="background:linear-gradient(135deg,#4f7cff,#7c4fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Analyst</span>
        </h1>
        <p style="color:#8b92a5;font-size:1rem;max-width:480px;margin:0 auto 40px;line-height:1.7">
            วิเคราะห์หุ้นเชิงลึกด้วย AI ครอบคลุม 5 มิติ พร้อมคะแนน DEEPV Score และ Signal ที่ชัดเจน
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    col1, col2, col3, col4 = st.columns(4)
    features = [
        ("📐", "DEEPV Score", "คะแนน 0-100 พร้อม Traffic Light แต่ละมิติ"),
        ("⚖️", "เปรียบเทียบ", "วิเคราะห์สูงสุด 3 หุ้นพร้อมกัน"),
        ("💼", "Portfolio", "จำลอง Asset Allocation พอร์ตลงทุน"),
        ("📄", "Report", "ดาวน์โหลดรายงาน DEEPV เป็น HTML"),
    ]
    for col, (icon, title, desc) in zip([col1,col2,col3,col4], features):
        col.markdown(f"""
        <div style="background:#1c1f26;border:1px solid #2d313d;border-radius:12px;padding:20px;text-align:center;height:140px">
            <div style="font-size:1.8rem;margin-bottom:8px">{icon}</div>
            <div style="font-weight:600;color:#e8eaf0;margin-bottom:4px">{title}</div>
            <div style="font-size:0.78rem;color:#8b92a5;line-height:1.5">{desc}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Framework explanation
    st.markdown("""
    <div style="background:#1c1f26;border:1px solid #2d313d;border-radius:12px;padding:24px;margin-bottom:24px">
        <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px">DEEPV Framework คืออะไร?</div>
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;text-align:center">
            <div><div style="font-size:1.5rem;font-weight:800;color:#4f7cff">D</div><div style="font-size:0.8rem;font-weight:600;color:#e8eaf0">Durability</div><div style="font-size:0.72rem;color:#8b92a5">ความทนทาน</div></div>
            <div><div style="font-size:1.5rem;font-weight:800;color:#7c4fff">E</div><div style="font-size:0.8rem;font-weight:600;color:#e8eaf0">Earnings</div><div style="font-size:0.72rem;color:#8b92a5">คุณภาพกำไร</div></div>
            <div><div style="font-size:1.5rem;font-weight:800;color:#a78bfa">E</div><div style="font-size:0.8rem;font-weight:600;color:#e8eaf0">Execution</div><div style="font-size:0.72rem;color:#8b92a5">การบริหาร</div></div>
            <div><div style="font-size:1.5rem;font-weight:800;color:#34d399">P</div><div style="font-size:0.8rem;font-weight:600;color:#e8eaf0">Pricing Power</div><div style="font-size:0.72rem;color:#8b92a5">อำนาจตั้งราคา</div></div>
            <div><div style="font-size:1.5rem;font-weight:800;color:#fbbf24">V</div><div style="font-size:0.8rem;font-weight:600;color:#e8eaf0">Valuation</div><div style="font-size:0.72rem;color:#8b92a5">ราคาเหมาะสม</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("👈 ใส่ Ticker ใน Sidebar แล้วกด **วิเคราะห์หุ้น** เพื่อเริ่มต้น")

# ═══ RESULTS ════════════════════════════════════════════════════════════════════
else:
    tickers_ready = list(results.keys())
    tab_labels = [f"📈 {t}" for t in tickers_ready]
    if len(tickers_ready) > 1: tab_labels.append("⚖️ เปรียบเทียบ")
    tab_labels.append("💼 Portfolio")
    tabs = st.tabs(tab_labels)

    # ── Per-ticker tabs ──────────────────────────────────────────────────────────
    for i, ticker in enumerate(tickers_ready):
        with tabs[i]:
            d  = results[ticker]["data"]
            ai = results[ticker]["ai"]

            cc = "#34d399" if d["change"]>=0 else "#f87171"
            arrow = "▲" if d["change"]>=0 else "▼"

            # Header
            st.markdown(f"""
            <div style="margin-bottom:4px">
              <span style="font-size:1.5rem;font-weight:700;color:#e8eaf0">{d['name']}</span>
              <span style="color:#8b92a5;font-size:0.85rem;margin-left:8px">{ticker}</span>
              <span style="color:{cc};font-size:0.9rem;font-weight:600;margin-left:10px">{arrow} {abs(d['change']):.2f}%</span>
            </div>
            <div style="font-size:0.78rem;color:#8b92a5;margin-bottom:16px">{d['sector']} · {d['industry']} · {d.get('country','')}</div>
            """, unsafe_allow_html=True)

            # Company Description
            if d.get("description"):
                with st.expander("📋 เกี่ยวกับบริษัท", expanded=False):
                    st.markdown(f'<p style="color:#c5c9d6;font-size:0.88rem;line-height:1.7">{d["description"][:800]}{"..." if len(d["description"])>800 else ""}</p>', unsafe_allow_html=True)
                    info_cols = st.columns(3)
                    if d.get("employees"):
                        info_cols[0].metric("พนักงาน", f"{d['employees']:,} คน")
                    if d.get("website"):
                        info_cols[1].markdown(f'<a href="{d["website"]}" target="_blank" style="color:#4f7cff;font-size:0.85rem">🌐 {d["website"]}</a>', unsafe_allow_html=True)

            # ── Pricing
            st.markdown('<div class="section-label">💰 ราคา</div>', unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("ราคาล่าสุด", f"${d['price']:,.2f}")
            c2.metric("Prev Close",  usd(d.get("prev_close")))
            c3.metric("Day High",    usd(d.get("day_high")))
            c4.metric("Day Low",     usd(d.get("day_low")))
            c5,c6,c7,c8 = st.columns(4)
            c5.metric("52W High",      usd(d.get("52w_high")))
            c6.metric("52W Low",       usd(d.get("52w_low")))
            c7.metric("Target Price",  usd(d.get("target_price")))
            c8.metric("Market Cap",    fmt_large(d["cap"]))

            # ── Valuation
            st.markdown('<div class="section-label" style="margin-top:16px">📐 Valuation</div>', unsafe_allow_html=True)
            v1,v2,v3,v4 = st.columns(4)
            v1.metric("P/E (Trailing)", xf(d.get("pe")))
            v2.metric("P/E (Forward)",  xf(d.get("fwd_pe")))
            v3.metric("PEG Ratio",      xf(d.get("peg")))
            v4.metric("P/B Ratio",      xf(d.get("pb")))
            v5,v6,v7,v8 = st.columns(4)
            v5.metric("P/S Ratio",   xf(d.get("ps")))
            v6.metric("EV/EBITDA",   xf(d.get("ev_ebitda")))
            v7.metric("EPS (Trail)", usd(d.get("eps")))
            v8.metric("EPS (Fwd)",   usd(d.get("fwd_eps")))

            # ── Financials
            st.markdown('<div class="section-label" style="margin-top:16px">📊 Financials</div>', unsafe_allow_html=True)
            f1,f2,f3,f4 = st.columns(4)
            f1.metric("Revenue",        fmt_large(d.get("revenue")))
            f2.metric("Revenue Growth", pct(d.get("revenue_growth")))
            f3.metric("Gross Margin",   pct(d.get("gross_margin")))
            f4.metric("Op Margin",      pct(d.get("op_margin")))
            f5,f6,f7,f8 = st.columns(4)
            f5.metric("Net Margin",     pct(d.get("net_margin")))
            f6.metric("ROE",            pct(d.get("roe")))
            f7.metric("ROA",            pct(d.get("roa")))
            f8.metric("Free Cash Flow", fmt_large(d.get("fcf")))

            # ── Balance Sheet
            st.markdown('<div class="section-label" style="margin-top:16px">🏦 Balance Sheet & Risk</div>', unsafe_allow_html=True)
            b1,b2,b3,b4 = st.columns(4)
            b1.metric("Total Cash",    fmt_large(d.get("total_cash")))
            b2.metric("Total Debt",    fmt_large(d.get("total_debt")))
            b3.metric("Debt/Equity",   f"{d['debt_equity']:.1f}" if d.get("debt_equity") else "—")
            b4.metric("Current Ratio", f"{d['current_ratio']:.2f}" if d.get("current_ratio") else "—")
            b5,b6,b7,b8 = st.columns(4)
            b5.metric("Beta",           f"{d['beta']:.2f}" if d.get("beta") else "—")
            b6.metric("Dividend Yield", pct(d.get("dividend_yield")))
            b7.metric("Short Ratio",    f"{d['short_ratio']:.1f}x" if d.get("short_ratio") else "—")
            b8.metric("Analyst Rating", d.get("analyst_rating","—"))

            st.divider()

            # ── Price Chart
            st.markdown('<div class="section-label">📈 กราฟราคา</div>', unsafe_allow_html=True)
            t_period = st.radio("ช่วงเวลา",["1d","5d","1mo","3mo","1y","5y","max"],
                                index=4, horizontal=True, key=f"p_{ticker}")
            hist = fetch_history(ticker, t_period)
            if not hist.empty:
                up  = hist["Close"].iloc[-1]>=hist["Close"].iloc[0]
                clr = "#34d399" if up else "#f87171"
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist["Close"], mode="lines",
                    line=dict(color=clr, width=1.8), fill="tozeroy",
                    fillcolor="rgba(52,211,153,0.07)" if up else "rgba(248,113,113,0.07)",
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>",
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                    margin=dict(l=0,r=0,t=16,b=0), height=280,
                    xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5",size=11)),
                    yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5",size=11), tickprefix="$"),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

            # ── Historical Financials Chart
            st.markdown('<div class="section-label" style="margin-top:8px">📉 Historical Financials</div>', unsafe_allow_html=True)
            with st.spinner("โหลด Historical Financials..."):
                fin = fetch_financials(ticker)
            if fin is not None and not fin.empty:
                try:
                    fin_t = fin.T
                    fin_t.index = pd.to_datetime(fin_t.index)
                    fin_t = fin_t.sort_index()
                    fig_fin = go.Figure()
                    if "Total Revenue" in fin_t.columns:
                        fig_fin.add_trace(go.Bar(
                            x=fin_t.index.year, y=fin_t["Total Revenue"]/1e9,
                            name="Revenue ($B)", marker_color="#4f7cff", opacity=0.85,
                        ))
                    if "Net Income" in fin_t.columns:
                        fig_fin.add_trace(go.Bar(
                            x=fin_t.index.year, y=fin_t["Net Income"]/1e9,
                            name="Net Income ($B)", marker_color="#34d399", opacity=0.85,
                        ))
                    if "Gross Profit" in fin_t.columns:
                        fig_fin.add_trace(go.Bar(
                            x=fin_t.index.year, y=fin_t["Gross Profit"]/1e9,
                            name="Gross Profit ($B)", marker_color="#7c4fff", opacity=0.85,
                        ))
                    fig_fin.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                        barmode="group", height=280,
                        margin=dict(l=0,r=0,t=16,b=0),
                        xaxis=dict(tickfont=dict(color="#8b92a5",size=11)),
                        yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5",size=11), ticksuffix="B"),
                        legend=dict(font=dict(color="#8b92a5",size=11), bgcolor="rgba(0,0,0,0)"),
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_fin, use_container_width=True)
                except:
                    st.caption("ไม่สามารถแสดง Historical Financials ได้")

            # ── DEEPV Analysis
            if ai and "dimensions" in ai:
                st.divider()
                overall = ai.get("overall_score",0)
                rec     = ai.get("recommendation","—")
                rc      = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
                oc      = sc(overall)

                st.markdown(f"""
                <div style="background:#1c1f26;border-radius:12px;padding:20px;margin-bottom:20px;
                            display:flex;align-items:center;gap:20px;border:1px solid #2d313d">
                  <div style="text-align:center;min-width:65px">
                    <div style="font-size:2.2rem;font-weight:800;color:{oc}">{overall}</div>
                    <div style="font-size:0.6rem;color:#8b92a5;text-transform:uppercase">DEEPV Score</div>
                  </div>
                  <div style="flex:1">
                    <div style="background:#2d313d;border-radius:999px;height:8px;overflow:hidden">
                      <div style="background:linear-gradient(90deg,#f87171,#fbbf24,#34d399);width:100%;height:100%;border-radius:999px;opacity:0.3"></div>
                    </div>
                    <div style="background:#2d313d;border-radius:999px;height:8px;overflow:hidden;margin-top:-8px">
                      <div style="background:{oc};width:{overall}%;height:100%;border-radius:999px"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:4px">
                      <span style="font-size:0.65rem;color:#f87171">เสี่ยงสูง 0-39</span>
                      <span style="font-size:0.65rem;color:#fbbf24">เสี่ยงกลาง 40-69</span>
                      <span style="font-size:0.65rem;color:#34d399">เสี่ยงต่ำ 70-100</span>
                    </div>
                  </div>
                  <div style="text-align:center;min-width:75px">
                    <div style="font-size:1.4rem;font-weight:800;color:{rc};background:{rc}18;border:1px solid {rc}44;border-radius:8px;padding:6px 12px">{rec}</div>
                    <div style="font-size:0.6rem;color:#8b92a5;text-transform:uppercase;margin-top:4px">Signal</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                for key, dim in ai.get("dimensions",{}).items():
                    s = dim.get("score",0); lc=sc(s); lbl=ll(dim.get("level","yellow"))
                    st.markdown(f"""
                    <div class="deepv-card" style="border-left:3px solid {lc}">
                      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
                        <span style="font-size:1.6rem;font-weight:800;color:{lc};min-width:38px">{key}</span>
                        <div><div style="font-size:0.95rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</div>
                        <div style="font-size:0.78rem;color:#8b92a5">{dim.get('summary','')}</div></div>
                        <div style="margin-left:auto;text-align:right">
                          <div style="font-size:1.4rem;font-weight:700;color:{lc}">{s}<span style="font-size:0.75rem;color:#8b92a5">/100</span></div>
                          <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;border-radius:6px;padding:1px 7px;font-size:0.72rem">{lbl}</span>
                        </div>
                      </div>
                      <div style="height:4px;background:#2d313d;border-radius:999px;margin-bottom:11px;overflow:hidden">
                        <div style="background:{lc};width:{s}%;height:100%;border-radius:999px"></div></div>
                      <p style="color:#c5c9d6;margin:0;font-size:0.88rem;line-height:1.7">{dim.get('analysis','')}</p>
                    </div>""", unsafe_allow_html=True)

                col_l,col_r = st.columns(2)
                with col_l:
                    st.markdown(f"""<div style="background:#1c1f26;border-radius:12px;padding:16px;border-left:3px solid #34d399">
                      <div style="font-size:0.66rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">✅ ปัจจัยบวก</div>
                      <p style="color:#c5c9d6;margin:0;line-height:1.7;font-size:0.88rem">{ai.get('catalysts','—')}</p></div>""", unsafe_allow_html=True)
                with col_r:
                    st.markdown(f"""<div style="background:#1c1f26;border-radius:12px;padding:16px;border-left:3px solid #f87171">
                      <div style="font-size:0.66rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">⚠️ ความเสี่ยง</div>
                      <p style="color:#c5c9d6;margin:0;line-height:1.7;font-size:0.88rem">{ai.get('risks','—')}</p></div>""", unsafe_allow_html=True)

                st.markdown(f"""<div style="background:#1c1f26;border-radius:12px;padding:16px;border-left:3px solid {rc};margin-top:12px">
                  <div style="font-size:0.66rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">🧠 สรุปภาพรวม</div>
                  <p style="color:#c5c9d6;margin:0;line-height:1.7">{ai.get('summary','')}</p></div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                html_r = generate_html_report(ticker, d, ai)
                st.download_button("📄 ดาวน์โหลด DEEPV Report",
                    data=html_r.encode("utf-8"),
                    file_name=f"DEEPV_{ticker}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html", key=f"dl_{ticker}")
                st.balloons()

            elif ai and "raw" in ai:
                st.markdown(f'<div style="background:#1c1f26;border-radius:12px;padding:20px;color:#c5c9d6">{ai["raw"]}</div>', unsafe_allow_html=True)
            elif ai and "error" in ai:
                st.error(f"❌ {ai['error']}")
            elif not api_key:
                st.info("💡 ใส่ Google Gemini API Key เพื่อดูผลวิเคราะห์ DEEPV")

    # ── Compare Tab ──────────────────────────────────────────────────────────────
    compare_idx = len(tickers_ready) if len(tickers_ready)>1 else None
    if compare_idx:
        with tabs[compare_idx]:
            st.markdown("### ⚖️ เปรียบเทียบ DEEPV Score")
            has_ai = {t:r["ai"] for t,r in results.items() if r["ai"] and "dimensions" in r["ai"]}
            palette = ["#4f7cff","#34d399","#fbbf24"]

            if has_ai:
                dim_keys  = ["D","E1","E2","P","V"]
                dim_names = ["Durability","Earnings","Execution","Pricing","Valuation"]
                fig = go.Figure()
                for idx,(t,aai) in enumerate(has_ai.items()):
                    scores=[aai["dimensions"].get(k,{}).get("score",0) for k in dim_keys]
                    fig.add_trace(go.Bar(name=t,x=dim_names,y=scores,marker_color=palette[idx%len(palette)]))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                    barmode="group", height=340,
                    yaxis=dict(range=[0,100],gridcolor="#1c2030",tickfont=dict(color="#8b92a5")),
                    xaxis=dict(tickfont=dict(color="#8b92a5")),
                    legend=dict(font=dict(color="#8b92a5"),bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0,r=0,t=16,b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### คะแนนแยกรายด้าน")
                td={}
                for t,aai in has_ai.items():
                    row={}
                    for k in dim_keys:
                        s=aai["dimensions"].get(k,{}).get("score",0)
                        lv=aai["dimensions"].get(k,{}).get("level","yellow")
                        row[k]=f'{"🟢" if lv=="green" else "🟡" if lv=="yellow" else "🔴"} {s}'
                    row["Overall"]=aai.get("overall_score",0); row["Signal"]=aai.get("recommendation","—")
                    td[t]=row
                st.dataframe(pd.DataFrame(td).T, use_container_width=True)
            else:
                st.info("ต้องวิเคราะห์หุ้นอย่างน้อย 2 ตัวพร้อม API Key")

            st.markdown("#### เปรียบเทียบราคา (Normalized %)")
            cmp_p = st.radio("ช่วงเวลา",["1mo","3mo","1y","5y"],index=2,horizontal=True,key="cmp")
            fig2=go.Figure()
            for idx,t in enumerate(tickers_ready):
                h=fetch_history(t,cmp_p)
                if not h.empty:
                    norm=(h["Close"]/h["Close"].iloc[0])*100
                    fig2.add_trace(go.Scatter(x=h.index,y=norm,name=t,
                        line=dict(color=palette[idx%len(palette)],width=2),
                        hovertemplate=f"<b>{t}</b>: %{{y:.1f}}%<extra></extra>"))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e", height=300,
                xaxis=dict(showgrid=False,tickfont=dict(color="#8b92a5",size=11)),
                yaxis=dict(gridcolor="#1c2030",tickfont=dict(color="#8b92a5",size=11),ticksuffix="%"),
                legend=dict(font=dict(color="#8b92a5"),bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0,r=0,t=16,b=0),hovermode="x unified",
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Portfolio Tab ─────────────────────────────────────────────────────────────
    with tabs[-1]:
        st.markdown("### 💼 Portfolio Simulator")
        st.caption("จำลอง Asset Allocation และดู return ของพอร์ตลงทุน")

        # Add stock to portfolio
        col_a, col_b, col_c = st.columns([2,1,1])
        with col_a:
            port_ticker = st.text_input("เพิ่มหุ้น", placeholder="เช่น NVDA, AAPL, PTT.BK").upper().strip()
        with col_b:
            port_alloc = st.number_input("% สัดส่วน", min_value=1, max_value=100, value=25, step=5)
        with col_c:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ เพิ่มหุ้น"):
                if port_ticker:
                    # Check duplicate
                    existing = [p["ticker"] for p in st.session_state.portfolio]
                    if port_ticker in existing:
                        st.warning(f"{port_ticker} อยู่ในพอร์ตแล้ว")
                    else:
                        with st.spinner(f"โหลด {port_ticker}..."):
                            pdata = fetch_stock(port_ticker)
                        if pdata:
                            st.session_state.portfolio.append({
                                "ticker": port_ticker,
                                "name": pdata["name"],
                                "alloc": port_alloc,
                                "price": pdata["price"],
                                "change": pdata["change"],
                                "sector": pdata["sector"],
                                "pe": pdata.get("pe"),
                                "beta": pdata.get("beta"),
                                "cap": pdata.get("cap"),
                            })
                            st.rerun()
                        else:
                            st.error(f"ไม่พบ {port_ticker}")

        # Auto-add from analyzed tickers
        if results and st.button("📥 นำเข้าหุ้นที่วิเคราะห์แล้ว"):
            existing = [p["ticker"] for p in st.session_state.portfolio]
            added = 0
            for t, r in results.items():
                if t not in existing and r["data"]:
                    d_ = r["data"]
                    equal_alloc = round(100 / (len(results) + len(existing)))
                    st.session_state.portfolio.append({
                        "ticker": t, "name": d_["name"],
                        "alloc": equal_alloc, "price": d_["price"],
                        "change": d_["change"], "sector": d_["sector"],
                        "pe": d_.get("pe"), "beta": d_.get("beta"), "cap": d_.get("cap"),
                    })
                    added += 1
            if added: st.rerun()

        portfolio = st.session_state.portfolio

        if not portfolio:
            st.markdown("""
            <div style="text-align:center;padding:48px 0;color:#8b92a5">
                <div style="font-size:2.5rem;margin-bottom:12px">💼</div>
                <p>ยังไม่มีหุ้นในพอร์ต — เพิ่มหุ้นด้านบนหรือนำเข้าจากที่วิเคราะห์แล้ว</p>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("---")

            # Edit allocations
            st.markdown("#### ปรับสัดส่วน Portfolio")
            total_alloc = 0
            updated_portfolio = []
            for idx, p in enumerate(portfolio):
                col1, col2, col3, col4 = st.columns([3,2,1,1])
                with col1:
                    cc_ = "#34d399" if p["change"]>=0 else "#f87171"
                    st.markdown(f"""<div style="padding:8px 0">
                        <span style="font-weight:600;color:#e8eaf0">{p['ticker']}</span>
                        <span style="color:#8b92a5;font-size:0.8rem;margin-left:8px">{p['name'][:25]}</span>
                        <span style="color:{cc_};font-size:0.8rem;margin-left:8px">{"▲" if p["change"]>=0 else "▼"}{abs(p["change"]):.1f}%</span>
                    </div>""", unsafe_allow_html=True)
                with col2:
                    new_alloc = st.slider("", 1, 100, p["alloc"], key=f"sl_{idx}", label_visibility="collapsed")
                    p["alloc"] = new_alloc
                with col3:
                    st.markdown(f'<div style="padding-top:10px;font-weight:700;color:#4f7cff">{new_alloc}%</div>', unsafe_allow_html=True)
                with col4:
                    if st.button("🗑️", key=f"del_{idx}"):
                        st.session_state.portfolio.pop(idx)
                        st.rerun()
                total_alloc += new_alloc
                updated_portfolio.append(p)

            st.session_state.portfolio = updated_portfolio

            # Total check
            alloc_color = "#34d399" if total_alloc==100 else "#fbbf24" if total_alloc<100 else "#f87171"
            st.markdown(f'<div style="text-align:right;font-size:0.85rem;color:{alloc_color};margin-bottom:16px">รวมสัดส่วน: <strong>{total_alloc}%</strong> {"✅" if total_alloc==100 else "⚠️ ควรรวมเป็น 100%"}</div>', unsafe_allow_html=True)

            st.markdown("---")

            # ── Portfolio Charts
            col_pie, col_sector = st.columns(2)

            with col_pie:
                st.markdown("#### Asset Allocation")
                fig_pie = go.Figure(go.Pie(
                    labels=[p["ticker"] for p in portfolio],
                    values=[p["alloc"] for p in portfolio],
                    hole=0.5,
                    marker=dict(colors=["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa","#fb923c"][:len(portfolio)]),
                    textinfo="label+percent",
                    textfont=dict(color="#e8eaf0", size=12),
                    hovertemplate="<b>%{label}</b><br>%{value}%<extra></extra>",
                ))
                fig_pie.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", height=280,
                    showlegend=False, margin=dict(l=0,r=0,t=16,b=0),
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_sector:
                st.markdown("#### Sector Breakdown")
                sector_alloc = {}
                for p in portfolio:
                    sector_alloc[p["sector"]] = sector_alloc.get(p["sector"],0) + p["alloc"]
                fig_sec = go.Figure(go.Bar(
                    x=list(sector_alloc.values()),
                    y=list(sector_alloc.keys()),
                    orientation="h",
                    marker_color="#7c4fff",
                    text=[f"{v}%" for v in sector_alloc.values()],
                    textposition="outside",
                    textfont=dict(color="#8b92a5"),
                    hovertemplate="<b>%{y}</b>: %{x}%<extra></extra>",
                ))
                fig_sec.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                    height=280, margin=dict(l=0,r=0,t=16,b=80),
                    xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5"), ticksuffix="%"),
                    yaxis=dict(tickfont=dict(color="#8b92a5")),
                )
                st.plotly_chart(fig_sec, use_container_width=True)

            # ── Portfolio Performance (Normalized)
            st.markdown("#### Portfolio Performance vs ตลาด")
            perf_period = st.radio("ช่วงเวลา",["1mo","3mo","1y","5y"],index=2,horizontal=True,key="port_p")
            fig_perf = go.Figure()
            port_returns = None
            clr_list = ["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa"]

            for idx, p in enumerate(portfolio):
                h = fetch_history(p["ticker"], perf_period)
                if not h.empty:
                    norm = (h["Close"]/h["Close"].iloc[0])*100
                    weighted = norm * (p["alloc"]/100)
                    if port_returns is None:
                        port_returns = weighted
                    else:
                        port_returns = port_returns + weighted
                    fig_perf.add_trace(go.Scatter(
                        x=h.index, y=norm, name=p["ticker"],
                        line=dict(color=clr_list[idx%len(clr_list)], width=1.5, dash="dot"),
                        opacity=0.6,
                        hovertemplate=f"<b>{p['ticker']}</b>: %{{y:.1f}}%<extra></extra>",
                    ))

            if port_returns is not None:
                fig_perf.add_trace(go.Scatter(
                    x=port_returns.index, y=port_returns,
                    name="📦 Portfolio (Weighted)",
                    line=dict(color="#ffffff", width=2.5),
                    hovertemplate="<b>Portfolio</b>: %{y:.1f}%<extra></extra>",
                ))

            fig_perf.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e", height=320,
                xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5",size=11)),
                yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5",size=11), ticksuffix="%"),
                legend=dict(font=dict(color="#8b92a5",size=11), bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0,r=0,t=16,b=0), hovermode="x unified",
            )
            st.plotly_chart(fig_perf, use_container_width=True)

            # ── Portfolio Summary Table
            st.markdown("#### สรุปพอร์ต")
            avg_beta = sum([(p.get("beta") or 1)*p["alloc"]/100 for p in portfolio])
            port_change = sum([p["change"]*p["alloc"]/100 for p in portfolio])

            pm1, pm2, pm3, pm4 = st.columns(4)
            pm1.metric("จำนวนหุ้น", f"{len(portfolio)} ตัว")
            pm2.metric("Portfolio Beta", f"{avg_beta:.2f}")
            pm3.metric("วันนี้ (Weighted %)", f"{port_change:+.2f}%")
            pm4.metric("รวมสัดส่วน", f"{total_alloc}%")

            # Table
            table_rows = []
            for p in portfolio:
                table_rows.append({
                    "Ticker": p["ticker"], "ชื่อ": p["name"][:20],
                    "สัดส่วน": f"{p['alloc']}%",
                    "ราคา": f"${p['price']:,.2f}",
                    "วันนี้": f"{'▲' if p['change']>=0 else '▼'}{abs(p['change']):.2f}%",
                    "Sector": p["sector"],
                    "P/E": f"{p['pe']:.1f}x" if p.get("pe") else "—",
                    "Beta": f"{p['beta']:.2f}" if p.get("beta") else "—",
                })
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

            if st.button("🗑️ ล้างพอร์ตทั้งหมด"):
                st.session_state.portfolio = []
                st.rerun()

# ── Also show Portfolio tab when no results yet
if not results:
    with st.expander("💼 Portfolio Simulator", expanded=False):
        st.info("วิเคราะห์หุ้นก่อน แล้วกลับมาที่ Tab Portfolio เพื่อสร้างพอร์ตครับ")
