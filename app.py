import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import json
import re
from datetime import datetime

st.set_page_config(page_title="D.E.E.P.V AI Analyst", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    [data-testid="metric-container"] {
        background: #1c1f26; border: 1px solid #2d313d;
        border-radius: 12px; padding: 16px 20px;
    }
    [data-testid="metric-container"] label {
        font-size: 0.75rem !important; color: #8b92a5 !important;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.4rem !important; font-weight: 700 !important; color: #e8eaf0 !important;
    }
    [data-testid="stSidebar"] { background: #13161e; border-right: 1px solid #2d313d; }
    .stButton > button {
        background: linear-gradient(135deg, #4f7cff, #7c4fff);
        color: white; border: none; border-radius: 8px;
        padding: 10px 20px; font-weight: 600; width: 100%;
    }
    hr { border-color: #2d313d !important; }
    .deepv-card {
        background: #1c1f26; border: 1px solid #2d313d;
        border-radius: 12px; padding: 20px; margin-bottom: 12px;
    }
    .info-section {
        background: #13161e; border: 1px solid #2d313d;
        border-radius: 10px; padding: 16px; margin-bottom: 12px;
    }
    .info-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 0; border-bottom: 1px solid #2d313d22;
    }
    .info-label { font-size: 0.8rem; color: #8b92a5; }
    .info-value { font-size: 0.9rem; font-weight: 600; color: #e8eaf0; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────
def fmt_large(v):
    if not v: return "—"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def calc_pct_change(info: dict) -> float:
    """คำนวณ % เปลี่ยนแปลงจาก currentPrice / previousClose โดยตรง — แม่นกว่าใช้ field สำเร็จรูป"""
    current   = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    prev      = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
    if prev and prev > 0:
        return ((current - prev) / prev) * 100
    return 0.0

def score_color(s): return "#34d399" if s>=70 else "#fbbf24" if s>=40 else "#f87171"
def level_label(l): return {"green":"🟢 เสี่ยงต่ำ","yellow":"🟡 เสี่ยงกลาง","red":"🔴 เสี่ยงสูง"}.get(l,"—")
def pct(v):  return f"{v*100:.1f}%" if v else "—"
def usd(v):  return f"${v:,.2f}" if v else "—"
def xfmt(v): return f"{v:.1f}x" if v else "—"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        if not info or (not info.get("currentPrice") and not info.get("regularMarketPrice")):
            return None
        return {
            # ── Header
            "name":           info.get("longName") or info.get("shortName") or ticker,
            "ticker":         ticker,
            "change":         calc_pct_change(info),   # ← ใช้ฟังก์ชันใหม่
            "sector":         info.get("sector","—"),
            "industry":       info.get("industry","—"),
            "website":        info.get("website",""),
            "description":    info.get("longBusinessSummary",""),
            # ── Pricing
            "price":          info.get("currentPrice") or info.get("regularMarketPrice",0),
            "prev_close":     info.get("previousClose"),
            "open":           info.get("open"),
            "day_high":       info.get("dayHigh"),
            "day_low":        info.get("dayLow"),
            "52w_high":       info.get("fiftyTwoWeekHigh"),
            "52w_low":        info.get("fiftyTwoWeekLow"),
            "target_price":   info.get("targetMeanPrice"),
            # ── Valuation
            "cap":            info.get("marketCap",0),
            "pe":             info.get("trailingPE"),
            "fwd_pe":         info.get("forwardPE"),
            "peg":            info.get("pegRatio"),
            "pb":             info.get("priceToBook"),
            "ps":             info.get("priceToSalesTrailing12Months"),
            "ev_ebitda":      info.get("enterpriseToEbitda"),
            "eps":            info.get("trailingEps"),
            "fwd_eps":        info.get("forwardEps"),
            # ── Financials
            "revenue":        info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth":info.get("earningsGrowth"),
            "gross_margin":   info.get("grossMargins"),
            "op_margin":      info.get("operatingMargins"),
            "net_margin":     info.get("profitMargins"),
            "roe":            info.get("returnOnEquity"),
            "roa":            info.get("returnOnAssets"),
            "fcf":            info.get("freeCashflow"),
            "ebitda":         info.get("ebitda"),
            # ── Balance Sheet
            "total_cash":     info.get("totalCash"),
            "total_debt":     info.get("totalDebt"),
            "debt_equity":    info.get("debtToEquity"),
            "current_ratio":  info.get("currentRatio"),
            # ── Dividend & Risk
            "dividend_yield": info.get("dividendYield"),
            "beta":           info.get("beta"),
            "short_ratio":    info.get("shortRatio"),
            # ── Analyst
            "analyst_count":  info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey","").upper(),
        }
    except Exception as e:
        st.error(f"yfinance error: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(ticker, period):
    return yf.Ticker(ticker).history(period=period)


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

    prompt = f"""คุณเป็น AI Analyst วิเคราะห์หุ้น {ticker} ({d['name']}) ด้วย D.E.E.P.V

ข้อมูลทางการเงิน:
ราคา ${d['price']} | เปลี่ยน {d['change']:.2f}% | Market Cap {fmt_large(d['cap'])}
Trailing P/E: {d.get('pe','N/A')} | Forward P/E: {d.get('fwd_pe','N/A')} | PEG: {d.get('peg','N/A')}
Revenue: {fmt_large(d.get('revenue'))} | Revenue Growth: {pct(d.get('revenue_growth'))}
Gross Margin: {pct(d.get('gross_margin'))} | Op Margin: {pct(d.get('op_margin'))} | Net Margin: {pct(d.get('net_margin'))}
ROE: {pct(d.get('roe'))} | ROA: {pct(d.get('roa'))} | FCF: {fmt_large(d.get('fcf'))}
Debt/Equity: {d.get('debt_equity','N/A')} | Beta: {d.get('beta','N/A')}
Sector: {d['sector']} / {d['industry']}

ตอบเป็น JSON เท่านั้น ไม่มี backtick ไม่มีข้อความอื่น:
{{
  "dimensions": {{
    "D": {{"name":"Durability","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<4-5 ประโยคไทย>"}},
    "E1": {{"name":"Earnings Quality","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<4-5 ประโยคไทย>"}},
    "E2": {{"name":"Execution","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<4-5 ประโยคไทย>"}},
    "P": {{"name":"Pricing Power","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<4-5 ประโยคไทย>"}},
    "V": {{"name":"Valuation","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<4-5 ประโยคไทย>"}}
  }},
  "overall_score":<0-100>,
  "overall_level":"<green|yellow|red>",
  "recommendation":"<BUY|HOLD|AVOID>",
  "summary":"<สรุปภาพรวม 4-5 ประโยคไทย>",
  "risks":"<ความเสี่ยงหลัก 2-3 ข้อไทย>",
  "catalysts":"<ปัจจัยบวกหลัก 2-3 ข้อไทย>"
}}"""
    try:
        resp = genai.GenerativeModel(mn).generate_content(prompt)
        text = re.sub(r'^```json\s*|\s*```$','', resp.text.strip())
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error":"parse_failed","raw": resp.text}
    except Exception as e:
        return {"error": str(e)}


def generate_html_report(ticker, d, ai) -> str:
    dims    = ai.get("dimensions",{})
    overall = ai.get("overall_score",0)
    rec     = ai.get("recommendation","—")
    rc  = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
    oc  = score_color(overall)
    now = datetime.now().strftime("%d %b %Y %H:%M")
    rows = "".join([f"""
    <div style="margin-bottom:14px;padding:16px;background:#1c1f26;border-radius:10px;border-left:3px solid {score_color(dim.get('score',0))}">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="font-size:1.3rem;font-weight:800;color:{score_color(dim.get('score',0))}">{k}</span>
        <span style="font-size:0.9rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</span>
        <span style="margin-left:auto;color:{score_color(dim.get('score',0))};font-weight:700">{dim.get('score',0)}/100</span>
        <span style="background:{score_color(dim.get('score',0))}22;color:{score_color(dim.get('score',0))};border:1px solid {score_color(dim.get('score',0))}44;border-radius:5px;padding:1px 8px;font-size:0.72rem">{level_label(dim.get('level',''))}</span>
      </div>
      <div style="background:#2d313d;border-radius:999px;height:4px;margin-bottom:8px;overflow:hidden">
        <div style="background:{score_color(dim.get('score',0))};width:{dim.get('score',0)}%;height:100%;border-radius:999px"></div>
      </div>
      <p style="color:#8b92a5;margin:0 0 5px;font-size:0.78rem">{dim.get('summary','')}</p>
      <p style="color:#c5c9d6;margin:0;font-size:0.85rem;line-height:1.6">{dim.get('analysis','')}</p>
    </div>""" for k,dim in dims.items()])

    return f"""<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8">
<title>DEEPV: {ticker}</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:#0e1117;color:#e8eaf0;margin:0;padding:40px;max-width:860px;margin:0 auto}}
.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}}
.c{{background:#1c1f26;border-radius:8px;padding:12px}}
.cl{{font-size:0.68rem;color:#8b92a5;text-transform:uppercase}}
.cv{{font-size:1.1rem;font-weight:700}}</style></head><body>
<div style="border-bottom:1px solid #2d313d;padding-bottom:18px;margin-bottom:20px">
  <div style="font-size:0.72rem;color:#8b92a5">DEEPV AI Analyst · {now}</div>
  <h1 style="margin:6px 0 0;font-size:1.6rem">{d.get('name',ticker)} <span style="color:#8b92a5;font-size:0.9rem">({ticker})</span></h1>
  <div style="margin-top:8px;display:flex;align-items:center;gap:20px">
    <span style="font-size:1.3rem;font-weight:700">${d.get('price',0):,.2f}</span>
    <div style="text-align:center"><div style="font-size:1.8rem;font-weight:800;color:{oc}">{overall}</div><div style="font-size:0.62rem;color:#8b92a5">DEEPV SCORE</div></div>
    <div style="text-align:center"><div style="font-size:1.2rem;font-weight:800;color:{rc}">{rec}</div><div style="font-size:0.62rem;color:#8b92a5">SIGNAL</div></div>
  </div>
</div>
<div class="g">
  <div class="c"><div class="cl">Market Cap</div><div class="cv">{fmt_large(d.get('cap',0))}</div></div>
  <div class="c"><div class="cl">P/E (Trail)</div><div class="cv">{xfmt(d.get('pe'))}</div></div>
  <div class="c"><div class="cl">Forward P/E</div><div class="cv">{xfmt(d.get('fwd_pe'))}</div></div>
  <div class="c"><div class="cl">Revenue</div><div class="cv">{fmt_large(d.get('revenue'))}</div></div>
  <div class="c"><div class="cl">Gross Margin</div><div class="cv">{pct(d.get('gross_margin'))}</div></div>
  <div class="c"><div class="cl">ROE</div><div class="cv">{pct(d.get('roe'))}</div></div>
</div>
{rows}
<div style="background:#1c1f26;border-radius:10px;padding:16px;border-left:3px solid {rc};margin-bottom:12px">
  <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">สรุปภาพรวม</div>
  <p style="margin:0;line-height:1.7;color:#c5c9d6">{ai.get('summary','')}</p>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid #34d399">
    <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">ปัจจัยบวก</div>
    <p style="margin:0;color:#c5c9d6;font-size:0.85rem;line-height:1.6">{ai.get('catalysts','')}</p>
  </div>
  <div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid #f87171">
    <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">ความเสี่ยง</div>
    <p style="margin:0;color:#c5c9d6;font-size:0.85rem;line-height:1.6">{ai.get('risks','')}</p>
  </div>
</div>
</body></html>"""


# ─── Session State ───────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = {}


# ─── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 D.E.E.P.V Analyst")
    api_key = st.text_input("Google Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")
    st.markdown("**Ticker Symbols**")
    st.caption("รองรับหุ้นสหรัฐ (NVDA) และหุ้นไทย (PTT.BK)")
    t1 = st.text_input("หุ้นตัวที่ 1", value="NVDA").upper().strip()
    t2 = st.text_input("หุ้นตัวที่ 2 (เปรียบเทียบ)", value="").upper().strip()
    t3 = st.text_input("หุ้นตัวที่ 3 (เปรียบเทียบ)", value="").upper().strip()
    btn = st.button("🚀 วิเคราะห์หุ้น")
    st.divider()
    st.caption("D · Durability\nE · Earnings Quality\nE · Execution\nP · Pricing Power\nV · Valuation")


# ─── Run analysis ────────────────────────────────────────────────────────────────
tickers = [t for t in [t1,t2,t3] if t]
if btn and tickers:
    st.session_state.results = {}
    for ticker in tickers:
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


# ─── Display ────────────────────────────────────────────────────────────────────
results = st.session_state.results

if not results:
    st.markdown("""
    <div style="text-align:center;padding:80px 0;color:#8b92a5">
        <div style="font-size:3rem;margin-bottom:16px">📊</div>
        <h3 style="color:#e8eaf0">D.E.E.P.V AI Stock Analyst</h3>
        <p>ใส่ Ticker และกด "วิเคราะห์หุ้น" เพื่อเริ่มต้น</p>
        <p style="font-size:0.8rem;margin-top:24px;color:#444">รองรับ NVDA, AAPL, PTT.BK, ADVANC.BK และอื่นๆ</p>
    </div>""", unsafe_allow_html=True)

else:
    tickers_ready = list(results.keys())
    tab_labels = [f"📈 {t}" for t in tickers_ready]
    if len(tickers_ready) > 1: tab_labels.append("⚖️ เปรียบเทียบ")
    tabs = st.tabs(tab_labels)

    for i, ticker in enumerate(tickers_ready):
        with tabs[i]:
            d  = results[ticker]["data"]
            ai = results[ticker]["ai"]

            cc    = "#34d399" if d["change"] >= 0 else "#f87171"
            arrow = "▲" if d["change"] >= 0 else "▼"

            st.markdown(f"""
            <div style="margin-bottom:4px">
              <span style="font-size:1.6rem;font-weight:700;color:#e8eaf0">{d['name']}</span>
              <span style="color:#8b92a5;font-size:0.9rem;margin-left:8px">{ticker}</span>
              <span style="color:{cc};font-size:0.9rem;font-weight:600;margin-left:12px">{arrow} {abs(d['change']):.2f}%</span>
            </div>
            <div style="font-size:0.8rem;color:#8b92a5;margin-bottom:20px">{d['sector']} · {d['industry']}</div>
            """, unsafe_allow_html=True)

            # ── Row 1: Pricing
            st.markdown('<div style="font-size:0.7rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">💰 ราคา</div>', unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("ราคาล่าสุด",   f"${d['price']:,.2f}")
            c2.metric("Prev Close",    usd(d.get("prev_close")))
            c3.metric("Day High",      usd(d.get("day_high")))
            c4.metric("Day Low",       usd(d.get("day_low")))

            c5,c6,c7,c8 = st.columns(4)
            c5.metric("52W High",      usd(d.get("52w_high")))
            c6.metric("52W Low",       usd(d.get("52w_low")))
            c7.metric("Target Price",  usd(d.get("target_price")))
            c8.metric("Market Cap",    fmt_large(d["cap"]))

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Row 2: Valuation
            st.markdown('<div style="font-size:0.7rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">📐 Valuation</div>', unsafe_allow_html=True)
            v1,v2,v3,v4 = st.columns(4)
            v1.metric("P/E (Trailing)", xfmt(d.get("pe")))
            v2.metric("P/E (Forward)",  xfmt(d.get("fwd_pe")))
            v3.metric("PEG Ratio",      xfmt(d.get("peg")))
            v4.metric("P/B Ratio",      xfmt(d.get("pb")))

            v5,v6,v7,v8 = st.columns(4)
            v5.metric("P/S Ratio",      xfmt(d.get("ps")))
            v6.metric("EV/EBITDA",      xfmt(d.get("ev_ebitda")))
            v7.metric("EPS (Trail)",    usd(d.get("eps")))
            v8.metric("EPS (Fwd)",      usd(d.get("fwd_eps")))

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Row 3: Financials
            st.markdown('<div style="font-size:0.7rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">📊 Financials</div>', unsafe_allow_html=True)
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

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Row 4: Balance Sheet & Risk
            st.markdown('<div style="font-size:0.7rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">🏦 Balance Sheet & Risk</div>', unsafe_allow_html=True)
            b1,b2,b3,b4 = st.columns(4)
            b1.metric("Total Cash",     fmt_large(d.get("total_cash")))
            b2.metric("Total Debt",     fmt_large(d.get("total_debt")))
            b3.metric("Debt/Equity",    f"{d['debt_equity']:.1f}" if d.get("debt_equity") else "—")
            b4.metric("Current Ratio",  f"{d['current_ratio']:.2f}" if d.get("current_ratio") else "—")

            b5,b6,b7,b8 = st.columns(4)
            b5.metric("Beta",           f"{d['beta']:.2f}" if d.get("beta") else "—")
            b6.metric("Dividend Yield", pct(d.get("dividend_yield")))
            b7.metric("Short Ratio",    f"{d['short_ratio']:.1f}x" if d.get("short_ratio") else "—")
            b8.metric("Analyst Rating", d.get("recommendation","—"))

            st.divider()

            # ── Chart
            t_period = st.radio("ช่วงเวลา",["1d","5d","1mo","3mo","1y","5y","max"],
                                index=4, horizontal=True, key=f"p_{ticker}")
            hist = fetch_history(ticker, t_period)
            if not hist.empty:
                up   = hist["Close"].iloc[-1] >= hist["Close"].iloc[0]
                clr  = "#34d399" if up else "#f87171"
                fill = "rgba(52,211,153,0.08)" if up else "rgba(248,113,113,0.08)"
                fig  = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist["Close"], mode="lines",
                    line=dict(color=clr, width=1.8), fill="tozeroy", fillcolor=fill,
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>",
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                    margin=dict(l=0,r=0,t=16,b=0), height=300,
                    xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5",size=11)),
                    yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5",size=11), tickprefix="$"),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

            # ── DEEPV Section
            if ai and "dimensions" in ai:
                st.divider()
                overall = ai.get("overall_score",0)
                rec     = ai.get("recommendation","—")
                rc      = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
                oc      = score_color(overall)

                st.markdown(f"""
                <div style="background:#1c1f26;border-radius:12px;padding:20px;margin-bottom:20px;
                            display:flex;align-items:center;gap:24px;border:1px solid #2d313d">
                  <div style="text-align:center;min-width:70px">
                    <div style="font-size:2.4rem;font-weight:800;color:{oc}">{overall}</div>
                    <div style="font-size:0.65rem;color:#8b92a5;text-transform:uppercase">DEEPV Score</div>
                  </div>
                  <div style="flex:1">
                    <div style="background:#2d313d;border-radius:999px;height:8px;overflow:hidden">
                      <div style="background:{oc};width:{overall}%;height:100%;border-radius:999px"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:4px">
                      <span style="font-size:0.7rem;color:#f87171">เสี่ยงสูง</span>
                      <span style="font-size:0.7rem;color:#fbbf24">เสี่ยงกลาง</span>
                      <span style="font-size:0.7rem;color:#34d399">เสี่ยงต่ำ</span>
                    </div>
                  </div>
                  <div style="text-align:center;min-width:80px">
                    <div style="font-size:1.4rem;font-weight:800;color:{rc}">{rec}</div>
                    <div style="font-size:0.65rem;color:#8b92a5;text-transform:uppercase">Signal</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                for key, dim in ai.get("dimensions",{}).items():
                    sc  = dim.get("score",0)
                    lc  = score_color(sc)
                    lbl = level_label(dim.get("level","yellow"))
                    st.markdown(f"""
                    <div class="deepv-card" style="border-left:3px solid {lc}">
                      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
                        <span style="font-size:1.8rem;font-weight:800;color:{lc};min-width:40px">{key}</span>
                        <div>
                          <div style="font-size:1rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</div>
                          <div style="font-size:0.8rem;color:#8b92a5">{dim.get('summary','')}</div>
                        </div>
                        <div style="margin-left:auto;text-align:right">
                          <div style="font-size:1.5rem;font-weight:700;color:{lc}">{sc}<span style="font-size:0.8rem;color:#8b92a5">/100</span></div>
                          <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;border-radius:6px;padding:2px 8px;font-size:0.75rem">{lbl}</span>
                        </div>
                      </div>
                      <div style="height:4px;background:#2d313d;border-radius:999px;margin-bottom:12px;overflow:hidden">
                        <div style="background:{lc};width:{sc}%;height:100%;border-radius:999px"></div>
                      </div>
                      <p style="color:#c5c9d6;margin:0;font-size:0.9rem;line-height:1.7">{dim.get('analysis','')}</p>
                    </div>""", unsafe_allow_html=True)

                # Summary + Catalysts + Risks
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(f"""
                    <div style="background:#1c1f26;border-radius:12px;padding:16px;border-left:3px solid #34d399;height:100%">
                      <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">✅ ปัจจัยบวก</div>
                      <p style="color:#c5c9d6;margin:0;line-height:1.7;font-size:0.9rem">{ai.get('catalysts','—')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_r:
                    st.markdown(f"""
                    <div style="background:#1c1f26;border-radius:12px;padding:16px;border-left:3px solid #f87171;height:100%">
                      <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">⚠️ ความเสี่ยง</div>
                      <p style="color:#c5c9d6;margin:0;line-height:1.7;font-size:0.9rem">{ai.get('risks','—')}</p>
                    </div>""", unsafe_allow_html=True)

                st.markdown(f"""
                <div style="background:#1c1f26;border-radius:12px;padding:16px;border-left:3px solid {rc};margin-top:12px">
                  <div style="font-size:0.68rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">🧠 สรุปภาพรวม</div>
                  <p style="color:#c5c9d6;margin:0;line-height:1.7">{ai.get('summary','')}</p>
                </div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                html_report = generate_html_report(ticker, d, ai)
                st.download_button(
                    "📄 ดาวน์โหลด DEEPV Report (HTML)",
                    data=html_report.encode("utf-8"),
                    file_name=f"DEEPV_{ticker}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html", key=f"dl_{ticker}",
                )
                st.balloons()

            elif ai and "raw" in ai:
                st.markdown(f'<div style="background:#1c1f26;border-radius:12px;padding:20px;color:#c5c9d6">{ai["raw"]}</div>', unsafe_allow_html=True)
            elif ai and "error" in ai:
                st.error(f"❌ {ai['error']}")
            elif not api_key:
                st.info("💡 ใส่ Google Gemini API Key ใน Sidebar เพื่อดูผลวิเคราะห์ DEEPV")

    # ── Compare Tab
    if len(tickers_ready) > 1:
        with tabs[-1]:
            st.markdown("### ⚖️ เปรียบเทียบ DEEPV Score")
            has_ai  = {t:r["ai"] for t,r in results.items() if r["ai"] and "dimensions" in r["ai"]}
            palette = ["#4f7cff","#34d399","#fbbf24"]

            if has_ai:
                dim_keys  = ["D","E1","E2","P","V"]
                dim_names = ["Durability","Earnings","Execution","Pricing","Valuation"]
                fig = go.Figure()
                for idx,(t,ai) in enumerate(has_ai.items()):
                    scores = [ai["dimensions"].get(k,{}).get("score",0) for k in dim_keys]
                    fig.add_trace(go.Bar(name=t, x=dim_names, y=scores,
                                        marker_color=palette[idx%len(palette)]))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                    barmode="group", height=360,
                    yaxis=dict(range=[0,100], gridcolor="#1c2030", tickfont=dict(color="#8b92a5")),
                    xaxis=dict(tickfont=dict(color="#8b92a5")),
                    legend=dict(font=dict(color="#8b92a5"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0,r=0,t=16,b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### คะแนนแยกรายด้าน")
                table_data = {}
                for t,ai in has_ai.items():
                    row = {}
                    for k in dim_keys:
                        sc = ai["dimensions"].get(k,{}).get("score",0)
                        lv = ai["dimensions"].get(k,{}).get("level","yellow")
                        row[k] = f'{"🟢" if lv=="green" else "🟡" if lv=="yellow" else "🔴"} {sc}'
                    row["Overall"] = ai.get("overall_score",0)
                    row["Signal"]  = ai.get("recommendation","—")
                    table_data[t]  = row
                st.dataframe(pd.DataFrame(table_data).T, use_container_width=True)
            else:
                st.info("วิเคราะห์หุ้นอย่างน้อย 2 ตัวพร้อม API Key เพื่อดูกราฟเปรียบเทียบ")

            st.markdown("#### เปรียบเทียบราคา (Normalized %)")
            period_cmp = st.radio("ช่วงเวลา",["1mo","3mo","1y","5y"], index=2, horizontal=True, key="cmp")
            fig2 = go.Figure()
            for idx,t in enumerate(tickers_ready):
                hist = fetch_history(t, period_cmp)
                if not hist.empty:
                    norm = (hist["Close"]/hist["Close"].iloc[0])*100
                    fig2.add_trace(go.Scatter(x=hist.index, y=norm, name=t,
                        line=dict(color=palette[idx%len(palette)],width=2),
                        hovertemplate=f"<b>{t}</b>: %{{y:.1f}}%<extra></extra>"))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e", height=300,
                xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5",size=11)),
                yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5",size=11), ticksuffix="%"),
                legend=dict(font=dict(color="#8b92a5"), bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0,r=0,t=16,b=0), hovermode="x unified",
            )
            st.plotly_chart(fig2, use_container_width=True)
