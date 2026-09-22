"""Streamlit UI for the Investor Intelligence Platform.

Talks to the FastAPI backend over HTTP (BACKEND_URL). Three views: Dashboard,
Upload, AI Analyst chat.

Styled to match the author's portfolio site (~/port/portfolio): an editorial
"cobalt on warm paper" system — Inter + JetBrains Mono, a single cobalt accent,
pill buttons, raised paper cards. Theme colours are set in
`.streamlit/config.toml`; the finer component styling is the injected CSS below.
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

KPI_FIELDS = [
    ("revenue", "Revenue"),
    ("net_income", "Net Income"),
    ("operating_income", "Operating Income"),
    ("cash_flow", "Operating Cash Flow"),
    ("total_assets", "Total Assets"),
    ("total_liabilities", "Total Liabilities"),
]

st.set_page_config(
    page_title="Investor Intelligence Platform",
    page_icon="◆",
    layout="wide",
)

# --- Portfolio design system (cobalt on warm paper) -----------------------
_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300..700;1,300..600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --canvas:#EFEEE8; --surface:#F7F6F1; --surface-2:#FBFAF6; --ink:#16171B;
  --ink-70:rgba(22,23,27,.66); --ink-45:rgba(22,23,27,.45);
  --accent:#1F45D6; --accent-ink:#fff; --accent-soft:#E2E6FB; --accent-deep:#16309A;
  --hairline:rgba(22,23,27,.14); --hairline-soft:rgba(22,23,27,.08);
  --font-sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --font-mono:"JetBrains Mono","SF Mono",Menlo,monospace;
  --radius-md:10px; --radius-lg:20px; --radius-pill:50px;
}

/* Canvas + base type */
.stApp, [data-testid="stAppViewContainer"] { background: var(--canvas); }
html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] * {
  font-family: var(--font-sans);
}
body { color: var(--ink); -webkit-font-smoothing: antialiased; }

/* Remove Streamlit chrome for a cleaner editorial page */
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
  display: none !important;
}

/* Content column */
.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1120px; padding-top: 8px; padding-bottom: 96px;
}

/* Headings */
h1, h2, h3 { color: var(--ink); font-family: var(--font-sans); }
h1 { font-variation-settings:"wght" 560; letter-spacing:-.03em; line-height:1.0; }
h2 { font-variation-settings:"wght" 560; letter-spacing:-.022em; }
h3 { font-variation-settings:"wght" 560; letter-spacing:-.018em; }

/* Hero */
.ii-hero { padding: 40px 0 8px; }
.ii-eyebrow {
  font-family: var(--font-mono); text-transform: lowercase; letter-spacing:.14em;
  font-size: 13px; color: var(--accent); display: inline-flex; align-items:center;
  gap: 9px; margin-bottom: 14px;
}
.ii-eyebrow::before { content:""; width:7px; height:7px; border-radius:50%; background:var(--accent); }
.ii-hero h1 {
  font-size: clamp(34px, 5.4vw, 58px); font-variation-settings:"wght" 560;
  line-height: 1.02; letter-spacing:-.03em; margin: 0 0 14px;
}
.ii-hero h1 em { font-style: italic; color: var(--accent); font-variation-settings:"wght" 520; }
.ii-lead { font-size: 19px; color: var(--ink-70); max-width: 640px; line-height:1.5; font-variation-settings:"wght" 350; }
.ii-rule { height:1px; background: var(--hairline); margin: 28px 0 8px; border:0; }

/* Section eyebrow (mono, uppercase) */
.ii-sec { font-family: var(--font-mono); text-transform: uppercase; letter-spacing:.14em;
  font-size: 12px; color: var(--ink-45); margin: 6px 0 2px; }
.ii-sec b { color: var(--accent); font-weight: 600; }

/* Tabs -> editorial nav */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--hairline); }
.stTabs [data-baseweb="tab"] {
  font-family: var(--font-mono); text-transform: uppercase; letter-spacing:.1em;
  font-size: 12.5px; color: var(--ink-45); background: transparent; padding: 8px 14px;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--ink); }
.stTabs [aria-selected="true"] { color: var(--accent) !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { background: var(--accent) !important; }

/* Buttons -> pill; default dark ink, primary cobalt */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
  border-radius: var(--radius-pill) !important; min-height: 48px; padding: 10px 26px;
  font-family: var(--font-sans); font-variation-settings:"wght" 500; letter-spacing:-.01em;
  border: none !important; background: var(--ink); color: var(--surface-2);
  transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-2px); box-shadow: 0 10px 24px rgba(22,23,27,.18); color: var(--surface-2);
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background: var(--accent); color: var(--accent-ink);
}
.stButton > button[kind="primary"]:hover {
  background: var(--accent-deep); box-shadow: 0 10px 24px rgba(31,69,214,.28);
}

/* Metric cards */
[data-testid="stMetric"] {
  background: var(--surface); border: 1px solid var(--hairline-soft);
  border-radius: var(--radius-lg); padding: 18px 20px;
}
[data-testid="stMetricLabel"] p {
  font-family: var(--font-mono); text-transform: uppercase; letter-spacing:.1em;
  font-size: 11.5px !important; color: var(--ink-45);
}
[data-testid="stMetricValue"] {
  font-variation-settings:"wght" 560; letter-spacing:-.02em; color: var(--ink);
  font-size: clamp(20px, 2.2vw, 27px) !important;
}
[data-testid="stMetricValue"] > div {
  white-space: normal; overflow: visible; text-overflow: clip; line-height: 1.1;
}

/* Expanders -> cards */
[data-testid="stExpander"] {
  border: 1px solid var(--hairline-soft) !important; border-radius: var(--radius-lg) !important;
  background: var(--surface); overflow: hidden;
}
[data-testid="stExpander"] summary p {
  font-family: var(--font-mono); text-transform: uppercase; letter-spacing:.1em;
  font-size: 12.5px; color: var(--ink-70);
}

/* Inputs, selects, uploader */
[data-baseweb="select"] > div, [data-baseweb="input"], .stTextInput input {
  border-radius: var(--radius-md) !important; border-color: var(--hairline) !important;
  background: var(--surface-2) !important;
}
[data-testid="stFileUploaderDropzone"] {
  background: var(--surface); border: 1.5px dashed var(--hairline); border-radius: var(--radius-lg);
}

/* Dataframe */
[data-testid="stDataFrame"] {
  border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--hairline-soft);
}

/* Alerts a touch softer */
[data-testid="stAlert"] { border-radius: var(--radius-md); }
</style>
"""

st.markdown(_STYLE, unsafe_allow_html=True)


def _eyebrow(text: str) -> None:
    st.markdown(f'<div class="ii-sec">{text}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=15)
def fetch_metrics() -> list[dict]:
    try:
        resp = requests.get(f"{BACKEND_URL}/api/metrics", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.warning(f"Could not reach backend at {BACKEND_URL}: {exc}")
        return []


@st.cache_data(ttl=15)
def fetch_ingested() -> list[dict]:
    try:
        resp = requests.get(f"{BACKEND_URL}/api/ingested", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def generate_kpis(company: str, year) -> None:
    payload = {"company": company}
    if year not in (None, "", "None"):
        try:
            payload["year"] = int(year)
        except (TypeError, ValueError):
            pass
    with st.spinner(f"Extracting KPIs for {company}… (one LLM call)"):
        try:
            resp = requests.post(f"{BACKEND_URL}/api/extract", json=payload, timeout=180)
            resp.raise_for_status()
            st.success(f"KPIs generated for {company}.")
            fetch_metrics.clear()
        except Exception as exc:
            st.error(f"Extraction was rate-limited. Wait ~30s and try again. ({exc})")


def upload_view() -> None:
    _eyebrow("02 · Ingest")
    st.subheader("Upload an annual report")
    st.caption("Name files like `2025_Apple.pdf` so the company and year are parsed automatically.")
    file = st.file_uploader("Annual report (PDF)", type=["pdf"])
    if file and st.button("Ingest report", type="primary"):
        with st.spinner("Converting, chunking, embedding and extracting KPIs…"):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/api/upload",
                    files={"file": (file.name, file.getvalue(), "application/pdf")},
                    timeout=600,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("metrics_error"):
                    st.warning(data["message"])
                else:
                    st.success(data["message"])
                    st.json(data.get("metrics", {}))
                fetch_metrics.clear()
                fetch_ingested.clear()
            except Exception as exc:
                st.error(f"Upload failed: {exc}")


def dashboard_view() -> None:
    _eyebrow("01 · Overview")
    st.subheader("Financial KPI dashboard")
    metrics = fetch_metrics()

    ingested = fetch_ingested()
    have = {(m["company"], str(m["year"])) for m in metrics}
    pending = [r for r in ingested if (r["company"], str(r["year"])) not in have]
    if pending:
        st.info("These reports are ingested but have no KPIs yet:")
        for r in pending:
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{r['company']}** ({r['year']}) — {r['chunks']} chunks")
            if c2.button("Generate KPIs", key=f"gen_{r['company']}_{r['year']}"):
                generate_kpis(r["company"], r["year"])
                st.rerun()

    if not metrics:
        st.info("No KPIs yet. Upload a report, then generate KPIs above.")
        return

    companies = [f"{m['company']} ({m['year']})" for m in metrics]
    idx = st.selectbox("Company", range(len(companies)), format_func=lambda i: companies[i])
    row = metrics[idx]

    cols = st.columns(3)
    for i, (key, label) in enumerate(KPI_FIELDS):
        cols[i % 3].metric(label, row.get(key) or "—")

    with st.expander("Top risk factors"):
        st.write(row.get("risk_factors") or "—")
    with st.expander("Top growth drivers"):
        st.write(row.get("growth_drivers") or "—")

    st.markdown("### Compare companies")
    df = pd.DataFrame(metrics)
    if not df.empty:
        st.dataframe(
            df[["company", "year"] + [k for k, _ in KPI_FIELDS]],
            use_container_width=True,
            hide_index=True,
        )


def chat_view() -> None:
    _eyebrow("03 · Ask")
    st.subheader("AI analyst")
    metrics = fetch_metrics()
    company_opts = ["(all)"] + sorted({m["company"] for m in metrics if m.get("company")})
    company = st.selectbox("Scope to company", company_opts)
    question = st.text_input("Ask about the reports", placeholder="What drove revenue growth?")
    if question and st.button("Ask", type="primary"):
        payload: dict = {"question": question}
        if company != "(all)":
            payload["company"] = company
        with st.spinner("Thinking…"):
            try:
                resp = requests.post(f"{BACKEND_URL}/api/chat", json=payload, timeout=120)
                resp.raise_for_status()
                st.markdown(resp.json().get("answer", "_No answer._"))
            except Exception as exc:
                st.error(f"Chat failed: {exc}")


# --- Hero ------------------------------------------------------------------
st.markdown(
    """
    <div class="ii-hero">
      <span class="ii-eyebrow">rag · investor intelligence</span>
      <h1>AI-Powered <em>Investor</em><br>Intelligence Platform</h1>
      <p class="ii-lead">Upload a company's annual report and get the numbers that
      matter — extracted, compared, and explained by a retrieval-grounded analyst.</p>
      <hr class="ii-rule">
    </div>
    """,
    unsafe_allow_html=True,
)

tab_dash, tab_upload, tab_chat = st.tabs(["Dashboard", "Upload", "AI Analyst"])
with tab_dash:
    dashboard_view()
with tab_upload:
    upload_view()
with tab_chat:
    chat_view()
