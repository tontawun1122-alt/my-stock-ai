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
    bg="#0e1117";bg2="#1c1f26";bg3="#13161e";border="#2d313d"
    text="#e8eaf0";muted="#8b92a5";plot_bg="#13161e";grid="#1c2030"
else:
    bg="#f0f2f6";bg2="#ffffff";bg3="#e8eaf0";border="#d1d5db"
    text="#111827";muted="#6b7280";plot_bg="#f8fafc";grid="#e5e7eb"

st.markdown(f"""<style>
.stApp{{background:{bg}}}
[data-testid="metric-container"]{{background:{bg2};border:1px solid {border};border-radius:8px;padding:10px 14px}}
[data-testid="metric-container"] label{{font-size:.65rem!important;color:{muted}!important;text-transform:uppercase;letter-spacing:.04em}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{font-size:1rem!important;font-weight:700!important;color:{text}!important}}
[data-testid="stSidebar"]{{background:{bg3};border-right:1px solid {border}}}
.stButton>button{{background:linear-gradient(135deg,#4f7cff,#7c4fff);color:white;border:none;border-radius:8px;padding:8px 16px;font-weight:600;width:100%}}
hr{{border-color:{border}!important}}
.dcard{{background:{bg2};border:1px solid {border};border-radius:12px;padding:18px;margin-bottom:10px}}
.slbl{{font-size:.62rem;color:{muted};text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;margin-top:10px}}
.news-card{{background:{bg2};border:1px solid {border};border-radius:10px;padding:14px;margin-bottom:8px}}
.peer-card{{background:{bg2};border:1px solid {border};border-radius:10px;padding:12px;text-align:center}}
p,span,div,h1,h2,h3{{color:{text}}}
#MainMenu,footer{{visibility:hidden}}
.block-container{{padding-top:1.5rem;padding-bottom:2rem}}
</style>""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────────
def fmt(v):
    if not v or v==0: return "—"
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
    m={"green":("🟢 เสี่ยงต่ำ","🟢 Low Risk"),"yellow":("🟡 เสี่ยงกลาง","🟡 Med Risk"),"red":("🔴 เสี่ยงสูง","🔴 High Risk")}
    return m.get(l,("—","—"))[0 if TH else 1]
def pct(v): return f"{v*100:.1f}%" if v else "—"
def usd(v): return f"${v:,.2f}" if v else "—"
def xf(v):  return f"{v:.1f}x" if v else "—"

def plot_base(h=280):
    return dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor=plot_bg,
                margin=dict(l=0,r=0,t=16,b=0),height=h,hovermode="x unified",
                xaxis=dict(showgrid=False,tickfont=dict(color=muted,size=10)),
                yaxis=dict(gridcolor=grid,tickfont=dict(color=muted,size=10)),
                legend=dict(font=dict(color=muted,size=10),bgcolor="rgba(0,0,0,0)"),
                font=dict(color=text))


@st.cache_data(ttl=300,show_spinner=False)
def get_stock(ticker):
    try:
        info=yf.Ticker(ticker).info
        if not info or (not info.get("currentPrice") and not info.get("regularMarketPrice")): return None
        return {"name":info.get("longName") or info.get("shortName") or ticker,
                "ticker":ticker,"change":cpct(info),
                "sector":info.get("sector","—"),"industry":info.get("industry","—"),
                "website":info.get("website",""),"country":info.get("country","—"),
                "description":info.get("longBusinessSummary",""),
                "employees":info.get("fullTimeEmployees"),
                "price":info.get("currentPrice") or info.get("regularMarketPrice",0),
                "prev_close":info.get("previousClose"),"day_high":info.get("dayHigh"),
                "day_low":info.get("dayLow"),"52w_high":info.get("fiftyTwoWeekHigh"),
                "52w_low":info.get("fiftyTwoWeekLow"),"target":info.get("targetMeanPrice"),
                "cap":info.get("marketCap",0),"pe":info.get("trailingPE"),
                "fwd_pe":info.get("forwardPE"),"peg":info.get("pegRatio"),
                "pb":info.get("priceToBook"),"ps":info.get("priceToSalesTrailing12Months"),
                "ev_eb":info.get("enterpriseToEbitda"),"eps":info.get("trailingEps"),
                "fwd_eps":info.get("forwardEps"),"rev":info.get("totalRevenue"),
                "rev_g":info.get("revenueGrowth"),"gm":info.get("grossMargins"),
                "om":info.get("operatingMargins"),"nm":info.get("profitMargins"),
                "roe":info.get("returnOnEquity"),"roa":info.get("returnOnAssets"),
                "fcf":info.get("freeCashflow"),"cash":info.get("totalCash"),
                "debt":info.get("totalDebt"),"de":info.get("debtToEquity"),
                "cr":info.get("currentRatio"),"div":info.get("dividendYield"),
                "beta":info.get("beta"),"short":info.get("shortRatio"),
                "ar":info.get("recommendationKey","").upper(),
                "analyst_buy":info.get("numberOfAnalystOpinions",0),
                "rec_mean":info.get("recommendationMean"),
                "peers":[] }
    except Exception as e:
        st.error(f"Error: {e}"); return None


@st.cache_data(ttl=300,show_spinner=False)
def get_hist(ticker,period): return yf.Ticker(ticker).history(period=period)

@st.cache_data(ttl=3600,show_spinner=False)
def get_fin(ticker):
    try: return yf.Ticker(ticker).financials
    except: return None

@st.cache_data(ttl=600,show_spinner=False)
def get_news(ticker):
    try:
        news=yf.Ticker(ticker).news or []
        return news[:6]
    except: return []

@st.cache_data(ttl=300,show_spinner=False)
def get_peers(ticker,sector):
    """ดึงหุ้นในกลุ่มเดียวกัน โดยใช้ sector ETF หรือ list ที่กำหนดไว้"""
    sector_map={
        "Technology":       ["AAPL","MSFT","NVDA","GOOG","META","AVGO","TSM","AMD","INTC","ORCL"],
        "Consumer Cyclical":["AMZN","TSLA","HD","NKE","MCD","SBUX","TGT","LOW","F","GM"],
        "Healthcare":       ["JNJ","UNH","PFE","ABBV","MRK","LLY","TMO","ABT","BMY","GILD"],
        "Financials":       ["JPM","BAC","WFC","GS","MS","C","BLK","AXP","USB","PNC"],
        "Communication Services":["GOOG","META","NFLX","DIS","T","VZ","CMCSA","TMUS","SNAP","SPOT"],
        "Energy":           ["XOM","CVX","COP","SLB","EOG","PXD","MPC","VLO","OXY","BKR"],
        "Industrials":      ["HON","UPS","CAT","DE","LMT","RTX","GE","MMM","FDX","BA"],
        "Consumer Defensive":["WMT","PG","KO","PEP","COST","PM","MO","CL","GIS","K"],
        "Real Estate":      ["AMT","PLD","CCI","EQIX","PSA","O","WELL","DLR","SPG","AVB"],
        "Utilities":        ["NEE","DUK","SO","D","EXC","AEP","SRE","PCG","ED","XEL"],
        "Basic Materials":  ["LIN","APD","ECL","SHW","NEM","FCX","NUE","CF","MOS","ALB"],
    }
    candidates=sector_map.get(sector,[])
    return [t for t in candidates if t!=ticker][:4]

@st.cache_data(ttl=300,show_spinner=False)
def get_peer_data(ticker):
    try:
        info=yf.Ticker(ticker).info
        if not info: return None
        c=info.get("currentPrice") or info.get("regularMarketPrice") or 0
        p=info.get("previousClose") or 0
        chg=((c-p)/p*100) if p else 0
        return {"ticker":ticker,"name":info.get("shortName") or ticker,
                "price":c,"change":chg,"cap":info.get("marketCap",0),
                "pe":info.get("trailingPE"),"gm":info.get("grossMargins")}
    except: return None

# Market indices
INDICES={
    "S&P 500":"^GSPC","NASDAQ":"^IXIC","Dow Jones":"^DJI",
    "SET (TH)":"^SET.BK","Nikkei 225":"^N225","Hang Seng":"^HSI",
    "FTSE 100":"^FTSE","DAX":"^GDAXI",
}

@st.cache_data(ttl=300,show_spinner=False)
def get_index(symbol):
    try:
        info=yf.Ticker(symbol).fast_info
        price=getattr(info,"last_price",None) or getattr(info,"regularMarketPrice",None)
        prev=getattr(info,"previous_close",None)
        if price and prev:
            chg=((price-prev)/prev)*100
            return {"price":price,"change":chg}
        return None
    except: return None


def run_ai(api_key,ticker,d,lang):
    genai.configure(api_key=api_key)
    try:
        avail=[m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        pref=["models/gemini-1.5-pro","models/gemini-1.5-flash","models/gemini-pro"]
        mn=next((m for m in pref if m in avail),avail[0] if avail else None)
        if not mn: return {"error":"No model found"}
    except Exception as e: return {"error":str(e)}

    lang_rule=("⚠️ ABSOLUTE RULE: Write ALL text fields in Thai (ภาษาไทย) ONLY. Zero English sentences in analysis/summary/risks/catalysts."
               if lang=="TH" else "Write all text fields in English only.")

    prompt=f"""{lang_rule}
Analyze {ticker} ({d['name']}) using D.E.E.P.V. Return ONLY valid JSON, no backticks.
Data: ${d['price']} | {d['change']:.2f}% | MCap {fmt(d['cap'])} | P/E {d.get('pe','N/A')} | Fwd P/E {d.get('fwd_pe','N/A')}
Rev {fmt(d.get('rev'))} | RevGrowth {pct(d.get('rev_g'))} | GM {pct(d.get('gm'))} | OpM {pct(d.get('om'))} | NM {pct(d.get('nm'))}
ROE {pct(d.get('roe'))} | FCF {fmt(d.get('fcf'))} | D/E {d.get('de','N/A')} | Beta {d.get('beta','N/A')} | {d['sector']}
{{"dimensions":{{"D":{{"name":"{"ความทนทาน" if lang=="TH" else "Durability"}","score":75,"level":"green","summary":"1 sentence","analysis":"3-5 sentences"}},"E1":{{"name":"{"คุณภาพกำไร" if lang=="TH" else "Earnings Quality"}","score":75,"level":"green","summary":"1 sentence","analysis":"3-5 sentences"}},"E2":{{"name":"{"การบริหาร" if lang=="TH" else "Execution"}","score":75,"level":"green","summary":"1 sentence","analysis":"3-5 sentences"}},"P":{{"name":"{"อำนาจตั้งราคา" if lang=="TH" else "Pricing Power"}","score":75,"level":"green","summary":"1 sentence","analysis":"3-5 sentences"}},"V":{{"name":"{"ราคาเหมาะสม" if lang=="TH" else "Valuation"}","score":75,"level":"green","summary":"1 sentence","analysis":"3-5 sentences"}}}},"overall_score":75,"overall_level":"green","recommendation":"BUY","summary":"3-4 sentences","risks":"2-3 risks","catalysts":"2-3 catalysts"}}
score: 70+=green, 40-69=yellow, 0-39=red. recommendation: BUY/HOLD/AVOID"""
    try:
        resp=genai.GenerativeModel(mn).generate_content(prompt)
        clean=re.sub(r'^```json\s*|\s*```$','',resp.text.strip())
        return json.loads(clean)
    except json.JSONDecodeError: return {"error":"parse_failed","raw":resp.text}
    except Exception as e: return {"error":str(e)}


# ─── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    cl,ct=st.columns(2)
    with cl:
        if st.button("🌐 TH/EN"): st.session_state.lang="EN" if TH else "TH"; st.rerun()
    with ct:
        if st.button("☀️" if DARK else "🌙"):
            st.session_state.theme="light" if DARK else "dark"; st.rerun()
    st.markdown("## 📊 D.E.E.P.V")
    st.caption("AI Stock Analyst" if not TH else "วิเคราะห์หุ้นด้วย AI")
    api_key=st.text_input("Google Gemini API Key",type="password",placeholder="AIza...")
    st.markdown("---")
    st.caption("US: NVDA, AAPL  |  TH: PTT.BK")
    t1=st.text_input("Ticker 1",value="NVDA").upper().strip()
    t2=st.text_input("Ticker 2",value="").upper().strip()
    t3=st.text_input("Ticker 3",value="").upper().strip()
    btn=st.button("🚀 วิเคราะห์" if TH else "🚀 Analyze")
    st.divider()
    st.caption("D·Durability  E·Earnings\nE·Execution  P·Pricing  V·Valuation")

tickers_in=[x for x in [t1,t2,t3] if x]
if btn and tickers_in:
    st.session_state.results={}
    for tk in tickers_in:
        with st.spinner(f"{'โหลด' if TH else 'Loading'} {tk}..."): data=get_stock(tk)
        if not data: st.error(f"❌ {tk}"); continue
        ai=None
        if api_key:
            with st.spinner(f"🧠 {tk}..."): ai=run_ai(api_key,tk,data,LANG)
        st.session_state.results[tk]={"data":data,"ai":ai}

results=st.session_state.results

# ══ LANDING ══════════════════════════════════════════════════════════════════════
if not results:
    # ── Market Dashboard
    st.markdown(f"## {'🌍 สถานะตลาดโลกวันนี้' if TH else '🌍 Global Market Dashboard'}")
    idx_cols=st.columns(len(INDICES))
    for col,(name,symbol) in zip(idx_cols,INDICES.items()):
        idata=get_index(symbol)
        if idata:
            cc="#34d399" if idata["change"]>=0 else "#f87171"
            ar="▲" if idata["change"]>=0 else "▼"
            col.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:10px;padding:12px;text-align:center">
              <div style="font-size:.7rem;color:{muted};margin-bottom:4px">{name}</div>
              <div style="font-size:1rem;font-weight:700;color:{text}">{idata['price']:,.0f}</div>
              <div style="font-size:.78rem;color:{cc}">{ar} {abs(idata['change']):.2f}%</div>
            </div>""", unsafe_allow_html=True)
        else:
            col.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:10px;padding:12px;text-align:center">
              <div style="font-size:.7rem;color:{muted}">{name}</div>
              <div style="font-size:.85rem;color:{muted}">—</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""<div style="padding:32px 0;text-align:center">
      <h1 style="font-size:2.4rem;font-weight:800;color:{text};margin:0 0 10px">
        D.E.E.P.V <span style="background:linear-gradient(135deg,#4f7cff,#7c4fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Analyst</span>
      </h1>
      <p style="color:{muted};font-size:.95rem;max-width:480px;margin:0 auto 32px;line-height:1.7">
        {'วิเคราะห์หุ้นเชิงลึกด้วย AI ครอบคลุม 5 มิติ พร้อมคะแนน DEEPV Score' if TH else 'AI-powered stock analysis across 5 dimensions with DEEPV Score and signals'}
      </p>
    </div>""", unsafe_allow_html=True)

    fc=st.columns(4)
    feats=[("📐","DEEPV Score",{"TH":"คะแนน 0-100 + Traffic Light","EN":"0-100 Score + Traffic Light"}),
           ("📰","ข่าวหุ้น",   {"TH":"ข่าวล่าสุดของแต่ละหุ้น","EN":"Latest stock news"}),
           ("👥","Peer Compare",{"TH":"เปรียบเทียบหุ้นกลุ่มเดียวกัน","EN":"Compare sector peers"}),
           ("💼","Portfolio",  {"TH":"จำลอง Asset Allocation","EN":"Portfolio Simulator"})]
    for col,(icon,title,desc) in zip(fc,feats):
        col.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:12px;padding:18px;text-align:center;height:130px">
          <div style="font-size:1.6rem;margin-bottom:6px">{icon}</div>
          <div style="font-weight:600;color:{text};margin-bottom:4px;font-size:.9rem">{title}</div>
          <div style="font-size:.75rem;color:{muted};line-height:1.5">{desc[LANG]}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    st.info("👈 " + ("ใส่ Ticker ใน Sidebar แล้วกด วิเคราะห์หุ้น" if TH else "Enter Ticker in Sidebar then click Analyze"))

# ══ RESULTS ══════════════════════════════════════════════════════════════════════
else:
    tr=list(results.keys())
    tlabels=[f"📈 {x}" for x in tr]
    if len(tr)>1: tlabels.append("⚖️ เปรียบเทียบ" if TH else "⚖️ Compare")
    tlabels+=["💼 Portfolio","🌍 ตลาดโลก" if TH else "🌍 Markets"]
    tabs=st.tabs(tlabels)

    for i,ticker in enumerate(tr):
        with tabs[i]:
            d=results[ticker]["data"]; ai=results[ticker]["ai"]
            cc="#34d399" if d["change"]>=0 else "#f87171"; ar="▲" if d["change"]>=0 else "▼"

            # Header
            st.markdown(f"""<div style="margin-bottom:4px">
              <span style="font-size:1.4rem;font-weight:700;color:{text}">{d['name']}</span>
              <span style="color:{muted};font-size:.82rem;margin-left:8px">{ticker}</span>
              <span style="color:{cc};font-size:.88rem;font-weight:600;margin-left:10px">{ar} {abs(d['change']):.2f}%</span>
            </div>
            <div style="font-size:.75rem;color:{muted};margin-bottom:14px">{d['sector']} · {d['industry']} · {d.get('country','')}</div>
            """, unsafe_allow_html=True)

            # Company info expander
            if d.get("description"):
                with st.expander("📋 " + ("เกี่ยวกับบริษัท" if TH else "About"), expanded=False):
                    st.markdown(f'<p style="color:{muted};font-size:.85rem;line-height:1.7">{d["description"][:600]}...</p>', unsafe_allow_html=True)
                    if d.get("employees"): st.caption(f"👤 {d['employees']:,} employees")
                    if d.get("website"): st.markdown(f'<a href="{d["website"]}" target="_blank" style="color:#4f7cff;font-size:.82rem">🌐 {d["website"]}</a>', unsafe_allow_html=True)

            # ── COMPACT METRICS (5 columns)
            st.markdown(f'<div class="slbl">💰 {"ราคา" if TH else "Price"}</div>', unsafe_allow_html=True)
            m=st.columns(5)
            m[0].metric("Price",f"${d['price']:,.2f}")
            m[1].metric("Prev Close",usd(d.get("prev_close")))
            m[2].metric("Day High",usd(d.get("day_high")))
            m[3].metric("Day Low",usd(d.get("day_low")))
            m[4].metric("Market Cap",fmt(d["cap"]))
            m2=st.columns(5)
            m2[0].metric("52W High",usd(d.get("52w_high")))
            m2[1].metric("52W Low",usd(d.get("52w_low")))
            m2[2].metric("Target",usd(d.get("target")))
            m2[3].metric("Beta",f"{d['beta']:.2f}" if d.get("beta") else "—")
            m2[4].metric("Dividend",pct(d.get("div")))

            st.markdown(f'<div class="slbl" style="margin-top:10px">📐 Valuation</div>', unsafe_allow_html=True)
            v=st.columns(6)
            v[0].metric("P/E",xf(d.get("pe"))); v[1].metric("Fwd P/E",xf(d.get("fwd_pe")))
            v[2].metric("PEG",xf(d.get("peg"))); v[3].metric("P/B",xf(d.get("pb")))
            v[4].metric("P/S",xf(d.get("ps"))); v[5].metric("EV/EBITDA",xf(d.get("ev_eb")))

            st.markdown(f'<div class="slbl" style="margin-top:10px">📊 Financials</div>', unsafe_allow_html=True)
            f_=st.columns(6)
            f_[0].metric("Revenue",fmt(d.get("rev"))); f_[1].metric("Rev Growth",pct(d.get("rev_g")))
            f_[2].metric("Gross Margin",pct(d.get("gm"))); f_[3].metric("Op Margin",pct(d.get("om")))
            f_[4].metric("Net Margin",pct(d.get("nm"))); f_[5].metric("FCF",fmt(d.get("fcf")))

            st.markdown(f'<div class="slbl" style="margin-top:10px">🏦 Balance</div>', unsafe_allow_html=True)
            b_=st.columns(6)
            b_[0].metric("ROE",pct(d.get("roe"))); b_[1].metric("ROA",pct(d.get("roa")))
            b_[2].metric("Cash",fmt(d.get("cash"))); b_[3].metric("Debt",fmt(d.get("debt")))
            b_[4].metric("D/E",f"{d['de']:.1f}" if d.get("de") else "—")
            b_[5].metric("Current Ratio",f"{d['cr']:.2f}" if d.get("cr") else "—")

            st.divider()

            # ── Peer Comparison
            st.markdown(f'<div class="slbl">👥 {"หุ้นเพื่อนบ้าน (Peer Comparison)" if TH else "Sector Peers"}</div>', unsafe_allow_html=True)
            peer_tickers=get_peers(ticker, d['sector'])
            if peer_tickers:
                pcols=st.columns(len(peer_tickers))
                for pc,ptk in zip(pcols,peer_tickers):
                    pd_=get_peer_data(ptk)
                    if pd_:
                        pcc="#34d399" if pd_["change"]>=0 else "#f87171"
                        par="▲" if pd_["change"]>=0 else "▼"
                        pc.markdown(f"""<div class="peer-card">
                          <div style="font-size:.85rem;font-weight:700;color:{text}">{ptk}</div>
                          <div style="font-size:.72rem;color:{muted};margin-bottom:6px">{pd_['name'][:16]}</div>
                          <div style="font-size:1rem;font-weight:700;color:{text}">${pd_['price']:,.2f}</div>
                          <div style="font-size:.78rem;color:{pcc}">{par} {abs(pd_['change']):.2f}%</div>
                          <div style="font-size:.7rem;color:{muted};margin-top:4px">MCap {fmt(pd_['cap'])}</div>
                          <div style="font-size:.7rem;color:{muted}">P/E {xf(pd_.get('pe'))}</div>
                        </div>""", unsafe_allow_html=True)

            st.divider()

            # ── Price Chart
            st.markdown(f'<div class="slbl">📈 {"กราฟราคา" if TH else "Price Chart"}</div>', unsafe_allow_html=True)
            tp=st.radio("",["1d","5d","1mo","3mo","1y","5y","max"],index=4,horizontal=True,key=f"p_{ticker}")
            hist=get_hist(ticker,tp)
            if not hist.empty:
                up=hist["Close"].iloc[-1]>=hist["Close"].iloc[0]; clr="#34d399" if up else "#f87171"
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=hist.index,y=hist["Close"],mode="lines",
                    line=dict(color=clr,width=1.8),fill="tozeroy",
                    fillcolor="rgba(52,211,153,.07)" if up else "rgba(248,113,113,.07)",
                    hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:,.2f}<extra></extra>"))
                lo=plot_base(260); lo["yaxis"]["tickprefix"]="$"
                fig.update_layout(**lo); st.plotly_chart(fig,use_container_width=True)

            # ── Historical Financials
            fin=get_fin(ticker)
            if fin is not None and not fin.empty:
                try:
                    ft=fin.T.sort_index()
                    fig_f=go.Figure()
                    for col,(c_,nm) in [("Total Revenue",("#4f7cff","Revenue $B")),("Net Income",("#34d399","Net Income $B")),("Gross Profit",("#7c4fff","Gross Profit $B"))]:
                        if col in ft.columns:
                            fig_f.add_trace(go.Bar(x=ft.index.year,y=ft[col]/1e9,name=nm,marker_color=c_,opacity=.85))
                    lo2=plot_base(240); lo2["barmode"]="group"; lo2["yaxis"]["ticksuffix"]="B"
                    fig_f.update_layout(**lo2); st.plotly_chart(fig_f,use_container_width=True)
                except: pass

            st.divider()

            # ── News
            st.markdown(f'<div class="slbl">📰 {"ข่าวล่าสุด" if TH else "Latest News"}</div>', unsafe_allow_html=True)
            news=get_news(ticker)
            if news:
                for n in news:
                    title=n.get("title",""); link=n.get("link","#")
                    pub=n.get("publisher",""); ts=n.get("providerPublishTime",0)
                    try:
                        dt=datetime.fromtimestamp(ts,tz=timezone.utc).strftime("%d %b %Y") if ts else ""
                    except: dt=""
                    st.markdown(f"""<div class="news-card">
                      <a href="{link}" target="_blank" style="color:{text};text-decoration:none;font-size:.88rem;font-weight:600;line-height:1.5">{title}</a>
                      <div style="margin-top:6px;font-size:.72rem;color:{muted}">{pub} · {dt}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.caption("ไม่พบข่าว" if TH else "No news available")

            # ── DEEPV Section
            if ai and "dimensions" in ai:
                st.divider()
                overall=ai.get("overall_score",0); rec=ai.get("recommendation","—")
                rc={"BUY":"#34d399","HOLD":"#fbbf24","AVOID":"#f87171"}.get(rec,"#8b92a5"); oc=sc(overall)

                st.markdown(f"""<div style="background:{bg2};border-radius:12px;padding:18px;margin-bottom:16px;
                  display:flex;align-items:center;gap:20px;border:1px solid {border}">
                  <div style="text-align:center;min-width:60px">
                    <div style="font-size:2rem;font-weight:800;color:{oc}">{overall}</div>
                    <div style="font-size:.58rem;color:{muted};text-transform:uppercase">DEEPV Score</div>
                  </div>
                  <div style="flex:1">
                    <div style="background:{border};border-radius:999px;height:7px;overflow:hidden">
                      <div style="background:linear-gradient(90deg,#f87171,#fbbf24,#34d399);width:100%;height:100%;opacity:.2"></div>
                    </div>
                    <div style="background:transparent;border-radius:999px;height:7px;overflow:hidden;margin-top:-7px">
                      <div style="background:{oc};width:{overall}%;height:100%;border-radius:999px"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:3px">
                      <span style="font-size:.58rem;color:#f87171">{"เสี่ยงสูง 0-39" if TH else "High 0-39"}</span>
                      <span style="font-size:.58rem;color:#fbbf24">{"เสี่ยงกลาง 40-69" if TH else "Mid 40-69"}</span>
                      <span style="font-size:.58rem;color:#34d399">{"เสี่ยงต่ำ 70-100" if TH else "Low 70-100"}</span>
                    </div>
                  </div>
                  <div style="text-align:center;min-width:75px">
                    <div style="font-size:1.3rem;font-weight:800;color:{rc};background:{rc}18;border:1px solid {rc}44;border-radius:8px;padding:5px 12px">{rec}</div>
                    <div style="font-size:.58rem;color:{muted};margin-top:3px">Signal</div>
                  </div>
                </div>""", unsafe_allow_html=True)

                for key,dim in ai.get("dimensions",{}).items():
                    s=dim.get("score",0); lc=sc(s); lbl=ll(dim.get("level","yellow"))
                    st.markdown(f"""<div class="dcard" style="border-left:3px solid {lc}">
                      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                        <span style="font-size:1.4rem;font-weight:800;color:{lc};min-width:34px">{key}</span>
                        <div>
                          <div style="font-size:.9rem;font-weight:600;color:{text}">{dim.get('name','')}</div>
                          <div style="font-size:.74rem;color:{muted}">{dim.get('summary','')}</div>
                        </div>
                        <div style="margin-left:auto;text-align:right">
                          <div style="font-size:1.2rem;font-weight:700;color:{lc}">{s}<span style="font-size:.7rem;color:{muted}">/100</span></div>
                          <span style="background:{lc}22;color:{lc};border:1px solid {lc}44;border-radius:5px;padding:1px 6px;font-size:.68rem">{lbl}</span>
                        </div>
                      </div>
                      <div style="height:3px;background:{border};border-radius:999px;margin-bottom:10px;overflow:hidden">
                        <div style="background:{lc};width:{s}%;height:100%;border-radius:999px"></div></div>
                      <p style="color:{muted};margin:0;font-size:.85rem;line-height:1.7">{dim.get('analysis','')}</p>
                    </div>""", unsafe_allow_html=True)

                cl2,cr2=st.columns(2)
                with cl2:
                    st.markdown(f"""<div style="background:{bg2};border-radius:10px;padding:14px;border-left:3px solid #34d399">
                      <div style="font-size:.62rem;color:{muted};text-transform:uppercase;margin-bottom:6px">{"✅ ปัจจัยบวก" if TH else "✅ Catalysts"}</div>
                      <p style="color:{muted};margin:0;line-height:1.7;font-size:.85rem">{ai.get('catalysts','—')}</p></div>""", unsafe_allow_html=True)
                with cr2:
                    st.markdown(f"""<div style="background:{bg2};border-radius:10px;padding:14px;border-left:3px solid #f87171">
                      <div style="font-size:.62rem;color:{muted};text-transform:uppercase;margin-bottom:6px">{"⚠️ ความเสี่ยง" if TH else "⚠️ Risks"}</div>
                      <p style="color:{muted};margin:0;line-height:1.7;font-size:.85rem">{ai.get('risks','—')}</p></div>""", unsafe_allow_html=True)

                st.markdown(f"""<div style="background:{bg2};border-radius:10px;padding:14px;border-left:3px solid {rc};margin-top:10px">
                  <div style="font-size:.62rem;color:{muted};text-transform:uppercase;margin-bottom:6px">{"🧠 สรุปภาพรวม" if TH else "🧠 Summary"}</div>
                  <p style="color:{muted};margin:0;line-height:1.7;font-size:.88rem">{ai.get('summary','')}</p></div>""", unsafe_allow_html=True)

                st.markdown("<br>",unsafe_allow_html=True)
                rpt=f"""<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><title>DEEPV {ticker}</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:#0e1117;color:#e8eaf0;padding:32px;max-width:860px;margin:0 auto}}</style></head>
<body><h2>{d.get('name',ticker)} ({ticker}) — DEEPV: {overall} | {rec}</h2><p>{ai.get('summary','')}</p></body></html>"""
                st.download_button("📄 " + ("ดาวน์โหลด Report" if TH else "Download Report"),
                    data=rpt.encode("utf-8"),file_name=f"DEEPV_{ticker}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html",key=f"dl_{ticker}")
                st.balloons()

            elif ai and "error" in ai: st.error(f"❌ {ai['error']}")
            elif not api_key: st.info("💡 " + ("ใส่ API Key เพื่อดู DEEPV Analysis" if TH else "Add API Key to see DEEPV Analysis"))

    # ── Compare ──────────────────────────────────────────────────────────────────
    if len(tr)>1:
        with tabs[len(tr)]:
            st.markdown(f"### {'⚖️ เปรียบเทียบ' if TH else '⚖️ Compare'}")
            has_ai={x:r["ai"] for x,r in results.items() if r["ai"] and "dimensions" in r["ai"]}
            pal=["#4f7cff","#34d399","#fbbf24"]
            if has_ai:
                dk=["D","E1","E2","P","V"]; dn=["Durability","Earnings","Execution","Pricing","Valuation"]
                fig=go.Figure()
                for idx,(x,aai) in enumerate(has_ai.items()):
                    fig.add_trace(go.Bar(name=x,x=dn,y=[aai["dimensions"].get(k,{}).get("score",0) for k in dk],marker_color=pal[idx%len(pal)]))
                lo3=plot_base(320); lo3["barmode"]="group"; lo3["yaxis"]["range"]=[0,100]
                fig.update_layout(**lo3); st.plotly_chart(fig,use_container_width=True)
                td={}
                for x,aai in has_ai.items():
                    row={}
                    for k in dk:
                        s=aai["dimensions"].get(k,{}).get("score",0); lv=aai["dimensions"].get(k,{}).get("level","yellow")
                        row[k]=f'{"🟢" if lv=="green" else "🟡" if lv=="yellow" else "🔴"} {s}'
                    row["Overall"]=aai.get("overall_score",0); row["Signal"]=aai.get("recommendation","—"); td[x]=row
                st.dataframe(pd.DataFrame(td).T,use_container_width=True)
            else: st.info("วิเคราะห์ 2+ ตัวพร้อม API Key" if TH else "Analyze 2+ stocks with API Key")
            cp=st.radio("",["1mo","3mo","1y","5y"],index=2,horizontal=True,key="cmp")
            fig2=go.Figure()
            for idx,x in enumerate(tr):
                h=get_hist(x,cp)
                if not h.empty:
                    norm=(h["Close"]/h["Close"].iloc[0])*100
                    fig2.add_trace(go.Scatter(x=h.index,y=norm,name=x,line=dict(color=pal[idx%len(pal)],width=2),
                        hovertemplate=f"<b>{x}</b>: %{{y:.1f}}%<extra></extra>"))
            lo4=plot_base(280); lo4["yaxis"]["ticksuffix"]="%"
            fig2.update_layout(**lo4); st.plotly_chart(fig2,use_container_width=True)

    # ── Portfolio ─────────────────────────────────────────────────────────────────
    with tabs[-2]:
        st.markdown(f"### 💼 Portfolio")
        pa_,pb_,pc_=st.columns([2,1,1])
        with pa_: pt_=st.text_input("Ticker",placeholder="NVDA, PTT.BK").upper().strip()
        with pb_: pal_=st.number_input("%",min_value=1,max_value=100,value=25,step=5)
        with pc_:
            st.markdown("<br>",unsafe_allow_html=True)
            if st.button("➕ Add"):
                if pt_:
                    if pt_ in [p["ticker"] for p in st.session_state.portfolio]: st.warning("มีแล้ว")
                    else:
                        with st.spinner(f"Loading {pt_}..."): pd__=get_stock(pt_)
                        if pd__:
                            st.session_state.portfolio.append({"ticker":pt_,"name":pd__["name"],"alloc":pal_,
                                "price":pd__["price"],"change":pd__["change"],"sector":pd__["sector"],"beta":pd__.get("beta")})
                            st.rerun()
                        else: st.error(f"❌ {pt_}")

        if results and st.button("📥 Import analyzed"):
            ex=[p["ticker"] for p in st.session_state.portfolio]
            for x,r in results.items():
                if x not in ex and r["data"]:
                    d_=r["data"]; ea=max(1,round(100/max(1,len(results)+len(ex))))
                    st.session_state.portfolio.append({"ticker":x,"name":d_["name"],"alloc":ea,
                        "price":d_["price"],"change":d_["change"],"sector":d_["sector"],"beta":d_.get("beta")})
            st.rerun()

        port=st.session_state.portfolio
        if not port:
            st.markdown(f'<div style="text-align:center;padding:40px 0;color:{muted}"><div style="font-size:2rem">💼</div><p>{"ยังไม่มีหุ้นในพอร์ต" if TH else "Portfolio is empty"}</p></div>',unsafe_allow_html=True)
        else:
            st.markdown("---"); total=0; upd=[]
            for idx,p in enumerate(port):
                co1,co2,co3,co4=st.columns([3,2,1,1])
                cc_="#34d399" if p["change"]>=0 else "#f87171"
                with co1: st.markdown(f'<div style="padding:6px 0"><span style="font-weight:600;color:{text}">{p["ticker"]}</span> <span style="color:{muted};font-size:.78rem">{p["name"][:20]}</span> <span style="color:{cc_};font-size:.78rem">{"▲" if p["change"]>=0 else "▼"}{abs(p["change"]):.1f}%</span></div>',unsafe_allow_html=True)
                with co2: na=st.slider("",1,100,p["alloc"],key=f"sl_{idx}",label_visibility="collapsed"); p["alloc"]=na
                with co3: st.markdown(f'<div style="padding-top:10px;font-weight:700;color:#4f7cff">{na}%</div>',unsafe_allow_html=True)
                with co4:
                    if st.button("🗑️",key=f"del_{idx}"): st.session_state.portfolio.pop(idx); st.rerun()
                total+=na; upd.append(p)
            st.session_state.portfolio=upd
            ac="#34d399" if total==100 else "#fbbf24" if total<100 else "#f87171"
            st.markdown(f'<div style="text-align:right;font-size:.82rem;color:{ac};margin-bottom:10px">Total: <strong>{total}%</strong> {"✅" if total==100 else "⚠️"}</div>',unsafe_allow_html=True)
            st.markdown("---")
            pp1,pp2=st.columns(2)
            with pp1:
                fig_pie=go.Figure(go.Pie(labels=[p["ticker"] for p in port],values=[p["alloc"] for p in port],
                    hole=.5,marker=dict(colors=["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa","#fb923c"][:len(port)]),
                    textinfo="label+percent",textfont=dict(color=text,size=11)))
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)",height=240,showlegend=False,margin=dict(l=0,r=0,t=8,b=0))
                st.plotly_chart(fig_pie,use_container_width=True)
            with pp2:
                sa={}
                for p in port: sa[p["sector"]]=sa.get(p["sector"],0)+p["alloc"]
                fig_s=go.Figure(go.Bar(x=list(sa.values()),y=list(sa.keys()),orientation="h",
                    marker_color="#7c4fff",text=[f"{v}%" for v in sa.values()],textposition="outside",textfont=dict(color=muted,size=10)))
                lo5=plot_base(240); lo5["xaxis"]["ticksuffix"]="%"; lo5.pop("hovermode",None)
                fig_s.update_layout(**lo5); st.plotly_chart(fig_s,use_container_width=True)
            pp_r=st.radio("",["1mo","3mo","1y","5y"],index=2,horizontal=True,key="port_p")
            fig_pf=go.Figure(); pr=None; cls_=["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa"]
            for idx,p in enumerate(port):
                h=get_hist(p["ticker"],pp_r)
                if not h.empty:
                    norm=(h["Close"]/h["Close"].iloc[0])*100
                    pr=(norm*(p["alloc"]/100)) if pr is None else pr+norm*(p["alloc"]/100)
                    fig_pf.add_trace(go.Scatter(x=h.index,y=norm,name=p["ticker"],
                        line=dict(color=cls_[idx%len(cls_)],width=1.4,dash="dot"),opacity=.5,
                        hovertemplate=f"<b>{p['ticker']}</b>: %{{y:.1f}}%<extra></extra>"))
            if pr is not None:
                fig_pf.add_trace(go.Scatter(x=pr.index,y=pr,name="📦 Portfolio",
                    line=dict(color="#ffffff" if DARK else "#111827",width=2.5),
                    hovertemplate="<b>Portfolio</b>: %{y:.1f}%<extra></extra>"))
            lo6=plot_base(280); lo6["yaxis"]["ticksuffix"]="%"
            fig_pf.update_layout(**lo6); st.plotly_chart(fig_pf,use_container_width=True)
            m1,m2,m3=st.columns(3)
            m1.metric("Holdings",f"{len(port)}")
            m2.metric("Weighted Beta",f"{sum([(p.get('beta') or 1)*p['alloc']/100 for p in port]):.2f}")
            m3.metric("Today",f"{sum([p['change']*p['alloc']/100 for p in port]):+.2f}%")
            if st.button("🗑️ Clear All"): st.session_state.portfolio=[]; st.rerun()

    # ── Markets Tab ───────────────────────────────────────────────────────────────
    with tabs[-1]:
        st.markdown(f"### {'🌍 สถานะตลาดโลก' if TH else '🌍 Global Markets'}")       
        idx_cols=st.columns(4)
        for idx,(name,symbol) in enumerate(INDICES.items()):
            idata=get_index(symbol)
            col=idx_cols[idx%4]
            if idata:
                cc="#34d399" if idata["change"]>=0 else "#f87171"; ar="▲" if idata["change"]>=0 else "▼"
                col.markdown(f"""<div style="background:{bg2};border:1px solid {border};border-radius:10px;padding:14px;margin-bottom:10px">
                  <div style="font-size:.72rem;color:{muted};margin-bottom:4px">{name}</div>
                  <div style="font-size:1.15rem;font-weight:700;color:{text}">{idata['price']:,.2f}</div>
                  <div style="font-size:.82rem;color:{cc}">{ar} {abs(idata['change']):.2f}%</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"#### {'เปรียบเทียบ Index ย้อนหลัง' if TH else 'Index Performance'}")
        idx_sel=st.multiselect("เลือก Index" if TH else "Select Indices",
            list(INDICES.keys()), default=["S&P 500","NASDAQ","SET (TH)"])
        idx_period=st.radio("",["1mo","3mo","1y","5y"],index=2,horizontal=True,key="idx_p")
        fig_idx=go.Figure(); pal_idx=["#4f7cff","#34d399","#fbbf24","#f87171","#a78bfa","#fb923c","#38bdf8","#f472b6"]
        for ii,name in enumerate(idx_sel):
            sym=INDICES.get(name)
            if sym:
                h=get_hist(sym,idx_period)
                if not h.empty:
                    norm=(h["Close"]/h["Close"].iloc[0])*100
                    fig_idx.add_trace(go.Scatter(x=h.index,y=norm,name=name,
                        line=dict(color=pal_idx[ii%len(pal_idx)],width=2),
                        hovertemplate=f"<b>{name}</b>: %{{y:.1f}}%<extra></extra>"))
        lo7=plot_base(360); lo7["yaxis"]["ticksuffix"]="%"
        fig_idx.update_layout(**lo7); st.plotly_chart(fig_idx,use_container_width=True)
