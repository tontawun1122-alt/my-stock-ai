import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import json, re
from datetime import datetime

st.set_page_config(page_title="D.E.E.P.V AI Analyst", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

# ─── Session State ────────────────────────────────────────────────────────────────
for k, v in [("results", {}), ("portfolio", []), ("lang", "TH"), ("theme", "dark")]:
    if k not in st.session_state:
        st.session_state[k] = v

LANG = st.session_state.lang
DARK = st.session_state.theme == "dark"
TH   = LANG == "TH"

# ─── Theme Colors ─────────────────────────────────────────────────────────────────
if DARK:
    bg="#0e1117"; bg2="#1c1f26"; bg3="#13161e"; border="#2d313d"
    text="#e8eaf0"; muted="#8b92a5"; plot_bg="#13161e"; grid="#1c2030"
else:
    bg="#f0f2f6"; bg2="#ffffff"; bg3="#e8eaf0"; border="#d1d5db"
    text="#111827"; muted="#6b7280"; plot_bg="#f8fafc"; grid="#e5e7eb"

st.markdown(f"""<style>
.stApp{{background:{bg}}}
[data-testid="metric-container"]{{background:{bg2};border:1px solid {border};border-radius:12px;padding:14px 18px}}
[data-testid="metric-container"] label{{font-size:.72rem!important;color:{muted}!important;text-transform:uppercase;letter-spacing:.05em}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{font-size:1.2rem!important;font-weight:700!important;color:{text}!important}}
[data-testid="stSidebar"]{{background:{bg3};border-right:1px solid {border}}}
.stButton>button{{background:linear-gradient(135deg,#4f7cff,#7c4fff);color:white;border:none;border-radius:8px;padding:10px 20px;font-weight:600;width:100%}}
hr{{border-color:{border}!important}}
.dcard{{background:{bg2};border:1px solid {border};border-radius:12px;padding:20px;margin-bottom:12px}}
.slbl{{font-size:.68rem;color:{muted};text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;margin-top:6px}}
p,span,div,h1,h2,h3{{color:{text}}}
#MainMenu,footer{{visibility:hidden}}
.block-container{{padding-top:1.5rem;padding-bottom:2rem}}
</style>""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────────
def fmt(v):
    if not v or v == 0: return "—"
    s = "-" if v < 0 else ""; v = abs(v)
    if v >= 1e12: return f"{s}${v/1e12:.2f}T"
    if v >= 1e9:  return f"{s}${v/1e9:.2f}B"
    if v >= 1e6:  return f"{s}${v/1e6:.2f}M"
    return f"{s}${v:,.0f}"

def cpct(info):
    c = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    p = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
    return ((c - p) / p * 100) if p else 0.0

def sc(s):  return "#34d399" if s >= 70 else "#fbbf24" if s >= 40 else "#f87171"
def ll(lv): return {"green": ("🟢 เสี่ยงต่ำ","🟢 Low Risk"), "yellow": ("🟡 เสี่ยงกลาง","🟡 Med Risk"), "red": ("🔴 เสี่ยงสูง","🔴 High Risk")}.get(lv, ("—","—"))[0 if TH else 1]
def pct(v): return f"{v*100:.1f}%" if v else "—"
def usd(v): return f"${v:,.2f}" if v else "—"
def xf(v):  return f"{v:.1f}x" if v else "—"

def plot_base(h=300):
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=plot_bg,
                margin=dict(l=0,r=0,t=16,b=0), height=h, hovermode="x unified",
                xaxis=dict(showgrid=False, tickfont=dict(color=muted, size=11)),
                yaxis=dict(gridcolor=grid, tickfont=dict(color=muted, size=11)),
                legend=dict(font=dict(color=muted, size=11), bgcolor="rgba(0,0,0,0)"),
                font=dict(color=text))


@st.cache_data(ttl=300, show_spinner=False)
def get_stock(ticker):
    try:
        info = yf.Ticker(ticker).info
        if not info or (not info.get("currentPrice") and not info.get("regularMarketPrice")):
            return None
        return {
            "name":       info.get("longName") or info.get("shortName") or ticker,
            "ticker":     ticker,
            "change":     cpct(info),
            "sector":     info.get("sector", "—"),
            "industry":   info.get("industry", "—"),
            "website":    info.get("website", ""),
            "country":    info.get("country", "—"),
            "description":info.get("longBusinessSummary", ""),
            "employees":  info.get("fullTimeEmployees"),
            "price":      info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "prev_close": info.get("previousClose"),
            "day_high":   info.get("dayHigh"),
            "day_low":    info.get("dayLow"),
            "52w_high":   info.get("fiftyTwoWeekHigh"),
            "52w_low":    info.get("fiftyTwoWeekLow"),
            "target":     info.get("targetMeanPrice"),
            "cap":        info.get("marketCap", 0),
            "pe":         info.get("trailingPE"),
            "fwd_pe":     info.get("forwardPE"),
            "peg":        info.get("pegRatio"),
            "pb":         info.get("priceToBook"),
            "ps":         info.get("priceToSalesTrailing12Months"),
            "ev_eb":      info.get("enterpriseToEbitda"),
            "eps":        info.get("trailingEps"),
            "fwd_eps":    info.get("forwardEps"),
            "rev":        info.get("totalRevenue"),
            "rev_g":      info.get("revenueGrowth"),
            "earn_g":     info.get("earningsGrowth"),
            "gm":         info.get("grossMargins"),
            "om":         info.get("operatingMargins"),
            "nm":         info.get("profitMargins"),
            "roe":        info.get("returnOnEquity"),
            "roa":        info.get("returnOnAssets"),
            "fcf":        info.get("freeCashflow"),
            "ebitda":     info.get("ebitda"),
            "cash":       info.get("totalCash"),
            "debt":       info.get("totalDebt"),
            "de":         info.get("debtToEquity"),
            "cr":         info.get("currentRatio"),
            "div":        info.get("dividendYield"),
            "beta":       info.get("beta"),
            "short":      info.get("shortRatio"),
            "ar":         info.get("recommendationKey", "").upper(),
            "analysts":   info.get("numberOfAnalystOpinions"),
        }
    except Exception as e:
        st.error(f"Error: {e}"); return None


@st.cache_data(ttl=300, show_spinner=False)
def get_hist(ticker, period):
    return yf.Ticker(ticker).history(period=period)


@st.cache_data(ttl=3600, show_spinner=False)
def get_fin(ticker):
    try: return yf.Ticker(ticker).financials
    except: return None


def run_ai(api_key, ticker, d, lang):
    genai.configure(api_key=api_key)
    try:
        avail = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        pref  = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-pro"]
        mn    = next((m for m in pref if m in avail), avail[0] if avail else None)
        if not mn: return {"error": "No model found"}
    except Exception as e:
        return {"error": str(e)}

    is_thai = lang == "TH"
    lang_rule = (
        "⚠️ CRITICAL RULE: You MUST write ALL text fields (name, summary, analysis, risks, catalysts) "
        "ENTIRELY in Thai language (ภาษาไทย). Every sentence must be Thai. "
        "Numbers and company names can stay in English but all explanatory text = Thai only. This is non-negotiable."
    ) if is_thai else "Write all text fields in clear English."

    d_name  = "ความทนทาน" if is_thai else "Durability"
    e1_name = "คุณภาพกำไร" if is_thai else "Earnings Quality"
    e2_name = "การบริหาร"  if is_thai else "Execution"
    p_name  = "อำนาจตั้งราคา" if is_thai else "Pricing Power"
    v_name  = "ราคาเหมาะสม"  if is_thai else "Valuation"

    prompt = f"""{lang_rule}

Analyze {ticker} ({d['name']}) using D.E.E.P.V Framework. Return ONLY valid JSON. No backticks.

Financial Data:
Price: ${d['price']} | Change: {d['change']:.2f}% | Market Cap: {fmt(d['cap'])}
Trailing P/E: {d.get('pe','N/A')} | Forward P/E: {d.get('fwd_pe','N/A')} | PEG: {d.get('peg','N/A')} | P/B: {d.get('pb','N/A')}
Revenue: {fmt(d.get('rev'))} | Rev Growth: {pct(d.get('rev_g'))} | Earnings Growth: {pct(d.get('earn_g'))}
Gross Margin: {pct(d.get('gm'))} | Op Margin: {pct(d.get('om'))} | Net Margin: {pct(d.get('nm'))}
ROE: {pct(d.get('roe'))} | ROA: {pct(d.get('roa'))} | FCF: {fmt(d.get('fcf'))} | EBITDA: {fmt(d.get('ebitda'))}
Total Cash: {fmt(d.get('cash'))} | Total Debt: {fmt(d.get('debt'))} | D/E: {d.get('de','N/A')} | Beta: {d.get('beta','N/A')}
Sector: {d['sector']} / {d['industry']} | Analyst Rating: {d.get('ar','N/A')}

Return this exact JSON structure:
{{
  "dimensions": {{
    "D":  {{"name": "{d_name}",  "score": 75, "level": "green",  "summary": "1 sentence", "analysis": "4-5 sentences detailed"}},
    "E1": {{"name": "{e1_name}", "score": 75, "level": "green",  "summary": "1 sentence", "analysis": "4-5 sentences detailed"}},
    "E2": {{"name": "{e2_name}", "score": 75, "level": "yellow", "summary": "1 sentence", "analysis": "4-5 sentences detailed"}},
    "P":  {{"name": "{p_name}",  "score": 75, "level": "green",  "summary": "1 sentence", "analysis": "4-5 sentences detailed"}},
    "V":  {{"name": "{v_name}",  "score": 40, "level": "yellow", "summary": "1 sentence", "analysis": "4-5 sentences detailed"}}
  }},
  "overall_score": 72,
  "overall_level": "green",
  "recommendation": "HOLD",
  "summary": "3-4 sentences overall conclusion",
  "catalysts": "2-3 key positive catalysts",
  "risks": "2-3 key risks"
}}
Rules: score 70-100=green, 40-69=yellow, 0-39=red | recommendation must be BUY/HOLD/AVOID"""

    try:
        resp  = genai.GenerativeModel(mn).generate_content(prompt)
        clean = re.sub(r'^```json\s*|\s*```$', '', resp.text.strip())
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": resp.text}
    except Exception as e:
        return {"error": str(e)}


def build_html_report(ticker, d, ai):
    """Full beautiful HTML report"""
    dims    = ai.get("dimensions", {})
    overall = ai.get("overall_score", 0)
    rec     = ai.get("recommendation", "—")
    rc      = {"BUY": "#34d399", "HOLD": "#fbbf24", "AVOID": "#f87171"}.get(rec, "#8b92a5")
    oc      = sc(overall)
    now     = datetime.now().strftime("%d %b %Y %H:%M")

    dim_html = ""
    for key, dim in dims.items():
        lc = sc(dim.get("score", 0))
        dim_html += f"""
        <div style="margin-bottom:16px;padding:18px;background:#1c1f26;border-radius:10px;border-left:3px solid {lc}">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
            <span style="font-size:1.4rem;font-weight:800;color:{lc};min-width:38px">{key}</span>
            <div>
              <div style="font-size:.95rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</div>
              <div style="font-size:.78rem;color:#8b92a5">{dim.get('summary','')}</div>
            </div>
            <div style="margin-left:auto;text-align:right">
              <span style="font-size:1.4rem;font-weight:700;color:{lc}">{dim.get('score',0)}<span style="font-size:.75rem;color:#8b92a5">/100</span></span><br>
              <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;border-radius:5px;padding:1px 8px;font-size:.72rem">{ll(dim.get('level',''))}</span>
            </div>
          </div>
          <div style="height:5px;background:#2d313d;border-radius:999px;margin-bottom:12px;overflow:hidden">
            <div style="background:{lc};width:{dim.get('score',0)}%;height:100%;border-radius:999px"></div>
          </div>
          <p style="color:#c5c9d6;margin:0;font-size:.88rem;line-height:1.7">{dim.get('analysis','')}</p>
        </div>"""

    metrics_html = f"""
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px">
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Market Cap</div><div style="font-size:1.05rem;font-weight:700">{fmt(d.get('cap',0))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">P/E (Trailing)</div><div style="font-size:1.05rem;font-weight:700">{xf(d.get('pe'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">P/E (Forward)</div><div style="font-size:1.05rem;font-weight:700">{xf(d.get('fwd_pe'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Revenue</div><div style="font-size:1.05rem;font-weight:700">{fmt(d.get('rev'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Gross Margin</div><div style="font-size:1.05rem;font-weight:700">{pct(d.get('gm'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Net Margin</div><div style="font-size:1.05rem;font-weight:700">{pct(d.get('nm'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">ROE</div><div style="font-size:1.05rem;font-weight:700">{pct(d.get('roe'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Free Cash Flow</div><div style="font-size:1.05rem;font-weight:700">{fmt(d.get('fcf'))}</div></div>
      <div style="background:#1c1f26;border-radius:8px;padding:12px"><div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Beta</div><div style="font-size:1.05rem;font-weight:700">{f"{d['beta']:.2f}" if d.get("beta") else "—"}</div></div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DEEPV Report: {ticker}</title>
<style>
  body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#0e1117;color:#e8eaf0;margin:0;padding:32px;max-width:900px;margin:0 auto;line-height:1.6}}
  @media(max-width:600px){{body{{padding:16px}}}}
  @media print{{body{{background:white;color:black}}}}
</style>
</head>
<body>

<div style="border-bottom:1px solid #2d313d;padding-bottom:20px;margin-bottom:24px">
  <div style="font-size:.72rem;color:#8b92a5;margin-bottom:6px">D.E.E.P.V AI Analyst · {now}</div>
  <h1 style="margin:0 0 4px;font-size:1.7rem;font-weight:800">{d.get('name',ticker)}
    <span style="color:#8b92a5;font-size:.9rem;font-weight:400">({ticker})</span>
  </h1>
  <div style="font-size:.8rem;color:#8b92a5;margin-bottom:14px">{d.get('sector','—')} · {d.get('industry','—')} · {d.get('country','—')}</div>
  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:20px">
    <div>
      <div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">ราคาล่าสุด</div>
      <div style="font-size:1.6rem;font-weight:700">${d.get('price',0):,.2f}</div>
    </div>
    <div style="text-align:center;background:{oc}18;border:1px solid {oc}44;border-radius:10px;padding:10px 20px">
      <div style="font-size:2rem;font-weight:800;color:{oc}">{overall}</div>
      <div style="font-size:.62rem;color:#8b92a5;text-transform:uppercase">DEEPV Score</div>
    </div>
    <div style="text-align:center;background:{rc}18;border:1px solid {rc}44;border-radius:10px;padding:10px 24px">
      <div style="font-size:1.5rem;font-weight:800;color:{rc}">{rec}</div>
      <div style="font-size:.62rem;color:#8b92a5;text-transform:uppercase">Signal</div>
    </div>
    <div>
      <div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase">Target Price</div>
      <div style="font-size:1.1rem;font-weight:600">{usd(d.get('target'))}</div>
    </div>
  </div>
  <div style="background:#2d313d;border-radius:999px;height:6px;overflow:hidden;margin-top:16px">
    <div style="background:{oc};width:{overall}%;height:100%;border-radius:999px"></div>
  </div>
  <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:.65rem">
    <span style="color:#f87171">เสี่ยงสูง 0-39</span>
    <span style="color:#fbbf24">เสี่ยงกลาง 40-69</span>
    <span style="color:#34d399">เสี่ยงต่ำ 70-100</span>
  </div>
</div>

<div style="font-size:.68rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px">ข้อมูลทางการเงิน</div>
{metrics_html}

<div style="font-size:.68rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px">DEEPV Analysis</div>
{dim_html}

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
  <div style="background:#1c1f26;border-radius:10px;padding:16px;border-left:3px solid #34d399">
    <div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">✅ ปัจจัยบวก</div>
    <p style="margin:0;color:#c5c9d6;font-size:.88rem;line-height:1.7">{ai.get('catalysts','—')}</p>
  </div>
  <div style="background:#1c1f26;border-radius:10px;padding:16px;border-left:3px solid #f87171">
    <div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">⚠️ ความเสี่ยง</div>
    <p style="margin:0;color:#c5c9d6;font-size:.88rem;line-height:1.7">{ai.get('risks','—')}</p>
  </div>
</div>

<div style="background:#1c1f26;border-radius:10px;padding:16px;border-left:3px solid {rc}">
  <div style="font-size:.65rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">🧠 สรุปภาพรวม</div>
  <p style="margin:0;color:#c5c9d6;line-height:1.8">{ai.get('summary','')}</p>
</div>

<div style="margin-top:24px;padding-top:16px;border-top:1px solid #2d313d;font-size:.72rem;color:#8b92a5;text-align:center">
  Generated by D.E.E.P.V AI Analyst · {now} · ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน
</div>

</body>
</html>"""


# ─── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    cl, ct = st.columns(2)
    with cl:
        if st.button("🌐 TH/EN"):
            st.session_state.lang = "EN" if LANG == "TH" else "TH"
            # ── Clear results so user must re-analyze in new language
            st.session_state.results = {}
            st.rerun()
    with ct:
        if st.button("☀️ Light" if DARK else "🌙 Dark"):
            st.session_state.theme = "light" if DARK else "dark"
            st.rerun()

    if not DARK:
        st.caption("🌐 เปลี่ยนภาษา = วิเคราะห์ใหม่อัตโนมัติ" if TH else "🌐 Language change = re-analyze")
    else:
        st.caption("🌐 เปลี่ยนภาษาจะ clear ผลเดิมอัตโนมัติ" if TH else "🌐 Language change clears results")

    st.markdown(f"## 📊 D.E.E.P.V")
    st.caption("AI Stock Analyst" if not TH else "วิเคราะห์หุ้นด้วย AI")
    api_key = st.text_input("Google Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")
    st.markdown(f"**{'🔍 วิเคราะห์หุ้น' if TH else '🔍 Analyze Stocks'}**")
    st.caption("US: NVDA, AAPL  |  TH: PTT.BK, ADVANC.BK")
    t1 = st.text_input("Ticker 1", value="NVDA").upper().strip()
    t2 = st.text_input("Ticker 2", value="").upper().strip()
    t3 = st.text_input("Ticker 3", value="").upper().strip()
    btn = st.button("🚀 วิเคราะห์" if TH else "🚀 Analyze")
    st.divider()
    st.caption("D·Durability  E·Earnings Quality\nE·Execution  P·Pricing Power\nV·Valuation")


# ─── Run Analysis ─────────────────────────────────────────────────────────────────
tickers_in = [x for x in [t1, t2, t3] if x]
if btn and tickers_in:
    st.session_state.results = {}
    for tk in tickers_in:
        with st.spinner(f"{'กำลังโหลด' if TH else 'Loading'} {tk}..."):
            data = get_stock(tk)
        if not data:
            st.error(f"❌ {'ไม่พบข้อมูล' if TH else 'Not found'}: {tk}")
            continue
        ai = None
        if api_key:
            with st.spinner(f"🧠 AI {'วิเคราะห์' if TH else 'Analyzing'} {tk}..."):
                ai = run_ai(api_key, tk, data, LANG)
        st.session_state.results[tk] = {"data": data, "ai": ai}


results = st.session_state.results

# ══ LANDING ══════════════════════════════════════════════════════════════════════
if not results:
    st.markdown(f"""
    <div style="padding:48px 0 32px;text-align:center">
      <div style="font-size:.75rem;color:#4f7cff;text-transform:uppercase;letter-spacing:.15em;margin-bottom:12px">
        {'AI-Powered Fundamental Analysis' if not TH else 'วิเคราะห์หุ้นเชิงลึกด้วย AI'}
      </div>
      <h1 style="font-size:2.5rem;font-weight:800;color:{text};margin:0 0 12px">
        D.E.E.P.V <span style="background:linear-gradient(135deg,#4f7cff,#7c4fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Analyst</span>
      </h1>
      <p style="color:{muted};font-size:1rem;max-width:480px;margin:0 auto 40px;line-height:1.7">
        {'Analyze stocks across 5 dimensions with AI-powered DEEPV Score + BUY/HOLD/AVOID signals.' if not TH else
         'วิเคราะห์หุ้นเชิงลึกด้วย AI ครอบคลุม 5 มิติ พร้อมคะแนน DEEPV Score และ Signal ที่ชัดเจน'}
      </p>
    </div>""", unsafe_allow_html=True)

    cols = st.columns(4)
    for col, (icon, title, desc) in zip(cols, [
        ("📐","DEEPV Score",  {"TH":"คะแนน 0-100 พร้อมไฟจราจร","EN":"0-100 Score + Traffic Light"}),
        ("⚖️","Compare",     {"TH":"เปรียบเทียบหลายหุ้นพร้อมกัน","EN":"Compare multiple stocks"}),
        ("💼","Portfolio",   {"TH":"จำลอง Asset Allocation","EN":"Simulate Asset Allocation"}),
        ("📄","Report",      {"TH":"ดาวน์โหลดรายงาน HTML ครบถ้วน","EN":"Download full HTML Report"}),
    ]):
        col.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:12px;padding:20px;text-align:center;height:140px">
            <div style="font-size:1.8rem;margin-bottom:8px">{icon}</div>
            <div style="font-weight:600;color:{text};margin-bottom:4px">{title}</div>
            <div style="font-size:.78rem;color:{muted};line-height:1.5">{desc[LANG]}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:12px;padding:24px">
    <div style="font-size:.68rem;color:{muted};text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px">
      {'What is DEEPV?' if not TH else 'DEEPV Framework คืออะไร?'}
    </div>
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;text-align:center">
      <div><div style="font-size:1.4rem;font-weight:800;color:#4f7cff">D</div><div style="font-size:.8rem;font-weight:600;color:{text}">Durability</div><div style="font-size:.72rem;color:{muted}">{"ความทนทาน" if TH else "Business Moat"}</div></div>
      <div><div style="font-size:1.4rem;font-weight:800;color:#7c4fff">E</div><div style="font-size:.8rem;font-weight:600;color:{text}">Earnings</div><div style="font-size:.72rem;color:{muted}">{"คุณภาพกำไร" if TH else "Profit Quality"}</div></div>
      <div><div style="font-size:1.4rem;font-weight:800;color:#a78bfa">E</div><div style="font-size:.8rem;font-weight:600;color:{text}">Execution</div><div style="font-size:.72rem;color:{muted}">{"การบริหาร" if TH else "Management"}</div></div>
      <div><div style="font-size:1.4rem;font-weight:800;color:#34d399">P</div><div style="font-size:.8rem;font-weight:600;color:{text}">Pricing</div><div style="font-size:.72rem;color:{muted}">{"อำนาจตั้งราคา" if TH else "Pricing Power"}</div></div>
      <div><div style="font-size:1.4rem;font-weight:800;color:#fbbf24">V</div><div style="font-size:.8rem;font-weight:600;color:{text}">Valuation</div><div style="font-size:.72rem;color:{muted}">{"ราคาเหมาะสม" if TH else "Fair Value"}</div></div>
    </div></div>""", unsafe_allow_html=True)
    st.info("👈 " + ("ใส่ Ticker ใน Sidebar แล้วกด วิเคราะห์หุ้น" if TH else "Enter Ticker in Sidebar then click Analyze"))

# ══ RESULTS ══════════════════════════════════════════════════════════════════════
else:
    tr = list(results.keys())
    tlabels = [f"📈 {x}" for x in tr]
    if len(tr) > 1: tlabels.append("⚖️ เปรียบเทียบ" if TH else "⚖️ Compare")
    tlabels.append("💼 Portfolio")
    tabs = st.tabs(tlabels)

    # ── Per-ticker tabs ──────────────────────────────────────────────────────────
    for i, ticker in enumerate(tr):
        with tabs[i]:
            d  = results[ticker]["data"]
            ai = results[ticker]["ai"]
            cc = "#34d399" if d["change"] >= 0 else "#f87171"
            ar = "▲" if d["change"] >= 0 else "▼"

            st.markdown(f"""<div style="margin-bottom:4px">
              <span style="font-size:1.5rem;font-weight:700;color:{text}">{d['name']}</span>
              <span style="color:{muted};font-size:.85rem;margin-left:8px">{ticker}</span>
              <span style="color:{cc};font-size:.9rem;font-weight:600;margin-left:10px">{ar} {abs(d['change']):.2f}%</span>
            </div>
            <div style="font-size:.78rem;color:{muted};margin-bottom:16px">{d['sector']} · {d['industry']} · {d.get('country','')}</div>""",
            unsafe_allow_html=True)

            if d.get("description"):
                with st.expander("📋 " + ("เกี่ยวกับบริษัท" if TH else "About Company"), expanded=False):
                    st.markdown(f'<p style="color:{muted};font-size:.88rem;line-height:1.7">{d["description"][:800]}...</p>', unsafe_allow_html=True)
                    ci1, ci2 = st.columns(2)
                    if d.get("employees"): ci1.metric("Employees", f"{d['employees']:,}")
                    if d.get("website"):   ci2.markdown(f'<a href="{d["website"]}" target="_blank" style="color:#4f7cff">🌐 {d["website"]}</a>', unsafe_allow_html=True)

            # ── PRICING ──────────────────────────────────────────────────────────
            st.markdown(f'<div class="slbl">💰 {"ราคา" if TH else "Price"}</div>', unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Price",       f"${d['price']:,.2f}")
            c2.metric("Prev Close",  usd(d.get("prev_close")))
            c3.metric("Day High",    usd(d.get("day_high")))
            c4.metric("Day Low",     usd(d.get("day_low")))
            c5,c6,c7,c8 = st.columns(4)
            c5.metric("52W High",     usd(d.get("52w_high")))
            c6.metric("52W Low",      usd(d.get("52w_low")))
            c7.metric("Target Price", usd(d.get("target")))
            c8.metric("Market Cap",   fmt(d["cap"]))

            # ── VALUATION ────────────────────────────────────────────────────────
            st.markdown(f'<div class="slbl" style="margin-top:14px">📐 Valuation</div>', unsafe_allow_html=True)
            v1,v2,v3,v4 = st.columns(4)
            v1.metric("P/E (Trailing)", xf(d.get("pe")))
            v2.metric("P/E (Forward)",  xf(d.get("fwd_pe")))
            v3.metric("PEG Ratio",      xf(d.get("peg")))
            v4.metric("P/B Ratio",      xf(d.get("pb")))
            v5,v6,v7,v8 = st.columns(4)
            v5.metric("P/S Ratio",  xf(d.get("ps")))
            v6.metric("EV/EBITDA",  xf(d.get("ev_eb")))
            v7.metric("EPS (Trail)", usd(d.get("eps")))
            v8.metric("EPS (Fwd)",  usd(d.get("fwd_eps")))

            # ── FINANCIALS ───────────────────────────────────────────────────────
            st.markdown(f'<div class="slbl" style="margin-top:14px">📊 Financials</div>', unsafe_allow_html=True)
            f1,f2,f3,f4 = st.columns(4)
            f1.metric("Revenue",        fmt(d.get("rev")))
            f2.metric("Revenue Growth", pct(d.get("rev_g")))
            f3.metric("Gross Margin",   pct(d.get("gm")))
            f4.metric("Op Margin",      pct(d.get("om")))
            f5,f6,f7,f8 = st.columns(4)
            f5.metric("Net Margin",     pct(d.get("nm")))
            f6.metric("ROE",            pct(d.get("roe")))
            f7.metric("ROA",            pct(d.get("roa")))
            f8.metric("Free Cash Flow", fmt(d.get("fcf")))

            # ── BALANCE SHEET ────────────────────────────────────────────────────
            st.markdown(f'<div class="slbl" style="margin-top:14px">🏦 Balance Sheet & Risk</div>', unsafe_allow_html=True)
            b1,b2,b3,b4 = st.columns(4)
            b1.metric("Total Cash",    fmt(d.get("cash")))
            b2.metric("Total Debt",    fmt(d.get("debt")))
            b3.metric("Debt/Equity",   f"{d['de']:.1f}" if d.get("de") else "—")
            b4.metric("Current Ratio", f"{d['cr']:.2f}" if d.get("cr") else "—")
            b5,b6,b7,b8 = st.columns(4)
            b5.metric("Beta",           f"{d['beta']:.2f}" if d.get("beta") else "—")
            b6.metric("Dividend Yield", pct(d.get("div")))
            b7.metric("Short Ratio",    f"{d['short']:.1f}x" if d.get("short") else "—")
            b8.metric("Analyst Rating", d.get("ar","—"))

            st.divider()

            # ── PRICE CHART ──────────────────────────────────────────────────────
            st.markdown(f'<div class="slbl">📈 {"กราฟราคา" if TH else "Price Chart"}</div>', unsafe_allow_html=True)
            tp = st.radio("", ["1d","5d","1mo","3mo","1y","5y","max"], index=4, horizontal=True, key=f"p_{ticker}")
            hist = get_hist(ticker, tp)
            if not hist.empty:
                up  = hist["Close"].iloc[-1] >= hist["Close"].iloc[0]
                clr = "#34d399" if up else "#f87171"
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines",
                    line=dict(color=clr, width=1.8), fill="tozeroy",
                    fillcolor="rgba(52,211,153,.07)" if up else "rgba(248,113,113,.07)",
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>"))
                lo = plot_base(280); lo["yaxis"]["tickprefix"] = "$"
                fig.update_layout(**lo)
                st.plotly_chart(fig, use_container_width=True)

            # ── HISTORICAL FINANCIALS ────────────────────────────────────────────
            st.markdown(f'<div class="slbl" style="margin-top:8px">📉 Historical Financials</div>', unsafe_allow_html=True)
            fin = get_fin(ticker)
            if fin is not None and not fin.empty:
                try:
                    ft = fin.T.sort_index()
                    fig_f = go.Figure()
                    for col, (clr_, nm) in [
                        ("Total Revenue", ("#4f7cff", "Revenue $B")),
                        ("Net Income",    ("#34d399", "Net Income $B")),
                        ("Gross Profit",  ("#7c4fff", "Gross Profit $B"))
                    ]:
                        if col in ft.columns:
                            fig_f.add_trace(go.Bar(x=ft.index.year, y=ft[col]/1e9,
                                name=nm, marker_color=clr_, opacity=.85))
                    lo2 = plot_base(260); lo2["barmode"] = "group"; lo2["yaxis"]["ticksuffix"] = "B"
                    fig_f.update_layout(**lo2)
                    st.plotly_chart(fig_f, use_container_width=True)
                except: st.caption("Historical Financials unavailable")

            # ── DEEPV ANALYSIS ───────────────────────────────────────────────────
            if ai and "dimensions" in ai:
                st.divider()
                overall = ai.get("overall_score", 0)
                rec     = ai.get("recommendation", "—")
                rc      = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
                oc      = sc(overall)

                st.markdown(f"""<div style="background:{bg2};border-radius:12px;padding:20px;margin-bottom:20px;
                  display:flex;align-items:center;gap:20px;border:1px solid {border}">
                  <div style="text-align:center;min-width:65px">
                    <div style="font-size:2.2rem;font-weight:800;color:{oc}">{overall}</div>
                    <div style="font-size:.6rem;color:{muted};text-transform:uppercase">DEEPV Score</div>
                  </div>
                  <div style="flex:1">
                    <div style="background:{border};border-radius:999px;height:8px;overflow:hidden">
                      <div style="background:linear-gradient(90deg,#f87171,#fbbf24,#34d399);width:100%;height:100%;opacity:.25;border-radius:999px"></div>
                    </div>
                    <div style="background:transparent;border-radius:999px;height:8px;overflow:hidden;margin-top:-8px">
                      <div style="background:{oc};width:{overall}%;height:100%;border-radius:999px"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:4px">
                      <span style="font-size:.62rem;color:#f87171">{"เสี่ยงสูง 0-39" if TH else "High 0-39"}</span>
                      <span style="font-size:.62rem;color:#fbbf24">{"เสี่ยงกลาง 40-69" if TH else "Mid 40-69"}</span>
                      <span style="font-size:.62rem;color:#34d399">{"เสี่ยงต่ำ 70-100" if TH else "Low 70-100"}</span>
                    </div>
                  </div>
                  <div style="text-align:center;min-width:80px">
                    <div style="font-size:1.4rem;font-weight:800;color:{rc};background:{rc}18;border:1px solid {rc}44;border-radius:8px;padding:6px 14px">{rec}</div>
                    <div style="font-size:.6rem;color:{muted};text-transform:uppercase;margin-top:4px">Signal</div>
                  </div>
                </div>""", unsafe_allow_html=True)

                for key, dim in ai.get("dimensions", {}).items():
                    s = dim.get("score", 0); lc = sc(s); lbl = ll(dim.get("level","yellow"))
                    st.markdown(f"""<div class="dcard" style="border-left:3px solid {lc}">
                      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
                        <span style="font-size:1.6rem;font-weight:800;color:{lc};min-width:38px">{key}</span>
                        <div>
                          <div style="font-size:.95rem;font-weight:600;color:{text}">{dim.get('name','')}</div>
                          <div style="font-size:.78rem;color:{muted}">{dim.get('summary','')}</div>
                        </div>
                        <div style="margin-left:auto;text-align:right">
                          <div style="font-size:1.4rem;font-weight:700;color:{lc}">{s}<span style="font-size:.75rem;color:{muted}">/100</span></div>
                          <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;border-radius:6px;padding:1px 7px;font-size:.72rem">{lbl}</span>
                        </div>
                      </div>
                      <div style="height:4px;background:{border};border-radius:999px;margin-bottom:11px;overflow:hidden">
                        <div style="background:{lc};width:{s}%;height:100%;border-radius:999px"></div></div>
                      <p style="color:{muted};margin:0;font-size:.88rem;line-height:1.7">{dim.get('analysis','')}</p>
                    </div>""", unsafe_allow_html=True)

                cl2, cr2 = st.columns(2)
                with cl2:
                    st.markdown(f"""<div style="background:{bg2};border-radius:12px;padding:16px;border-left:3px solid #34d399">
                      <div style="font-size:.66rem;color:{muted};text-transform:uppercase;margin-bottom:8px">{"✅ ปัจจัยบวก" if TH else "✅ Catalysts"}</div>
                      <p style="color:{muted};margin:0;line-height:1.7;font-size:.88rem">{ai.get('catalysts','—')}</p></div>""", unsafe_allow_html=True)
                with cr2:
                    st.markdown(f"""<div style="background:{bg2};border-radius:12px;padding:16px;border-left:3px solid #f87171">
                      <div style="font-size:.66rem;color:{muted};text-transform:uppercase;margin-bottom:8px">{"⚠️ ความเสี่ยง" if TH else "⚠️ Risks"}</div>
                      <p style="color:{muted};margin:0;line-height:1.7;font-size:.88rem">{ai.get('risks','—')}</p></div>""", unsafe_allow_html=True)

                st.markdown(f"""<div style="background:{bg2};border-radius:12px;padding:16px;border-left:3px solid {rc};margin-top:12px">
                  <div style="font-size:.66rem;color:{muted};text-transform:uppercase;margin-bottom:8px">{"🧠 สรุปภาพรวม" if TH else "🧠 Summary"}</div>
                  <p style="color:{muted};margin:0;line-height:1.7">{ai.get('summary','')}</p></div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                # ── FULL HTML REPORT ─────────────────────────────────────────────
                html_rpt = build_html_report(ticker, d, ai)
                st.download_button(
                    "📄 " + ("ดาวน์โหลด DEEPV Report (HTML)" if TH else "Download DEEPV Report (HTML)"),
                    data=html_rpt.encode("utf-8"),
                    file_name=f"DEEPV_{ticker}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html", key=f"dl_{ticker}"
                )
                st.balloons()

            elif ai and "raw" in ai:
                st.warning("⚠️ AI ตอบผิดรูปแบบ กดวิเคราะห์ใหม่อีกครั้ง")
                with st.expander("Raw response"): st.text(ai["raw"])
            elif ai and "error" in ai:
                st.error(f"❌ {ai['error']}")
            elif not api_key:
                st.info("💡 " + ("ใส่ API Key เพื่อดู DEEPV Analysis" if TH else "Add API Key to see DEEPV Analysis"))

    # ── Compare Tab ──────────────────────────────────────────────────────────────
    if len(tr) > 1:
        with tabs[len(tr)]:
            st.markdown(f"### {'⚖️ เปรียบเทียบ' if TH else '⚖️ Compare'}")
            has_ai = {x: r["ai"] for x, r in results.items() if r["ai"] and "dimensions" in r["ai"]}
            pal    = ["#4f7cff", "#34d399", "#fbbf24"]

            if has_ai:
                dk = ["D","E1","E2","P","V"]
                dn = ["Durability","Earnings","Execution","Pricing","Valuation"]
                fig = go.Figure()
                for idx, (x, aai) in enumerate(has_ai.items()):
                    fig.add_trace(go.Bar(name=x, x=dn,
                        y=[aai["dimensions"].get(k,{}).get("score",0) for k in dk],
                        marker_color=pal[idx % len(pal)]))
                lo3 = plot_base(340); lo3["barmode"] = "group"; lo3["yaxis"]["range"] = [0, 100]
                fig.update_layout(**lo3)
                st.plotly_chart(fig, use_container_width=True)

                td = {}
                for x, aai in has_ai.items():
                    row = {}
                    for k in dk:
                        s  = aai["dimensions"].get(k,{}).get("score",0)
                        lv = aai["dimensions"].get(k,{}).get("level","yellow")
                        row[k] = f'{"🟢" if lv=="green" else "🟡" if lv=="yellow" else "🔴"} {s}'
                    row["Overall"] = aai.get("overall_score",0)
                    row["Signal"]  = aai.get("recommendation","—")
                    td[x] = row
                st.dataframe(pd.DataFrame(td).T, use_container_width=True)
            else:
                st.info("วิเคราะห์ 2+ ตัวพร้อม API Key" if TH else "Analyze 2+ stocks with API Key")

            st.markdown("#### " + ("เปรียบเทียบราคา (Normalized %)" if TH else "Price Comparison (Normalized %)"))
            cp = st.radio("", ["1mo","3mo","1y","5y"], index=2, horizontal=True, key="cmp")
            fig2 = go.Figure()
            for idx, x in enumerate(tr):
                h = get_hist(x, cp)
                if not h.empty:
                    norm = (h["Close"] / h["Close"].iloc[0]) * 100
                    fig2.add_trace(go.Scatter(x=h.index, y=norm, name=x,
                        line=dict(color=pal[idx % len(pal)], width=2),
                        hovertemplate=f"<b>{x}</b>: %{{y:.1f}}%<extra></extra>"))
            lo4 = plot_base(300); lo4["yaxis"]["ticksuffix"] = "%"
            fig2.update_layout(**lo4)
            st.plotly_chart(fig2, use_container_width=True)

    # ── Portfolio Tab ─────────────────────────────────────────────────────────────
    with tabs[-1]:
        st.markdown(f"### 💼 {'Portfolio Simulator' if not TH else 'Portfolio Simulator'}")
        pa_, pb_, pc_ = st.columns([2,1,1])
        with pa_: pt_ = st.text_input("Ticker", placeholder="NVDA, PTT.BK").upper().strip()
        with pb_: pal_ = st.number_input("%", min_value=1, max_value=100, value=25, step=5)
        with pc_:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ " + ("เพิ่มหุ้น" if TH else "Add")):
                if pt_:
                    if pt_ in [p["ticker"] for p in st.session_state.portfolio]:
                        st.warning("มีแล้ว" if TH else "Already added")
                    else:
                        with st.spinner(f"Loading {pt_}..."): pd_ = get_stock(pt_)
                        if pd_:
                            st.session_state.portfolio.append({
                                "ticker": pt_, "name": pd_["name"], "alloc": pal_,
                                "price": pd_["price"], "change": pd_["change"],
                                "sector": pd_["sector"], "pe": pd_.get("pe"), "beta": pd_.get("beta")
                            })
                            st.rerun()
                        else: st.error(f"❌ {pt_}")

        if results and st.button("📥 " + ("นำเข้าหุ้นที่วิเคราะห์แล้ว" if TH else "Import analyzed stocks")):
            ex = [p["ticker"] for p in st.session_state.portfolio]
            for x, r in results.items():
                if x not in ex and r["data"]:
                    d_ = r["data"]
                    ea = max(1, round(100 / max(1, len(results) + len(ex))))
                    st.session_state.portfolio.append({
                        "ticker": x, "name": d_["name"], "alloc": ea,
                        "price": d_["price"], "change": d_["change"],
                        "sector": d_["sector"], "pe": d_.get("pe"), "beta": d_.get("beta")
                    })
            st.rerun()

        port = st.session_state.portfolio
        if not port:
            st.markdown(f'<div style="text-align:center;padding:48px 0;color:{muted}"><div style="font-size:2.5rem">💼</div><p>{"ยังไม่มีหุ้นในพอร์ต" if TH else "Portfolio is empty"}</p></div>', unsafe_allow_html=True)
        else:
            st.markdown("---"); total = 0; upd = []
            for idx, p in enumerate(port):
                co1, co2, co3, co4 = st.columns([3,2,1,1])
                cc_ = "#34d399" if p["change"] >= 0 else "#f87171"
                with co1: st.markdown(f'<div style="padding:8px 0"><span style="font-weight:600;color:{text}">{p["ticker"]}</span> <span style="color:{muted};font-size:.8rem">{p["name"][:22]}</span> <span style="color:{cc_};font-size:.8rem">{"▲" if p["change"]>=0 else "▼"}{abs(p["change"]):.1f}%</span></div>', unsafe_allow_html=True)
                with co2: na = st.slider("", 1, 100, p["alloc"], key=f"sl_{idx}", label_visibility="collapsed"); p["alloc"] = na
                with co3: st.markdown(f'<div style="padding-top:10px;font-weight:700;color:#4f7cff">{na}%</div>', unsafe_allow_html=True)
                with co4:
                    if st.button("🗑️", key=f"del_{idx}"): st.session_state.portfolio.pop(idx); st.rerun()
                total += na; upd.append(p)
            st.session_state.portfolio = upd
            ac = "#34d399" if total==100 else "#fbbf24" if total<100 else "#f87171"
            st.markdown(f'<div style="text-align:right;font-size:.85rem;color:{ac};margin-bottom:12px">{"รวม" if TH else "Total"}: <strong>{total}%</strong> {"✅" if total==100 else "⚠️ ควรรวมเป็น 100%"}</div>', unsafe_allow_html=True)
            st.markdown("---")

            pp1, pp2 = st.columns(2)
            with pp1:
                st.markdown("#### Asset Allocation")
                fig_pie = go.Figure(go.Pie(
                    labels=[p["ticker"] for p in port], values=[p["alloc"] for p in port],
                    hole=.5, marker=dict(colors=["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa","#fb923c"][:len(port)]),
                    textinfo="label+percent", textfont=dict(color=text, size=12),
                    hovertemplate="<b>%{label}</b>: %{value}%<extra></extra>"))
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=260, showlegend=False, margin=dict(l=0,r=0,t=16,b=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            with pp2:
                st.markdown("#### Sector Breakdown")
                sa = {}
                for p in port: sa[p["sector"]] = sa.get(p["sector"],0) + p["alloc"]
                fig_s = go.Figure(go.Bar(x=list(sa.values()), y=list(sa.keys()), orientation="h",
                    marker_color="#7c4fff", text=[f"{v}%" for v in sa.values()],
                    textposition="outside", textfont=dict(color=muted)))
                lo5 = plot_base(260); lo5["xaxis"]["ticksuffix"] = "%"; lo5.pop("hovermode", None)
                fig_s.update_layout(**lo5)
                st.plotly_chart(fig_s, use_container_width=True)

            st.markdown("#### " + ("ผลตอบแทนพอร์ต (Normalized %)" if TH else "Portfolio Performance"))
            pp_r = st.radio("", ["1mo","3mo","1y","5y"], index=2, horizontal=True, key="port_p")
            fig_pf = go.Figure(); pr = None; cls_ = ["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa"]
            for idx, p in enumerate(port):
                h = get_hist(p["ticker"], pp_r)
                if not h.empty:
                    norm = (h["Close"] / h["Close"].iloc[0]) * 100
                    pr   = norm * (p["alloc"]/100) if pr is None else pr + norm * (p["alloc"]/100)
                    fig_pf.add_trace(go.Scatter(x=h.index, y=norm, name=p["ticker"],
                        line=dict(color=cls_[idx%len(cls_)], width=1.5, dash="dot"), opacity=.55,
                        hovertemplate=f"<b>{p['ticker']}</b>: %{{y:.1f}}%<extra></extra>"))
            if pr is not None:
                fig_pf.add_trace(go.Scatter(x=pr.index, y=pr, name="📦 Portfolio",
                    line=dict(color="#ffffff" if DARK else "#111827", width=2.5),
                    hovertemplate="<b>Portfolio</b>: %{y:.1f}%<extra></extra>"))
            lo6 = plot_base(300); lo6["yaxis"]["ticksuffix"] = "%"
            fig_pf.update_layout(**lo6)
            st.plotly_chart(fig_pf, use_container_width=True)

            m1, m2, m3 = st.columns(3)
            m1.metric("Holdings", f"{len(port)}")
            m2.metric("Weighted Beta", f"{sum([(p.get('beta') or 1)*p['alloc']/100 for p in port]):.2f}")
            m3.metric("Today (Weighted)", f"{sum([p['change']*p['alloc']/100 for p in port]):+.2f}%")

            if st.button("🗑️ " + ("ล้างพอร์ตทั้งหมด" if TH else "Clear Portfolio")):
                st.session_state.portfolio = []; st.rerun()
