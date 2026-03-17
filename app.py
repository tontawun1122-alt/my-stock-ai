import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import json
import re
from datetime import datetime

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="D.E.E.P.V AI Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ────────────────────────────────────────────────────────────────────────
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
        font-size: 1.6rem !important; font-weight: 700 !important; color: #e8eaf0 !important;
    }
    [data-testid="stSidebar"] { background: #13161e; border-right: 1px solid #2d313d; }
    .stButton > button {
        background: linear-gradient(135deg, #4f7cff, #7c4fff);
        color: white; border: none; border-radius: 8px;
        padding: 10px 20px; font-weight: 600; width: 100%; transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }
    hr { border-color: #2d313d !important; }
    .deepv-card {
        background: #1c1f26; border: 1px solid #2d313d;
        border-radius: 12px; padding: 20px; margin-bottom: 12px;
    }
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ────────────────────────────────────────────────────────────────────
def fmt_large(value: float) -> str:
    if not value: return "—"
    if value >= 1e12: return f"${value/1e12:.2f}T"
    elif value >= 1e9: return f"${value/1e9:.2f}B"
    elif value >= 1e6: return f"${value/1e6:.2f}M"
    return f"${value:,.0f}"

def safe_pct_change(info: dict) -> float:
    raw = info.get("regularMarketChangePercent", 0) or 0
    return raw * 100 if abs(raw) < 1.0 else raw

def score_color(score: int) -> str:
    if score >= 70: return "#34d399"
    elif score >= 40: return "#fbbf24"
    return "#f87171"

def level_label(level: str) -> str:
    return {"green": "🟢 เสี่ยงต่ำ", "yellow": "🟡 เสี่ยงกลาง", "red": "🔴 เสี่ยงสูง"}.get(level, "—")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
            return None
        return {
            "name":         info.get("longName") or info.get("shortName") or ticker,
            "price":        info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "change":       safe_pct_change(info),
            "cap":          info.get("marketCap") or 0,
            "sector":       info.get("sector", "—"),
            "industry":     info.get("industry", "—"),
            "pe":           info.get("trailingPE"),
            "eps":          info.get("trailingEps"),
            "revenue":      info.get("totalRevenue"),
            "gross_margin": info.get("grossMargins"),
            "52w_high":     info.get("fiftyTwoWeekHigh"),
            "52w_low":      info.get("fiftyTwoWeekLow"),
            "ticker":       ticker,
        }
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(ticker: str, period: str) -> pd.DataFrame:
    return yf.Ticker(ticker).history(period=period)


def get_deepv_analysis(api_key: str, ticker: str, stock_data: dict) -> dict:
    genai.configure(api_key=api_key)
    try:
        available = [m.name for m in genai.list_models()
                     if "generateContent" in m.supported_generation_methods]
        preferred = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-pro"]
        model_name = next((m for m in preferred if m in available),
                          available[0] if available else None)
        if not model_name:
            return {"error": "ไม่พบโมเดล AI"}
    except Exception as e:
        return {"error": f"ตรวจสอบ API Key ไม่สำเร็จ: {e}"}

    prompt = f"""คุณเป็น AI Analyst ผู้เชี่ยวชาญด้านการวิเคราะห์หุ้นเชิงปัจจัยพื้นฐาน
วิเคราะห์หุ้น {ticker} ({stock_data['name']}) ด้วย Framework D.E.E.P.V

ข้อมูลปัจจุบัน:
- ราคา: ${stock_data['price']} | เปลี่ยนแปลง: {stock_data['change']:.2f}%
- Market Cap: {fmt_large(stock_data['cap'])}
- Sector: {stock_data['sector']} / {stock_data['industry']}
- P/E: {stock_data.get('pe', 'N/A')} | EPS: {stock_data.get('eps', 'N/A')}
- Revenue: {fmt_large(stock_data.get('revenue') or 0)} | Gross Margin: {f"{stock_data.get('gross_margin',0)*100:.1f}%" if stock_data.get('gross_margin') else 'N/A'}

ตอบเป็น JSON เท่านั้น ห้ามมี markdown, backtick, หรือข้อความอื่น:
{{
  "dimensions": {{
    "D": {{"name":"Durability","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<3-5 ประโยคไทย>"}},
    "E1": {{"name":"Earnings Quality","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<3-5 ประโยคไทย>"}},
    "E2": {{"name":"Execution","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<3-5 ประโยคไทย>"}},
    "P": {{"name":"Pricing Power","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<3-5 ประโยคไทย>"}},
    "V": {{"name":"Valuation","score":<0-100>,"level":"<green|yellow|red>","summary":"<1 บรรทัดไทย>","analysis":"<3-5 ประโยคไทย>"}}
  }},
  "overall_score": <0-100>,
  "overall_level": "<green|yellow|red>",
  "recommendation": "<BUY|HOLD|AVOID>",
  "summary": "<สรุปภาพรวม 3-4 ประโยคไทย>"
}}
กฎ: 70-100=green, 40-69=yellow, 0-39=red"""

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = re.sub(r'^```json\s*|\s*```$', '', response.text.strip())
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": response.text}
    except Exception as e:
        return {"error": str(e)}


def generate_html_report(ticker: str, stock_data: dict, ai_result: dict) -> str:
    dims    = ai_result.get("dimensions", {})
    overall = ai_result.get("overall_score", 0)
    rec     = ai_result.get("recommendation", "—")
    summary = ai_result.get("summary", "")
    rc  = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
    oc  = score_color(overall)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    rows = ""
    for key, dim in dims.items():
        lc = score_color(dim.get("score", 0))
        rows += f"""
        <div style="margin-bottom:16px;padding:16px;background:#1c1f26;border-radius:10px;border-left:3px solid {lc}">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="font-size:1.4rem;font-weight:800;color:{lc}">{key}</span>
            <span style="font-size:0.95rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</span>
            <span style="margin-left:auto;font-size:1.1rem;font-weight:700;color:{lc}">{dim.get('score',0)}/100</span>
            <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;border-radius:6px;padding:2px 10px;font-size:0.75rem">{level_label(dim.get('level',''))}</span>
          </div>
          <div style="background:#2d313d;border-radius:999px;height:5px;margin-bottom:10px;overflow:hidden">
            <div style="background:{lc};width:{dim.get('score',0)}%;height:100%;border-radius:999px"></div>
          </div>
          <p style="color:#8b92a5;margin:0 0 6px;font-size:0.8rem">{dim.get('summary','')}</p>
          <p style="color:#c5c9d6;margin:0;font-size:0.88rem;line-height:1.6">{dim.get('analysis','')}</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<title>DEEPV Report: {ticker}</title>
<style>
  body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#0e1117;color:#e8eaf0;margin:0;padding:40px;max-width:900px;margin:0 auto}}
  .metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px}}
  .metric{{background:#1c1f26;border-radius:10px;padding:14px}}
  .mlabel{{font-size:0.7rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.05em}}
  .mvalue{{font-size:1.25rem;font-weight:700;color:#e8eaf0}}
  @media print{{body{{background:white;color:black}}}}
</style>
</head>
<body>
<div style="border-bottom:1px solid #2d313d;padding-bottom:20px;margin-bottom:24px">
  <div style="font-size:0.75rem;color:#8b92a5;margin-bottom:4px">D.E.E.P.V AI Analyst · {now}</div>
  <h1 style="margin:0;font-size:1.8rem">{stock_data.get('name',ticker)}
    <span style="color:#8b92a5;font-size:1rem">({ticker})</span></h1>
  <div style="margin-top:10px;display:flex;align-items:center;gap:24px">
    <span style="font-size:1.4rem;font-weight:700">${stock_data.get('price',0):,.2f}</span>
    <div style="text-align:center">
      <div style="font-size:2rem;font-weight:800;color:{oc}">{overall}</div>
      <div style="font-size:0.65rem;color:#8b92a5">DEEPV SCORE</div>
    </div>
    <div style="text-align:center">
      <div style="font-size:1.3rem;font-weight:800;color:{rc}">{rec}</div>
      <div style="font-size:0.65rem;color:#8b92a5">RECOMMENDATION</div>
    </div>
  </div>
</div>
<div class="metrics">
  <div class="metric"><div class="mlabel">Market Cap</div><div class="mvalue">{fmt_large(stock_data.get('cap',0))}</div></div>
  <div class="metric"><div class="mlabel">P/E Ratio</div><div class="mvalue">{f"{stock_data.get('pe',0):.1f}x" if stock_data.get('pe') else '—'}</div></div>
  <div class="metric"><div class="mlabel">Sector</div><div class="mvalue" style="font-size:0.9rem">{stock_data.get('sector','—')}</div></div>
</div>
<div style="font-size:0.72rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px">DEEPV Analysis</div>
{rows}
<div style="background:#1c1f26;border-radius:10px;padding:16px;border-left:3px solid {rc}">
  <div style="font-size:0.7rem;color:#8b92a5;text-transform:uppercase;margin-bottom:8px">สรุปภาพรวม</div>
  <p style="margin:0;line-height:1.7;color:#c5c9d6">{summary}</p>
</div>
</body></html>"""


# ─── Session State ───────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = {}


# ─── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 D.E.E.P.V Analyst")
    api_key = st.text_input("Google Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")
    st.markdown("**Ticker Symbols**")
    st.caption("รองรับหุ้นสหรัฐ (NVDA) และหุ้นไทย (PTT.BK)")
    ticker1 = st.text_input("หุ้นตัวที่ 1", value="NVDA").upper().strip()
    ticker2 = st.text_input("หุ้นตัวที่ 2 (เปรียบเทียบ)", value="").upper().strip()
    ticker3 = st.text_input("หุ้นตัวที่ 3 (เปรียบเทียบ)", value="").upper().strip()
    analyze_btn = st.button("🚀 วิเคราะห์หุ้น")
    st.divider()
    st.caption("D · Durability\nE · Earnings Quality\nE · Execution\nP · Pricing Power\nV · Valuation")


# ─── Main Logic ──────────────────────────────────────────────────────────────────
tickers = [t for t in [ticker1, ticker2, ticker3] if t]

if analyze_btn and tickers:
    st.session_state.results = {}
    for ticker in tickers:
        with st.spinner(f"กำลังโหลด {ticker}..."):
            data = fetch_stock(ticker)
        if data is None:
            st.error(f"❌ ไม่พบข้อมูล {ticker}")
            continue
        ai_result = None
        if api_key:
            with st.spinner(f"🧠 AI วิเคราะห์ {ticker}..."):
                ai_result = get_deepv_analysis(api_key, ticker, data)
        st.session_state.results[ticker] = {"data": data, "ai": ai_result}


# ─── Display ─────────────────────────────────────────────────────────────────────
results = st.session_state.results

if not results:
    st.markdown("""
    <div style="text-align:center;padding:80px 0;color:#8b92a5">
        <div style="font-size:3rem;margin-bottom:16px">📊</div>
        <h3 style="color:#e8eaf0">D.E.E.P.V AI Stock Analyst</h3>
        <p>ใส่ Ticker และกด "วิเคราะห์หุ้น" เพื่อเริ่มต้น</p>
        <p style="font-size:0.8rem;margin-top:24px;color:#444">
            รองรับหุ้นสหรัฐ (NVDA, AAPL) และหุ้นไทย (PTT.BK, ADVANC.BK)
        </p>
    </div>
    """, unsafe_allow_html=True)

else:
    tickers_ready = list(results.keys())
    tab_labels = [f"📈 {t}" for t in tickers_ready]
    if len(tickers_ready) > 1:
        tab_labels.append("⚖️ เปรียบเทียบ")
    tabs = st.tabs(tab_labels)

    # ── Per-ticker tabs
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

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("ราคาล่าสุด", f"${d['price']:,.2f}")
            c2.metric("Market Cap",  fmt_large(d["cap"]))
            c3.metric("P/E Ratio",   f"{d['pe']:.1f}x"  if d.get("pe")  else "—")
            c4.metric("EPS",         f"${d['eps']:.2f}" if d.get("eps") else "—")

            c5,c6,c7,c8 = st.columns(4)
            c5.metric("52W High",     f"${d['52w_high']:,.2f}" if d.get("52w_high")    else "—")
            c6.metric("52W Low",      f"${d['52w_low']:,.2f}"  if d.get("52w_low")     else "—")
            c7.metric("Revenue",      fmt_large(d["revenue"])  if d.get("revenue")     else "—")
            gm = d.get("gross_margin")
            c8.metric("Gross Margin", f"{gm*100:.1f}%"         if gm                  else "—")

            st.divider()

            # Chart
            t_period = st.radio("ช่วงเวลา", ["1d","5d","1mo","3mo","1y","5y","max"],
                                index=4, horizontal=True, key=f"p_{ticker}")
            hist = fetch_history(ticker, t_period)
            if not hist.empty:
                up   = hist["Close"].iloc[-1] >= hist["Close"].iloc[0]
                clr  = "#34d399" if up else "#f87171"
                fill = "rgba(52,211,153,0.08)" if up else "rgba(248,113,113,0.08)"
                fig  = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist["Close"], mode="lines",
                    line=dict(color=clr, width=1.8),
                    fill="tozeroy", fillcolor=fill,
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

            # ── DEEPV Analysis
            if ai and "dimensions" in ai:
                st.divider()
                overall   = ai.get("overall_score", 0)
                rec       = ai.get("recommendation", "—")
                rc        = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
                oc        = score_color(overall)

                # Overall bar
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
                  </div>
                  <div style="text-align:center;min-width:70px">
                    <div style="font-size:1.4rem;font-weight:800;color:{rc}">{rec}</div>
                    <div style="font-size:0.65rem;color:#8b92a5;text-transform:uppercase">Recommendation</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Dimension cards with traffic light
                for key, dim in ai.get("dimensions", {}).items():
                    sc  = dim.get("score", 0)
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
                    </div>
                    """, unsafe_allow_html=True)

                # Summary
                summary = ai.get("summary","")
                if summary:
                    st.markdown(f"""
                    <div style="background:#1c1f26;border-radius:12px;padding:20px;border-left:3px solid {rc};margin-top:4px">
                      <div style="font-size:0.7rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">สรุปภาพรวม</div>
                      <p style="color:#c5c9d6;margin:0;line-height:1.7">{summary}</p>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # Download Report
                html_report = generate_html_report(ticker, d, ai)
                st.download_button(
                    label="📄 ดาวน์โหลด DEEPV Report (HTML)",
                    data=html_report.encode("utf-8"),
                    file_name=f"DEEPV_{ticker}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html",
                    key=f"dl_{ticker}",
                )
                st.balloons()

            elif ai and "raw" in ai:
                st.markdown(f'<div style="background:#1c1f26;border-radius:12px;padding:20px">{ai["raw"]}</div>',
                            unsafe_allow_html=True)
            elif ai and "error" in ai:
                st.error(f"❌ {ai['error']}")
            elif not api_key:
                st.info("💡 ใส่ Google Gemini API Key ใน Sidebar เพื่อดูผลวิเคราะห์ DEEPV")

    # ── Compare tab
    if len(tickers_ready) > 1:
        with tabs[-1]:
            st.markdown("### ⚖️ เปรียบเทียบ DEEPV Score")
            has_ai  = {t: r["ai"] for t, r in results.items() if r["ai"] and "dimensions" in r["ai"]}
            palette = ["#4f7cff", "#34d399", "#fbbf24"]

            if has_ai:
                dim_keys  = ["D", "E1", "E2", "P", "V"]
                dim_names = ["Durability","Earnings Quality","Execution","Pricing Power","Valuation"]

                fig = go.Figure()
                for idx,(t,ai) in enumerate(has_ai.items()):
                    scores = [ai["dimensions"].get(k,{}).get("score",0) for k in dim_keys]
                    fig.add_trace(go.Bar(name=t, x=dim_names, y=scores,
                                        marker_color=palette[idx % len(palette)]))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e",
                    barmode="group", height=360,
                    yaxis=dict(range=[0,100], gridcolor="#1c2030", tickfont=dict(color="#8b92a5")),
                    xaxis=dict(tickfont=dict(color="#8b92a5")),
                    legend=dict(font=dict(color="#8b92a5"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0,r=0,t=16,b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Score table
                st.markdown("#### คะแนนแยกรายด้าน")
                table_data = {}
                for t, ai in has_ai.items():
                    row = {}
                    for k in dim_keys:
                        sc = ai["dimensions"].get(k,{}).get("score",0)
                        lv = ai["dimensions"].get(k,{}).get("level","yellow")
                        emoji = {"green":"🟢","yellow":"🟡","red":"🔴"}.get(lv,"⚪")
                        row[k] = f"{emoji} {sc}"
                    row["Overall"] = ai.get("overall_score",0)
                    row["Rating"]  = ai.get("recommendation","—")
                    table_data[t]  = row
                st.dataframe(pd.DataFrame(table_data).T, use_container_width=True)
            else:
                st.info("วิเคราะห์หุ้นอย่างน้อย 2 ตัวพร้อม API Key เพื่อดูกราฟเปรียบเทียบ")

            # Normalized price comparison
            st.markdown("#### เปรียบเทียบราคา (Normalized %)")
            period_cmp = st.radio("ช่วงเวลา", ["1mo","3mo","1y","5y"],
                                  index=2, horizontal=True, key="cmp")
            fig2 = go.Figure()
            for idx, t in enumerate(tickers_ready):
                hist = fetch_history(t, period_cmp)
                if not hist.empty:
                    norm = (hist["Close"] / hist["Close"].iloc[0]) * 100
                    fig2.add_trace(go.Scatter(
                        x=hist.index, y=norm, name=t,
                        line=dict(color=palette[idx % len(palette)], width=2),
                        hovertemplate=f"<b>{t}</b>: %{{y:.1f}}%<extra></extra>",
                    ))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#13161e", height=300,
                xaxis=dict(showgrid=False, tickfont=dict(color="#8b92a5",size=11)),
                yaxis=dict(gridcolor="#1c2030", tickfont=dict(color="#8b92a5",size=11), ticksuffix="%"),
                legend=dict(font=dict(color="#8b92a5"), bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0,r=0,t=16,b=0),
                hovermode="x unified",
            )
            st.plotly_chart(fig2, use_container_width=True)
