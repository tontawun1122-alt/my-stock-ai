import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import json, re
from datetime import datetime, timezone

st.set_page_config(page_title="D.E.E.P.V AI Analyst", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

for k,v in [("results",{}),("portfolio",[]),("lang","TH"),("theme","dark")]:
    if k not in st.session_state: st.session_state[k]=v

LANG=st.session_state.lang; DARK=st.session_state.theme=="dark"; TH=LANG=="TH"

if DARK:
    bg="#0e1117"; bg2="#1c1f26"; bg3="#13161e"; border="#2d313d"
    txt="#e8eaf0"; muted="#8b92a5"; plot_bg="#13161e"; grid_c="#1c2030"
    news_title="#e8eaf0"; news_hover="#4f7cff"
else:
    bg="#f0f2f6"; bg2="#ffffff"; bg3="#e8eaf0"; border="#d1d5db"
    txt="#111827"; muted="#6b7280"; plot_bg="#f8fafc"; grid_c="#e5e7eb"
    news_title="#111827"; news_hover="#2563eb"

st.markdown(f"""<style>
.stApp{{background:{bg}}}
[data-testid="metric-container"]{{
    background:{bg2}!important;border:1px solid {border}!important;
    border-radius:8px!important;padding:6px 10px!important;min-height:0!important;
}}
[data-testid="metric-container"] label,
[data-testid="metric-container"] [data-testid="stMetricLabel"] p,
[data-testid="metric-container"] [data-testid="stMetricLabel"] span{{
    font-size:.58rem!important;color:{muted}!important;
    text-transform:uppercase!important;letter-spacing:.04em!important;
    line-height:1.2!important;margin:0!important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"],
[data-testid="metric-container"] [data-testid="stMetricValue"] div{{
    font-size:.88rem!important;font-weight:700!important;
    color:{txt}!important;line-height:1.3!important;
    padding:0!important;margin:0!important;
}}
[data-testid="metric-container"] [data-testid="stMetricDelta"]{{display:none!important;}}
[data-testid="stSidebar"]{{background:{bg3};border-right:1px solid {border}}}
.stButton>button{{
    background:linear-gradient(135deg,#4f7cff,#7c4fff);
    color:white;border:none;border-radius:8px;
    padding:8px 16px;font-weight:600;width:100%;
}}
hr{{border-color:{border}!important}}
.dcard{{background:{bg2};border:1px solid {border};border-radius:12px;padding:16px;margin-bottom:10px}}
.slbl{{
    font-size:.6rem;color:{muted};text-transform:uppercase;
    letter-spacing:.1em;margin-bottom:6px;margin-top:10px;
    display:block;
}}
/* ── News card ── */
.news-item{{
    background:{bg2};border:1px solid {border};
    border-radius:8px;padding:12px 14px;margin-bottom:7px;
}}
.news-item a{{
    color:{news_title}!important;
    text-decoration:none;
    font-size:.85rem;
    font-weight:600;
    line-height:1.5;
    display:block;
}}
.news-item a:hover{{color:{news_hover}!important}}
.news-meta{{font-size:.68rem;color:{muted};margin-top:5px}}
/* ── Peer card ── */
.peer-card{{
    background:{bg2};border:1px solid {border};
    border-radius:10px;padding:12px;text-align:center;
}}
.peer-ticker{{font-size:.9rem;font-weight:700;color:{txt}}}
.peer-name{{font-size:.68rem;color:{muted};margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.peer-price{{font-size:1rem;font-weight:700;color:{txt}}}
/* ── Index card ── */
.idx-card{{background:{bg2};border:1px solid {border};border-radius:8px;padding:10px;text-align:center;margin-bottom:8px}}
.idx-name{{font-size:.65rem;color:{muted};margin-bottom:3px}}
.idx-price{{font-size:.95rem;font-weight:700;color:{txt}}}
/* Remove streamlit default color override — IMPORTANT */
#MainMenu,footer{{visibility:hidden}}
.block-container{{padding-top:1.5rem;padding-bottom:2rem}}
</style>""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────────
def fmt(v):
    if v is None or v==0: return "—"
    s="-" if v<0 else ""; v=abs(v)
    if v>=1e12: return f"{s}${v/1e12:.2f}T"
    if v>=1e9:  return f"{s}${v/1e9:.2f}B"
    if v>=1e6:  return f"{s}${v/1e6:.2f}M"
    return f"{s}${v:,.0f}"

def cpct(info):
    c=info.get("currentPrice") or info.get("regularMarketPrice") or 0
    p=info.get("previousClose") or 0
    return ((c-p)/p*100) if p else 0.0

def sc(s): return "#34d399" if s>=70 else "#fbbf24" if s>=40 else "#f87171"
def ll(l):
    m={"green":("🟢 เสี่ยงต่ำ","🟢 Low Risk"),
       "yellow":("🟡 เสี่ยงกลาง","🟡 Med Risk"),
       "red":("🔴 เสี่ยงสูง","🔴 High Risk")}
    return m.get(l,("—","—"))[0 if TH else 1]
def pct(v):  return f"{v*100:.1f}%" if v else "—"
def usd(v):  return f"${v:,.2f}" if v else "—"
def xf(v):   return f"{v:.1f}x" if v else "—"

def plot_base(h=260):
    return dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=plot_bg,
        margin=dict(l=0,r=0,t=12,b=0), height=h, hovermode="x unified",
        xaxis=dict(showgrid=False, tickfont=dict(color=muted,size=10)),
        yaxis=dict(gridcolor=grid_c, tickfont=dict(color=muted,size=10)),
        legend=dict(font=dict(color=muted,size=10), bgcolor="rgba(0,0,0,0)"),
        font=dict(color=txt),
    )

SECTOR_PEERS = {
    "Technology":            ["AAPL","MSFT","NVDA","GOOG","META","AVGO","AMD","ORCL"],
    "Consumer Cyclical":     ["AMZN","TSLA","HD","NKE","MCD","SBUX","TGT","LOW"],
    "Healthcare":            ["JNJ","UNH","PFE","ABBV","MRK","LLY","TMO","ABT"],
    "Financials":            ["JPM","BAC","WFC","GS","MS","C","BLK","AXP"],
    "Communication Services":["GOOG","META","NFLX","DIS","T","VZ","CMCSA","SPOT"],
    "Energy":                ["XOM","CVX","COP","SLB","EOG","MPC","VLO","OXY"],
    "Industrials":           ["HON","UPS","CAT","DE","LMT","RTX","GE","FDX"],
    "Consumer Defensive":    ["WMT","PG","KO","PEP","COST","PM","CL","GIS"],
    "Basic Materials":       ["LIN","APD","ECL","SHW","NEM","FCX","CF","ALB"],
}

INDICES = {
    "S&P 500":"^GSPC","NASDAQ":"^IXIC","Dow Jones":"^DJI",
    "SET (TH)":"^SET.BK","Nikkei 225":"^N225","Hang Seng":"^HSI",
    "FTSE 100":"^FTSE","DAX":"^GDAXI",
}


@st.cache_data(ttl=300, show_spinner=False)
def get_stock(ticker):
    try:
        info = yf.Ticker(ticker).info
        if not info or (not info.get("currentPrice") and not info.get("regularMarketPrice")):
            return None
        return {
            "name":     info.get("longName") or info.get("shortName") or ticker,
            "ticker":   ticker, "change": cpct(info),
            "sector":   info.get("sector","—"), "industry": info.get("industry","—"),
            "website":  info.get("website",""), "country":  info.get("country","—"),
            "description": info.get("longBusinessSummary",""),
            "employees": info.get("fullTimeEmployees"),
            "price":    info.get("currentPrice") or info.get("regularMarketPrice",0),
            "prev_close":info.get("previousClose"), "day_high":info.get("dayHigh"),
            "day_low":  info.get("dayLow"), "52w_high":info.get("fiftyTwoWeekHigh"),
            "52w_low":  info.get("fiftyTwoWeekLow"), "target":info.get("targetMeanPrice"),
            "cap":      info.get("marketCap",0),
            "pe":       info.get("trailingPE"),   "fwd_pe": info.get("forwardPE"),
            "peg":      info.get("pegRatio"),      "pb":     info.get("priceToBook"),
            "ps":       info.get("priceToSalesTrailing12Months"),
            "ev_eb":    info.get("enterpriseToEbitda"),
            "eps":      info.get("trailingEps"),   "fwd_eps":info.get("forwardEps"),
            "rev":      info.get("totalRevenue"),  "rev_g":  info.get("revenueGrowth"),
            "gm":       info.get("grossMargins"),  "om":     info.get("operatingMargins"),
            "nm":       info.get("profitMargins"), "roe":    info.get("returnOnEquity"),
            "roa":      info.get("returnOnAssets"),"fcf":    info.get("freeCashflow"),
            "cash":     info.get("totalCash"),     "debt":   info.get("totalDebt"),
            "de":       info.get("debtToEquity"),  "cr":     info.get("currentRatio"),
            "div":      info.get("dividendYield"), "beta":   info.get("beta"),
            "short":    info.get("shortRatio"),
            "ar":       info.get("recommendationKey","").upper(),
        }
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}"); return None


@st.cache_data(ttl=300,  show_spinner=False)
def get_hist(ticker, period): return yf.Ticker(ticker).history(period=period)

@st.cache_data(ttl=3600, show_spinner=False)
def get_fin(ticker):
    try: return yf.Ticker(ticker).financials
    except: return None

@st.cache_data(ttl=600,  show_spinner=False)
def get_news(ticker):
    try:
        raw = yf.Ticker(ticker).news or []
        out = []
        for n in raw[:6]:
            # yfinance >=0.2.x returns nested structure
            content = n.get("content") or n
            title   = content.get("title") or n.get("title","")
            link    = (content.get("canonicalUrl") or {}).get("url") or n.get("link","#")
            pub     = (content.get("provider") or {}).get("displayName") or n.get("publisher","")
            ts      = n.get("providerPublishTime") or 0
            if title:
                try: dt=datetime.fromtimestamp(ts,tz=timezone.utc).strftime("%d %b %Y") if ts else ""
                except: dt=""
                out.append({"title":title,"link":link,"publisher":pub,"date":dt})
        return out
    except: return []

@st.cache_data(ttl=300, show_spinner=False)
def get_peer_quick(ticker):
    try:
        info = yf.Ticker(ticker).fast_info
        price = getattr(info,"last_price",None) or 0
        prev  = getattr(info,"previous_close",None) or 0
        cap   = getattr(info,"market_cap",None) or 0
        chg   = ((price-prev)/prev*100) if prev else 0
        full  = yf.Ticker(ticker).info
        return {"ticker":ticker,
                "name":  full.get("shortName") or ticker,
                "price": price, "change": chg, "cap": cap,
                "pe":    full.get("trailingPE"),
                "gm":    full.get("grossMargins")}
    except: return None

@st.cache_data(ttl=300, show_spinner=False)
def get_index_data(symbol):
    try:
        fi = yf.Ticker(symbol).fast_info
        price = getattr(fi,"last_price",None) or 0
        prev  = getattr(fi,"previous_close",None) or 0
        chg   = ((price-prev)/prev*100) if prev else 0
        return {"price":price,"change":chg}
    except: return None


def calc_deepv_auto(d) -> dict:
    """คำนวณ DEEPV Score อัตโนมัติจากตัวเลข ไม่ต้องใช้ API"""
    def clamp(v): return max(5, min(95, int(v)))

    gm    = d.get("gm")    or 0
    de    = d.get("de")    or 0
    cr    = d.get("cr")    or 0
    beta  = d.get("beta")  or 1
    nm    = d.get("nm")    or 0
    roe   = d.get("roe")   or 0
    roa   = d.get("roa")   or 0
    fcf   = d.get("fcf")   or 0
    rev   = d.get("rev")   or 1
    rev_g = d.get("rev_g") or 0
    om    = d.get("om")    or 0
    pe    = d.get("pe")    or 0
    fwd_pe= d.get("fwd_pe")or 0
    pb    = d.get("pb")    or 0
    ps    = d.get("ps")    or 0

    # ── D: Durability ─────────────────────────────────── max 100
    # Gross Margin (0-40 pts)
    d_gm  = 40 if gm>0.6 else 30 if gm>0.4 else 18 if gm>0.2 else 8 if gm>0 else 0
    # Debt/Equity (0-25 pts)
    d_de  = 25 if de<0.3 else 18 if de<1 else 10 if de<2 else 4 if de<4 else 0
    # Current Ratio (0-20 pts)
    d_cr  = 20 if cr>2.5 else 14 if cr>1.5 else 8 if cr>1 else 2
    # Beta (0-15 pts)
    d_bt  = 15 if beta<0.8 else 10 if beta<1.2 else 6 if beta<1.8 else 2
    d_score = clamp(d_gm + d_de + d_cr + d_bt)

    # ── E1: Earnings Quality ──────────────────────────── max 100
    # Net Margin (0-35 pts)
    e1_nm = 35 if nm>0.25 else 25 if nm>0.15 else 14 if nm>0.05 else 4 if nm>0 else 0
    # ROE (0-30 pts)
    e1_roe= 30 if roe>0.25 else 20 if roe>0.15 else 10 if roe>0.05 else 2 if roe>0 else 0
    # ROA (0-20 pts)
    e1_roa= 20 if roa>0.12 else 13 if roa>0.06 else 6 if roa>0 else 0
    # FCF Yield (0-15 pts)
    fcf_yield = fcf/rev if rev else 0
    e1_fcf= 15 if fcf_yield>0.15 else 10 if fcf_yield>0.08 else 5 if fcf_yield>0 else 0
    e1_score = clamp(e1_nm + e1_roe + e1_roa + e1_fcf)

    # ── E2: Execution ─────────────────────────────────── max 100
    # Revenue Growth (0-50 pts)
    e2_rg = 50 if rev_g>0.35 else 38 if rev_g>0.2 else 24 if rev_g>0.1 else 12 if rev_g>0 else 0
    # Operating Margin (0-35 pts)
    e2_om = 35 if om>0.3 else 25 if om>0.15 else 14 if om>0.05 else 4 if om>0 else 0
    # ROE bonus (0-15 pts)
    e2_roe= 15 if roe>0.2 else 8 if roe>0.1 else 2 if roe>0 else 0
    e2_score = clamp(e2_rg + e2_om + e2_roe)

    # ── P: Pricing Power ──────────────────────────────── max 100
    # Gross Margin หลัก (0-55 pts)
    p_gm  = 55 if gm>0.65 else 42 if gm>0.5 else 28 if gm>0.35 else 14 if gm>0.2 else 4
    # Operating Margin (0-30 pts)
    p_om  = 30 if om>0.25 else 20 if om>0.12 else 10 if om>0.05 else 2 if om>0 else 0
    # Rev Growth สะท้อน demand (0-15 pts)
    p_rg  = 15 if rev_g>0.2 else 8 if rev_g>0.1 else 3 if rev_g>0 else 0
    p_score = clamp(p_gm + p_om + p_rg)

    # ── V: Valuation ──────────────────────────────────── max 100
    # เริ่มที่ 80 แล้วลดตาม P/E (ยิ่งแพงยิ่งต่ำ)
    if pe <= 0:
        v_pe = 40  # ไม่มี P/E = ขาดทุน
    elif pe < 12:  v_pe = 80
    elif pe < 18:  v_pe = 70
    elif pe < 25:  v_pe = 58
    elif pe < 35:  v_pe = 44
    elif pe < 50:  v_pe = 30
    elif pe < 80:  v_pe = 18
    else:          v_pe = 8

    # Forward P/E adjust (±10 pts)
    v_fpe = 0
    if fwd_pe > 0:
        v_fpe = 10 if fwd_pe < pe*0.8 else -10 if fwd_pe > pe else 0

    # P/B (0-10 pts)
    v_pb  = 10 if pb<2 else 6 if pb<5 else 2 if pb<10 else -5

    # P/S (0-10 pts เหมาะ growth stock)
    v_ps  = 10 if ps<3 else 4 if ps<8 else 0 if ps<15 else -5

    v_score = clamp(v_pe + v_fpe + v_pb + v_ps)

    scores = {"D": d_score, "E1": e1_score, "E2": e2_score, "P": p_score, "V": v_score}
    names_th = {"D":"ความทนทาน","E1":"คุณภาพกำไร","E2":"การบริหาร","P":"อำนาจตั้งราคา","V":"ราคาเหมาะสม"}
    names_en = {"D":"Durability","E1":"Earnings Quality","E2":"Execution","P":"Pricing Power","V":"Valuation"}
    summaries_th = {
        "D": f"Gross Margin {gm*100:.1f}% | D/E {de:.1f} | Current Ratio {cr:.1f}",
        "E1":f"Net Margin {nm*100:.1f}% | ROE {roe*100:.1f}% | ROA {roa*100:.1f}%",
        "E2":f"Rev Growth {rev_g*100:.1f}% | Op Margin {om*100:.1f}%",
        "P": f"Gross Margin {gm*100:.1f}% | Op Margin {om*100:.1f}%",
        "V": f"P/E {pe:.1f}x | Fwd P/E {fwd_pe:.1f}x | P/B {pb:.1f}x",
    }
    summaries_en = {
        "D": f"Gross Margin {gm*100:.1f}% | D/E {de:.1f} | Current Ratio {cr:.1f}",
        "E1":f"Net Margin {nm*100:.1f}% | ROE {roe*100:.1f}% | ROA {roa*100:.1f}%",
        "E2":f"Rev Growth {rev_g*100:.1f}% | Op Margin {om*100:.1f}%",
        "P": f"Gross Margin {gm*100:.1f}% | Op Margin {om*100:.1f}%",
        "V": f"P/E {pe:.1f}x | Fwd P/E {fwd_pe:.1f}x | P/B {pb:.1f}x",
    }

    overall = clamp(sum(scores.values()) // 5)
    rec = "BUY" if overall >= 70 else "HOLD" if overall >= 45 else "AVOID"

    dimensions = {}
    for k, s in scores.items():
        lv = "green" if s>=70 else "yellow" if s>=40 else "red"
        dimensions[k] = {
            "name":    names_th[k] if TH else names_en[k],
            "score":   s, "level": lv,
            "summary": summaries_th[k] if TH else summaries_en[k],
            "analysis":"",
        }

    return {
        "dimensions": dimensions, "overall_score": overall,
        "overall_level": "green" if overall>=70 else "yellow" if overall>=40 else "red",
        "recommendation": rec, "summary":"", "risks":"", "catalysts":"", "auto": True,
    }


def run_ai(api_key, ticker, d, lang):
    genai.configure(api_key=api_key)
    try:
        avail=[m.name for m in genai.list_models()
               if "generateContent" in m.supported_generation_methods]
        pref=["models/gemini-1.5-pro","models/gemini-1.5-flash","models/gemini-pro"]
        mn=next((m for m in pref if m in avail), avail[0] if avail else None)
        if not mn: return {"error":"No model found"}
    except Exception as e: return {"error":str(e)}

    lang_rule = (
        "⚠️ ABSOLUTE RULE: Write EVERY text field ENTIRELY in Thai (ภาษาไทย). "
        "ALL analysis/summary/risks/catalysts = Thai only. Zero English sentences in text."
    ) if lang=="TH" else "Write all text in English only."

    prompt = f"""{lang_rule}
Analyze {ticker} ({d['name']}) D.E.E.P.V. Return ONLY valid JSON no backticks.
Data: ${d['price']} | {d['change']:.2f}% | MCap {fmt(d['cap'])}
P/E {d.get('pe','N/A')} | Fwd P/E {d.get('fwd_pe','N/A')} | PEG {d.get('peg','N/A')}
Rev {fmt(d.get('rev'))} | RevG {pct(d.get('rev_g'))} | GM {pct(d.get('gm'))} | OpM {pct(d.get('om'))} | NM {pct(d.get('nm'))}
ROE {pct(d.get('roe'))} | FCF {fmt(d.get('fcf'))} | D/E {d.get('de','N/A')} | Beta {d.get('beta','N/A')} | {d['sector']}

{{"dimensions":{{
  "D":{{"name":"{"ความทนทาน" if lang=="TH" else "Durability"}","score":75,"level":"green","summary":"1 sentence","analysis":"4-5 sentences"}},
  "E1":{{"name":"{"คุณภาพกำไร" if lang=="TH" else "Earnings Quality"}","score":75,"level":"green","summary":"1 sentence","analysis":"4-5 sentences"}},
  "E2":{{"name":"{"การบริหาร" if lang=="TH" else "Execution"}","score":75,"level":"green","summary":"1 sentence","analysis":"4-5 sentences"}},
  "P":{{"name":"{"อำนาจตั้งราคา" if lang=="TH" else "Pricing Power"}","score":75,"level":"green","summary":"1 sentence","analysis":"4-5 sentences"}},
  "V":{{"name":"{"ราคาเหมาะสม" if lang=="TH" else "Valuation"}","score":75,"level":"green","summary":"1 sentence","analysis":"4-5 sentences"}}
}},
"overall_score":75,"overall_level":"green","recommendation":"BUY",
"summary":"3-4 sentences","risks":"2-3 key risks","catalysts":"2-3 catalysts"}}
Rules: 70+=green, 40-69=yellow, 0-39=red. recommendation: BUY/HOLD/AVOID"""

    try:
        resp  = genai.GenerativeModel(mn).generate_content(prompt)
        clean = re.sub(r'^```json\s*|\s*```$','', resp.text.strip())
        return json.loads(clean)
    except json.JSONDecodeError: return {"error":"parse_failed","raw":resp.text}
    except Exception as e:       return {"error":str(e)}


# ─── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    cl, ct = st.columns(2)
    with cl:
        if st.button("🌐 TH/EN"):
            st.session_state.lang = "EN" if TH else "TH"; st.rerun()
    with ct:
        if st.button("☀️" if DARK else "🌙"):
            st.session_state.theme = "light" if DARK else "dark"; st.rerun()

    st.markdown("## 📊 D.E.E.P.V")
    st.caption("AI Stock Analyst" if not TH else "วิเคราะห์หุ้นด้วย AI")
    api_key = st.text_input("Google Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")
    st.caption("US: NVDA, AAPL  |  TH: PTT.BK, ADVANC.BK")
    t1 = st.text_input("Ticker 1", value="NVDA").upper().strip()
    t2 = st.text_input("Ticker 2", value="").upper().strip()
    t3 = st.text_input("Ticker 3", value="").upper().strip()
    btn = st.button("🚀 วิเคราะห์" if TH else "🚀 Analyze")
    st.divider()
    st.caption("D·Durability  E·Earnings\nE·Execution  P·Pricing  V·Valuation")


# ─── Run analysis ─────────────────────────────────────────────────────────────────
tickers_in = [x for x in [t1,t2,t3] if x]
if btn and tickers_in:
    st.session_state.results = {}
    for tk in tickers_in:
        with st.spinner(f"{'โหลด' if TH else 'Loading'} {tk}..."):
            data = get_stock(tk)
        if not data:
            st.error(f"❌ {'ไม่พบ' if TH else 'Not found'}: {tk}"); continue
        # คำนวณ auto score ทันทีโดยไม่ต้องใช้ API
        auto_result = calc_deepv_auto(data)
        ai = auto_result  # default = auto
        if api_key:
            with st.spinner(f"🧠 AI วิเคราะห์เชิงลึก {tk}..."):
                ai_full = run_ai(api_key, tk, data, LANG)
                if "dimensions" in ai_full:
                    ai = ai_full  # แทนที่ด้วย AI result ที่ละเอียดกว่า
        st.session_state.results[tk] = {"data": data, "ai": ai}

results = st.session_state.results


# ══ LANDING ══════════════════════════════════════════════════════════════════════
if not results:
    # Market dashboard at top
    st.markdown(f'<p style="font-size:.68rem;color:{muted};text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">{"🌍 ตลาดโลกวันนี้" if TH else "🌍 Global Markets Today"}</p>', unsafe_allow_html=True)
    idx_cols = st.columns(len(INDICES))
    for col, (name, sym) in zip(idx_cols, INDICES.items()):
        idata = get_index_data(sym)
        if idata:
            cc = "#34d399" if idata["change"]>=0 else "#f87171"
            ar = "▲" if idata["change"]>=0 else "▼"
            col.markdown(f"""<div class="idx-card">
              <div class="idx-name">{name}</div>
              <div class="idx-price">{idata['price']:,.0f}</div>
              <div style="font-size:.72rem;color:{cc}">{ar} {abs(idata['change']):.2f}%</div>
            </div>""", unsafe_allow_html=True)
        else:
            col.markdown(f'<div class="idx-card"><div class="idx-name">{name}</div><div class="idx-price">—</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""<div style="padding:28px 0 20px;text-align:center">
      <div style="font-size:.7rem;color:#4f7cff;text-transform:uppercase;letter-spacing:.15em;margin-bottom:10px">
        {'AI-Powered Fundamental Analysis' if not TH else 'วิเคราะห์หุ้นเชิงลึกด้วย AI'}
      </div>
      <h1 style="font-size:2.2rem;font-weight:800;color:{txt};margin:0 0 10px">
        D.E.E.P.V <span style="background:linear-gradient(135deg,#4f7cff,#7c4fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Analyst</span>
      </h1>
      <p style="color:{muted};font-size:.9rem;max-width:500px;margin:0 auto;line-height:1.7">
        {'วิเคราะห์หุ้นเชิงลึกด้วย AI ครอบคลุม 5 มิติ พร้อมคะแนน DEEPV Score, ข่าวล่าสุด และ Peer Comparison' if TH else
         'In-depth stock analysis across 5 dimensions with DEEPV Score, latest news, and peer comparison'}
      </p>
    </div>""", unsafe_allow_html=True)

    fc = st.columns(5)
    feats = [
        ("📐","DEEPV Score",    {"TH":"คะแนน 0-100 + Traffic Light","EN":"Score + Traffic Light"}),
        ("📰","ข่าวหุ้น",       {"TH":"ข่าวล่าสุด Real-time","EN":"Real-time News"}),
        ("👥","Peer Compare",  {"TH":"เปรียบเทียบหุ้นกลุ่มเดียวกัน","EN":"Compare sector peers"}),
        ("💼","Portfolio",     {"TH":"จำลอง Asset Allocation","EN":"Portfolio Simulator"}),
        ("🌍","ตลาดโลก",       {"TH":"ดัชนีตลาดทั่วโลก","EN":"Global Market Indices"}),
    ]
    for col,(icon,title,desc) in zip(fc,feats):
        col.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:10px;padding:14px;text-align:center;height:120px">
          <div style="font-size:1.4rem;margin-bottom:5px">{icon}</div>
          <div style="font-weight:600;color:{txt};margin-bottom:3px;font-size:.82rem">{title}</div>
          <div style="font-size:.7rem;color:{muted};line-height:1.4">{desc[LANG]}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    st.info("👈 " + ("ใส่ Ticker ใน Sidebar แล้วกด วิเคราะห์หุ้น" if TH else "Enter Ticker in Sidebar then click Analyze"))


# ══ RESULTS ══════════════════════════════════════════════════════════════════════
else:
    tr = list(results.keys())
    tlabels = [f"📈 {x}" for x in tr]
    if len(tr) > 1: tlabels.append("⚖️ เปรียบเทียบ" if TH else "⚖️ Compare")
    tlabels += ["💼 Portfolio", "🌍 ตลาดโลก" if TH else "🌍 Markets"]
    tabs = st.tabs(tlabels)

    # ── Per-ticker tabs ──────────────────────────────────────────────────────────
    for i, ticker in enumerate(tr):
        with tabs[i]:
            d  = results[ticker]["data"]
            ai = results[ticker]["ai"]
            cc = "#34d399" if d["change"]>=0 else "#f87171"
            ar = "▲" if d["change"]>=0 else "▼"

            # Header
            st.markdown(f"""<div style="margin-bottom:3px">
              <span style="font-size:1.35rem;font-weight:700;color:{txt}">{d['name']}</span>
              <span style="color:{muted};font-size:.78rem;margin-left:8px">{ticker}</span>
              <span style="color:{cc};font-size:.82rem;font-weight:600;margin-left:10px">{ar} {abs(d['change']):.2f}%</span>
            </div>
            <div style="font-size:.7rem;color:{muted};margin-bottom:12px">{d['sector']} · {d['industry']} · {d.get('country','')}</div>""",
            unsafe_allow_html=True)

            # Company expander
            if d.get("description"):
                with st.expander("📋 " + ("เกี่ยวกับบริษัท" if TH else "About Company"), expanded=False):
                    st.markdown(f'<p style="color:{muted};font-size:.82rem;line-height:1.65">{d["description"][:600]}...</p>',
                                unsafe_allow_html=True)
                    cc2 = st.columns(3)
                    if d.get("employees"): cc2[0].caption(f"👤 {d['employees']:,} employees")
                    if d.get("website"):
                        cc2[1].markdown(f'<a href="{d["website"]}" target="_blank" style="color:#4f7cff;font-size:.78rem">🌐 Website</a>',
                                        unsafe_allow_html=True)

            # ── COMPACT Metrics — 5 columns each row
            st.markdown(f'<span class="slbl">💰 {"ราคา" if TH else "Price"}</span>', unsafe_allow_html=True)
            mc = st.columns(5)
            mc[0].metric("Price",       f"${d['price']:,.2f}")
            mc[1].metric("Prev Close",  usd(d.get("prev_close")))
            mc[2].metric("Day High",    usd(d.get("day_high")))
            mc[3].metric("Day Low",     usd(d.get("day_low")))
            mc[4].metric("Market Cap",  fmt(d["cap"]))
            mc2 = st.columns(5)
            mc2[0].metric("52W High",   usd(d.get("52w_high")))
            mc2[1].metric("52W Low",    usd(d.get("52w_low")))
            mc2[2].metric("Target",     usd(d.get("target")))
            mc2[3].metric("Beta",       f"{d['beta']:.2f}" if d.get("beta") else "—")
            mc2[4].metric("Dividend",   pct(d.get("div")))

            st.markdown(f'<span class="slbl">📐 Valuation</span>', unsafe_allow_html=True)
            vc = st.columns(6)
            vc[0].metric("P/E",      xf(d.get("pe")))
            vc[1].metric("Fwd P/E",  xf(d.get("fwd_pe")))
            vc[2].metric("PEG",      xf(d.get("peg")))
            vc[3].metric("P/B",      xf(d.get("pb")))
            vc[4].metric("P/S",      xf(d.get("ps")))
            vc[5].metric("EV/EBITDA",xf(d.get("ev_eb")))

            st.markdown(f'<span class="slbl">📊 Financials</span>', unsafe_allow_html=True)
            fc2 = st.columns(6)
            fc2[0].metric("Revenue",     fmt(d.get("rev")))
            fc2[1].metric("Rev Growth",  pct(d.get("rev_g")))
            fc2[2].metric("Gross Margin",pct(d.get("gm")))
            fc2[3].metric("Op Margin",   pct(d.get("om")))
            fc2[4].metric("Net Margin",  pct(d.get("nm")))
            fc2[5].metric("FCF",         fmt(d.get("fcf")))

            st.markdown(f'<span class="slbl">🏦 Balance</span>', unsafe_allow_html=True)
            bc = st.columns(6)
            bc[0].metric("ROE",   pct(d.get("roe")))
            bc[1].metric("ROA",   pct(d.get("roa")))
            bc[2].metric("Cash",  fmt(d.get("cash")))
            bc[3].metric("Debt",  fmt(d.get("debt")))
            bc[4].metric("D/E",   f"{d['de']:.1f}" if d.get("de") else "—")
            bc[5].metric("Cur. Ratio", f"{d['cr']:.2f}" if d.get("cr") else "—")

            st.divider()

            # ── Peer Comparison
            peer_list = [x for x in SECTOR_PEERS.get(d['sector'],[]) if x != ticker][:4]
            if peer_list:
                st.markdown(f'<span class="slbl">👥 {"หุ้นเพื่อนบ้าน" if TH else "Sector Peers"} ({d["sector"]})</span>',
                            unsafe_allow_html=True)
                pcols = st.columns(len(peer_list))
                for pc, ptk in zip(pcols, peer_list):
                    pd_ = get_peer_quick(ptk)
                    if pd_:
                        pcc = "#34d399" if pd_["change"]>=0 else "#f87171"
                        par = "▲" if pd_["change"]>=0 else "▼"
                        pc.markdown(f"""<div class="peer-card">
                          <div class="peer-ticker">{ptk}</div>
                          <div class="peer-name">{pd_['name'][:18]}</div>
                          <div class="peer-price">${pd_['price']:,.2f}</div>
                          <div style="font-size:.72rem;color:{pcc};margin-bottom:4px">{par} {abs(pd_['change']):.2f}%</div>
                          <div style="font-size:.65rem;color:{muted}">MCap {fmt(pd_['cap'])}</div>
                          <div style="font-size:.65rem;color:{muted}">P/E {xf(pd_.get('pe'))}</div>
                        </div>""", unsafe_allow_html=True)

            st.divider()

            # ── Price chart
            st.markdown(f'<span class="slbl">📈 {"กราฟราคา" if TH else "Price Chart"}</span>', unsafe_allow_html=True)
            tp = st.radio("", ["1d","5d","1mo","3mo","1y","5y","max"],
                          index=4, horizontal=True, key=f"p_{ticker}")
            hist = get_hist(ticker, tp)
            if not hist.empty:
                up  = hist["Close"].iloc[-1] >= hist["Close"].iloc[0]
                clr = "#34d399" if up else "#f87171"
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist["Close"], mode="lines",
                    line=dict(color=clr, width=1.8), fill="tozeroy",
                    fillcolor="rgba(52,211,153,.07)" if up else "rgba(248,113,113,.07)",
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>",
                ))
                lo = plot_base(250); lo["yaxis"]["tickprefix"] = "$"
                fig.update_layout(**lo); st.plotly_chart(fig, use_container_width=True)

            # ── Historical Financials
            fin = get_fin(ticker)
            if fin is not None and not fin.empty:
                try:
                    ft = fin.T.sort_index()
                    fig_f = go.Figure()
                    for col,(c_,nm) in [("Total Revenue",("#4f7cff","Revenue $B")),
                                        ("Net Income",("#34d399","Net Income $B")),
                                        ("Gross Profit",("#7c4fff","Gross Profit $B"))]:
                        if col in ft.columns:
                            fig_f.add_trace(go.Bar(x=ft.index.year, y=ft[col]/1e9,
                                name=nm, marker_color=c_, opacity=.85))
                    lo2 = plot_base(220); lo2["barmode"]="group"; lo2["yaxis"]["ticksuffix"]="B"
                    fig_f.update_layout(**lo2); st.plotly_chart(fig_f, use_container_width=True)
                except: pass

            st.divider()

            # ── News  ← FIXED
            st.markdown(f'<span class="slbl">📰 {"ข่าวล่าสุด" if TH else "Latest News"}</span>',
                        unsafe_allow_html=True)
            news = get_news(ticker)
            if news:
                for n in news:
                    safe_title = n["title"].replace('"',"'")
                    st.markdown(f"""<div class="news-item">
                      <a href="{n['link']}" target="_blank">{n['title']}</a>
                      <div class="news-meta">{n['publisher']} · {n['date']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("ไม่พบข่าว" if TH else "No news available")

            # ── DEEPV Analysis (แสดงเสมอ — auto หรือ AI)
            if ai and "dimensions" in ai:
                st.divider()
                overall = ai.get("overall_score",0)
                rec     = ai.get("recommendation","—")
                is_auto = ai.get("auto", False)
                rc  = {"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5")
                oc  = sc(overall)
                mode_badge = (
                    f'<span style="background:#2d313d;color:{muted};border:1px solid {border};border-radius:4px;padding:2px 7px;font-size:.6rem">⚡ Auto Score</span>'
                    if is_auto else
                    f'<span style="background:#4f7cff22;color:#4f7cff;border:1px solid #4f7cff44;border-radius:4px;padding:2px 7px;font-size:.6rem">🧠 AI Analysis</span>'
                )

                st.markdown(f"""<div style="background:{bg2};border-radius:12px;padding:16px;
                  margin-bottom:14px;display:flex;align-items:center;gap:18px;border:1px solid {border}">
                  <div style="text-align:center;min-width:58px">
                    <div style="font-size:1.9rem;font-weight:800;color:{oc}">{overall}</div>
                    <div style="font-size:.56rem;color:{muted};text-transform:uppercase">DEEPV Score</div>
                    <div style="margin-top:4px">{mode_badge}</div>
                  </div>
                  <div style="flex:1">
                    <div style="background:{border};border-radius:999px;height:6px;overflow:hidden">
                      <div style="background:linear-gradient(90deg,#f87171,#fbbf24,#34d399);width:100%;height:100%;opacity:.2"></div>
                    </div>
                    <div style="background:transparent;border-radius:999px;height:6px;overflow:hidden;margin-top:-6px">
                      <div style="background:{oc};width:{overall}%;height:100%;border-radius:999px"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:3px">
                      <span style="font-size:.56rem;color:#f87171">{"เสี่ยงสูง 0-39" if TH else "High 0-39"}</span>
                      <span style="font-size:.56rem;color:#fbbf24">{"เสี่ยงกลาง 40-69" if TH else "Mid 40-69"}</span>
                      <span style="font-size:.56rem;color:#34d399">{"เสี่ยงต่ำ 70-100" if TH else "Low 70-100"}</span>
                    </div>
                  </div>
                  <div style="text-align:center;min-width:72px">
                    <div style="font-size:1.2rem;font-weight:800;color:{rc};background:{rc}18;
                         border:1px solid {rc}44;border-radius:8px;padding:5px 10px">{rec}</div>
                    <div style="font-size:.56rem;color:{muted};margin-top:3px">Signal</div>
                  </div>
                </div>""", unsafe_allow_html=True)

                for key, dim in ai.get("dimensions",{}).items():
                    s=dim.get("score",0); lc=sc(s); lbl=ll(dim.get("level","yellow"))
                    analysis_text = dim.get('analysis','')
                    if not analysis_text:
                        # Auto mode — แสดง summary แทน
                        analysis_text = dim.get('summary','')
                    st.markdown(f"""<div class="dcard" style="border-left:3px solid {lc}">
                      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                        <span style="font-size:1.3rem;font-weight:800;color:{lc};min-width:32px">{key}</span>
                        <div style="flex:1">
                          <div style="font-size:.88rem;font-weight:600;color:{txt}">{dim.get('name','')}</div>
                          <div style="font-size:.72rem;color:{muted}">{dim.get('summary','')}</div>
                        </div>
                        <div style="text-align:right;flex-shrink:0">
                          <div style="font-size:1.1rem;font-weight:700;color:{lc}">{s}<span style="font-size:.65rem;color:{muted}">/100</span></div>
                          <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;
                                border-radius:4px;padding:1px 5px;font-size:.65rem">{lbl}</span>
                        </div>
                      </div>
                      <div style="height:3px;background:{border};border-radius:999px;margin-bottom:9px;overflow:hidden">
                        <div style="background:{lc};width:{s}%;height:100%;border-radius:999px"></div></div>
                      {"" if not analysis_text else f'<p style="color:{muted};margin:0;font-size:.83rem;line-height:1.65">{analysis_text}</p>'}
                    </div>""", unsafe_allow_html=True)

                # ── ถ้าเป็น auto mode แสดง banner ให้ใส่ API key เพื่อ upgrade
                if is_auto:
                    st.markdown(f"""<div style="background:#4f7cff12;border:1px solid #4f7cff33;
                      border-radius:10px;padding:12px 16px;margin:8px 0;display:flex;align-items:center;gap:12px">
                      <span style="font-size:1.2rem">🧠</span>
                      <div>
                        <div style="font-size:.82rem;font-weight:600;color:#4f7cff">
                          {"อยากได้การวิเคราะห์เชิงลึกภาษาไทยจาก AI?" if TH else "Want deeper AI analysis in Thai?"}
                        </div>
                        <div style="font-size:.72rem;color:{muted}">
                          {"ใส่ Google Gemini API Key ใน Sidebar เพื่อดูการวิเคราะห์ D.E.E.P.V แบบละเอียด พร้อมปัจจัยบวก ความเสี่ยง และสรุปภาพรวม (ฟรี)" if TH else "Add Gemini API Key in Sidebar for detailed Thai AI analysis with catalysts, risks and summary (Free)"}
                        </div>
                      </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    cl2, cr2 = st.columns(2)
                    with cl2:
                        st.markdown(f"""<div style="background:{bg2};border-radius:10px;padding:13px;border-left:3px solid #34d399;border:1px solid {border}">
                          <div style="font-size:.6rem;color:{muted};text-transform:uppercase;margin-bottom:6px">{"✅ ปัจจัยบวก" if TH else "✅ Catalysts"}</div>
                          <p style="color:{muted};margin:0;line-height:1.65;font-size:.82rem">{ai.get('catalysts','—')}</p></div>""",
                          unsafe_allow_html=True)
                    with cr2:
                        st.markdown(f"""<div style="background:{bg2};border-radius:10px;padding:13px;border-left:3px solid #f87171;border:1px solid {border}">
                          <div style="font-size:.6rem;color:{muted};text-transform:uppercase;margin-bottom:6px">{"⚠️ ความเสี่ยง" if TH else "⚠️ Risks"}</div>
                          <p style="color:{muted};margin:0;line-height:1.65;font-size:.82rem">{ai.get('risks','—')}</p></div>""",
                          unsafe_allow_html=True)
                    st.markdown(f"""<div style="background:{bg2};border-radius:10px;padding:13px;
                      border-left:3px solid {rc};border:1px solid {border};margin-top:8px">
                      <div style="font-size:.6rem;color:{muted};text-transform:uppercase;margin-bottom:6px">{"🧠 สรุปภาพรวม" if TH else "🧠 Summary"}</div>
                      <p style="color:{muted};margin:0;line-height:1.65;font-size:.85rem">{ai.get('summary','')}</p></div>""",
                      unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # ── Build full HTML report
                dim_rows = ""
                for key, dim in ai.get("dimensions",{}).items():
                    s_   = dim.get("score",0)
                    lc_  = "#34d399" if s_>=70 else "#fbbf24" if s_>=40 else "#f87171"
                    lbl_ = ("🟢 เสี่ยงต่ำ" if s_>=70 else "🟡 เสี่ยงกลาง" if s_>=40 else "🔴 เสี่ยงสูง") if TH else ("🟢 Low Risk" if s_>=70 else "🟡 Med Risk" if s_>=40 else "🔴 High Risk")
                    dim_rows += f"""
                    <div style="border-left:4px solid {lc_};background:#1c1f26;border-radius:10px;padding:16px;margin-bottom:12px">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <div>
                          <span style="font-size:1.2rem;font-weight:800;color:{lc_};margin-right:10px">{key}</span>
                          <span style="font-size:1rem;font-weight:600;color:#e8eaf0">{dim.get('name','')}</span>
                        </div>
                        <div style="text-align:right">
                          <span style="font-size:1.3rem;font-weight:700;color:{lc_}">{s_}/100</span>
                          <span style="margin-left:8px;background:{lc_}22;color:{lc_};border:1px solid {lc_}55;border-radius:5px;padding:2px 8px;font-size:.75rem">{lbl_}</span>
                        </div>
                      </div>
                      <div style="background:#2d313d;border-radius:999px;height:5px;margin-bottom:10px;overflow:hidden">
                        <div style="background:{lc_};width:{s_}%;height:100%;border-radius:999px"></div>
                      </div>
                      <p style="color:#8b92a5;margin:0 0 5px;font-size:.8rem;font-style:italic">{dim.get('summary','')}</p>
                      <p style="color:#c5c9d6;margin:0;font-size:.88rem;line-height:1.7">{dim.get('analysis','')}</p>
                    </div>"""

                rpt = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DEEPV Report: {ticker}</title>
<style>
  body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#0e1117;color:#e8eaf0;margin:0;padding:32px;max-width:900px;margin:0 auto}}
  .grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}}
  .card{{background:#1c1f26;border-radius:8px;padding:12px}}
  .clabel{{font-size:.65rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.04em}}
  .cvalue{{font-size:1rem;font-weight:700;color:#e8eaf0;margin-top:2px}}
  @media(max-width:600px){{.grid3{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}}}
  @media print{{body{{background:#fff;color:#000}}}}
</style>
</head>
<body>

<div style="border-bottom:1px solid #2d313d;padding-bottom:16px;margin-bottom:20px">
  <div style="font-size:.7rem;color:#8b92a5;margin-bottom:4px">D.E.E.P.V AI Analyst · {datetime.now().strftime("%d %b %Y %H:%M")}</div>
  <h1 style="margin:0 0 6px;font-size:1.6rem">{d.get('name',ticker)} <span style="color:#8b92a5;font-size:.9rem">({ticker})</span></h1>
  <div style="font-size:.8rem;color:#8b92a5;margin-bottom:12px">{d.get('sector','—')} · {d.get('industry','—')} · {d.get('country','—')}</div>
  <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
    <span style="font-size:1.5rem;font-weight:700">${d.get('price',0):,.2f}</span>
    <div style="text-align:center">
      <div style="font-size:2.4rem;font-weight:800;color:{oc}">{overall}</div>
      <div style="font-size:.6rem;color:#8b92a5;text-transform:uppercase">DEEPV Score</div>
    </div>
    <div style="text-align:center">
      <div style="font-size:1.4rem;font-weight:800;color:{rc};background:{rc}18;border:1px solid {rc}44;border-radius:8px;padding:5px 14px">{rec}</div>
      <div style="font-size:.6rem;color:#8b92a5;margin-top:3px">Signal</div>
    </div>
  </div>
</div>

<div style="margin-bottom:6px;font-size:.62rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em">Key Metrics</div>
<div class="grid3">
  <div class="card"><div class="clabel">Market Cap</div><div class="cvalue">{fmt(d.get('cap',0))}</div></div>
  <div class="card"><div class="clabel">P/E (Trail)</div><div class="cvalue">{xf(d.get('pe'))}</div></div>
  <div class="card"><div class="clabel">Fwd P/E</div><div class="cvalue">{xf(d.get('fwd_pe'))}</div></div>
  <div class="card"><div class="clabel">Revenue</div><div class="cvalue">{fmt(d.get('rev'))}</div></div>
  <div class="card"><div class="clabel">Gross Margin</div><div class="cvalue">{pct(d.get('gm'))}</div></div>
  <div class="card"><div class="clabel">ROE</div><div class="cvalue">{pct(d.get('roe'))}</div></div>
  <div class="card"><div class="clabel">Net Margin</div><div class="cvalue">{pct(d.get('nm'))}</div></div>
  <div class="card"><div class="clabel">FCF</div><div class="cvalue">{fmt(d.get('fcf'))}</div></div>
  <div class="card"><div class="clabel">Beta</div><div class="cvalue">{f"{d['beta']:.2f}" if d.get('beta') else '—'}</div></div>
</div>

<div style="margin:16px 0 8px;font-size:.62rem;color:#8b92a5;text-transform:uppercase;letter-spacing:.1em">D.E.E.P.V Analysis</div>
{dim_rows}

<div class="grid2" style="margin-top:12px">
  <div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid #34d399">
    <div style="font-size:.62rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">{"✅ ปัจจัยบวก" if TH else "✅ Catalysts"}</div>
    <p style="margin:0;color:#c5c9d6;font-size:.85rem;line-height:1.7">{ai.get('catalysts','—')}</p>
  </div>
  <div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid #f87171">
    <div style="font-size:.62rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">{"⚠️ ความเสี่ยง" if TH else "⚠️ Risks"}</div>
    <p style="margin:0;color:#c5c9d6;font-size:.85rem;line-height:1.7">{ai.get('risks','—')}</p>
  </div>
</div>

<div style="background:#1c1f26;border-radius:10px;padding:14px;border-left:3px solid {rc};margin-top:10px">
  <div style="font-size:.62rem;color:#8b92a5;text-transform:uppercase;margin-bottom:6px">{"🧠 สรุปภาพรวม" if TH else "🧠 Summary"}</div>
  <p style="margin:0;color:#c5c9d6;font-size:.88rem;line-height:1.7">{ai.get('summary','—')}</p>
</div>

</body></html>"""
                st.download_button("📄 " + ("ดาวน์โหลด Report" if TH else "Download Report"),
                    data=rpt.encode("utf-8"),
                    file_name=f"DEEPV_{ticker}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html", key=f"dl_{ticker}")
                st.balloons()

            elif ai and "error" in ai: st.error(f"❌ {ai['error']}")


    # ── Compare ──────────────────────────────────────────────────────────────────
    if len(tr) > 1:
        with tabs[len(tr)]:
            st.markdown(f"### {'⚖️ เปรียบเทียบ' if TH else '⚖️ Compare'}")
            has_ai = {x:r["ai"] for x,r in results.items() if r["ai"] and "dimensions" in r["ai"]}
            pal    = ["#4f7cff","#34d399","#fbbf24"]
            if has_ai:
                dk = ["D","E1","E2","P","V"]
                dn = ["Durability","Earnings","Execution","Pricing","Valuation"]
                fig = go.Figure()
                for idx,(x,aai) in enumerate(has_ai.items()):
                    fig.add_trace(go.Bar(name=x, x=dn,
                        y=[aai["dimensions"].get(k,{}).get("score",0) for k in dk],
                        marker_color=pal[idx%len(pal)]))
                lo3 = plot_base(300); lo3["barmode"]="group"; lo3["yaxis"]["range"]=[0,100]
                fig.update_layout(**lo3); st.plotly_chart(fig, use_container_width=True)
                td = {}
                for x,aai in has_ai.items():
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

            cp = st.radio("", ["1mo","3mo","1y","5y"], index=2, horizontal=True, key="cmp")
            fig2 = go.Figure()
            for idx,x in enumerate(tr):
                h = get_hist(x, cp)
                if not h.empty:
                    norm = (h["Close"]/h["Close"].iloc[0])*100
                    fig2.add_trace(go.Scatter(x=h.index, y=norm, name=x,
                        line=dict(color=pal[idx%len(pal)], width=2),
                        hovertemplate=f"<b>{x}</b>: %{{y:.1f}}%<extra></extra>"))
            lo4 = plot_base(260); lo4["yaxis"]["ticksuffix"] = "%"
            fig2.update_layout(**lo4); st.plotly_chart(fig2, use_container_width=True)


    # ── Portfolio ─────────────────────────────────────────────────────────────────
    with tabs[-2]:
        st.markdown("### 💼 Portfolio")
        pa_, pb_, pc_ = st.columns([2,1,1])
        with pa_: pt_ = st.text_input("Ticker", placeholder="NVDA, PTT.BK").upper().strip()
        with pb_: pal_ = st.number_input("%", min_value=1, max_value=100, value=25, step=5)
        with pc_:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add"):
                if pt_:
                    if pt_ in [p["ticker"] for p in st.session_state.portfolio]:
                        st.warning("มีแล้ว" if TH else "Already added")
                    else:
                        with st.spinner(f"Loading {pt_}..."): pd__ = get_stock(pt_)
                        if pd__:
                            st.session_state.portfolio.append({
                                "ticker":pt_, "name":pd__["name"], "alloc":pal_,
                                "price":pd__["price"], "change":pd__["change"],
                                "sector":pd__["sector"], "beta":pd__.get("beta")})
                            st.rerun()
                        else: st.error(f"❌ {pt_}")

        if results and st.button("📥 Import analyzed"):
            ex = [p["ticker"] for p in st.session_state.portfolio]
            for x,r in results.items():
                if x not in ex and r["data"]:
                    d_ = r["data"]; ea = max(1, round(100/max(1,len(results)+len(ex))))
                    st.session_state.portfolio.append({
                        "ticker":x, "name":d_["name"], "alloc":ea,
                        "price":d_["price"], "change":d_["change"],
                        "sector":d_["sector"], "beta":d_.get("beta")})
            st.rerun()

        port = st.session_state.portfolio
        if not port:
            st.markdown(f'<div style="text-align:center;padding:40px 0;color:{muted}"><div style="font-size:2rem">💼</div><p>{"ยังไม่มีหุ้นในพอร์ต" if TH else "Portfolio is empty"}</p></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown("---"); total = 0; upd = []
            for idx, p in enumerate(port):
                co1,co2,co3,co4 = st.columns([3,2,1,1])
                cc_ = "#34d399" if p["change"]>=0 else "#f87171"
                with co1:
                    st.markdown(f'<div style="padding:6px 0"><span style="font-weight:600;color:{txt}">{p["ticker"]}</span> '
                                f'<span style="color:{muted};font-size:.75rem">{p["name"][:20]}</span> '
                                f'<span style="color:{cc_};font-size:.75rem">{"▲" if p["change"]>=0 else "▼"}{abs(p["change"]):.1f}%</span></div>',
                                unsafe_allow_html=True)
                with co2:
                    na = st.slider("",1,100,p["alloc"],key=f"sl_{idx}",label_visibility="collapsed"); p["alloc"]=na
                with co3:
                    st.markdown(f'<div style="padding-top:10px;font-weight:700;color:#4f7cff">{na}%</div>', unsafe_allow_html=True)
                with co4:
                    if st.button("🗑️", key=f"del_{idx}"): st.session_state.portfolio.pop(idx); st.rerun()
                total += na; upd.append(p)
            st.session_state.portfolio = upd
            ac = "#34d399" if total==100 else "#fbbf24" if total<100 else "#f87171"
            st.markdown(f'<div style="text-align:right;font-size:.78rem;color:{ac};margin-bottom:10px">Total: <strong>{total}%</strong> {"✅" if total==100 else "⚠️"}</div>',
                        unsafe_allow_html=True)
            st.markdown("---")
            pp1, pp2 = st.columns(2)
            with pp1:
                fig_pie = go.Figure(go.Pie(
                    labels=[p["ticker"] for p in port], values=[p["alloc"] for p in port],
                    hole=.5,
                    marker=dict(colors=["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa","#fb923c"][:len(port)]),
                    textinfo="label+percent", textfont=dict(color=txt,size=11)))
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=230,
                    showlegend=False, margin=dict(l=0,r=0,t=8,b=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            with pp2:
                sa = {}
                for p in port: sa[p["sector"]] = sa.get(p["sector"],0) + p["alloc"]
                fig_s = go.Figure(go.Bar(x=list(sa.values()), y=list(sa.keys()),
                    orientation="h", marker_color="#7c4fff",
                    text=[f"{v}%" for v in sa.values()], textposition="outside",
                    textfont=dict(color=muted,size=10)))
                lo5 = plot_base(230); lo5["xaxis"]["ticksuffix"]="%"; lo5.pop("hovermode",None)
                fig_s.update_layout(**lo5); st.plotly_chart(fig_s, use_container_width=True)

            pp_r = st.radio("", ["1mo","3mo","1y","5y"], index=2, horizontal=True, key="port_p")
            fig_pf = go.Figure(); pr = None
            cls_ = ["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa"]
            for idx, p in enumerate(port):
                h = get_hist(p["ticker"], pp_r)
                if not h.empty:
                    norm = (h["Close"]/h["Close"].iloc[0])*100
                    pr = (norm*(p["alloc"]/100)) if pr is None else pr+norm*(p["alloc"]/100)
                    fig_pf.add_trace(go.Scatter(x=h.index, y=norm, name=p["ticker"],
                        line=dict(color=cls_[idx%len(cls_)],width=1.4,dash="dot"), opacity=.5,
                        hovertemplate=f"<b>{p['ticker']}</b>: %{{y:.1f}}%<extra></extra>"))
            if pr is not None:
                fig_pf.add_trace(go.Scatter(x=pr.index, y=pr, name="📦 Portfolio",
                    line=dict(color="#ffffff" if DARK else "#111827", width=2.5),
                    hovertemplate="<b>Portfolio</b>: %{y:.1f}%<extra></extra>"))
            lo6 = plot_base(260); lo6["yaxis"]["ticksuffix"] = "%"
            fig_pf.update_layout(**lo6); st.plotly_chart(fig_pf, use_container_width=True)

            m1,m2,m3 = st.columns(3)
            m1.metric("Holdings", f"{len(port)}")
            m2.metric("Wtd Beta", f"{sum([(p.get('beta') or 1)*p['alloc']/100 for p in port]):.2f}")
            m3.metric("Today",    f"{sum([p['change']*p['alloc']/100 for p in port]):+.2f}%")
            if st.button("🗑️ Clear All"): st.session_state.portfolio=[]; st.rerun()


    # ── Markets Tab ───────────────────────────────────────────────────────────────
    with tabs[-1]:
        st.markdown(f"### {'🌍 สถานะตลาดโลก' if TH else '🌍 Global Markets'}")
        idx_cols = st.columns(4)
        for idx,(name,sym) in enumerate(INDICES.items()):
            idata = get_index_data(sym)
            col   = idx_cols[idx%4]
            if idata:
                cc = "#34d399" if idata["change"]>=0 else "#f87171"
                ar = "▲" if idata["change"]>=0 else "▼"
                col.markdown(f"""<div class="idx-card" style="margin-bottom:10px">
                  <div class="idx-name">{name}</div>
                  <div class="idx-price">{idata['price']:,.2f}</div>
                  <div style="font-size:.75rem;color:{cc}">{ar} {abs(idata['change']):.2f}%</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"#### {'เปรียบเทียบ Index ย้อนหลัง' if TH else 'Index Comparison'}")
        idx_sel = st.multiselect(
            "เลือก Index" if TH else "Select Indices",
            list(INDICES.keys()),
            default=["S&P 500","NASDAQ","SET (TH)"])
        idx_p = st.radio("", ["1mo","3mo","1y","5y"], index=2, horizontal=True, key="idx_p")
        fig_idx = go.Figure()
        pal_i = ["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa","#fb923c","#38bdf8","#f472b6"]
        for ii, name in enumerate(idx_sel):
            sym = INDICES.get(name)
            if sym:
                h = get_hist(sym, idx_p)
                if not h.empty:
                    norm = (h["Close"]/h["Close"].iloc[0])*100
                    fig_idx.add_trace(go.Scatter(x=h.index, y=norm, name=name,
                        line=dict(color=pal_i[ii%len(pal_i)],width=2),
                        hovertemplate=f"<b>{name}</b>: %{{y:.1f}}%<extra></extra>"))
        lo7 = plot_base(360); lo7["yaxis"]["ticksuffix"] = "%"
        fig_idx.update_layout(**lo7); st.plotly_chart(fig_idx, use_container_width=True)
