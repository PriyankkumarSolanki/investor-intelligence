"""Streamlit UI for the Investor Intelligence Platform.

Replaces the reference project's Jinja2 dashboard. Talks to the FastAPI backend
over HTTP (BACKEND_URL). Three views: Upload, Dashboard, AI Analyst chat.
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

st.set_page_config(page_title="Investor Intelligence Platform", page_icon="📊", layout="wide")


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
            st.error(
                f"Extraction was rate-limited. Wait ~30s and try again. ({exc})"
            )


def upload_view() -> None:
    st.subheader("Upload an annual report (PDF)")
    st.caption(
        "Name files like `2024_Apple.pdf` so the company and year are parsed "
        "automatically."
    )
    file = st.file_uploader("Annual report", type=["pdf"])
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
    st.subheader("Financial KPI dashboard")
    metrics = fetch_metrics()

    # Offer KPI generation for anything ingested but not yet extracted
    # (e.g. when upload-time extraction was rate-limited).
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
    st.subheader("AI analyst chatbot")
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


st.title("📊 AI-Powered Investor Intelligence Platform")
st.caption("Open-stack RAG: Gemini + pgvector + FastAPI + Streamlit")

tab_dash, tab_upload, tab_chat = st.tabs(["Dashboard", "Upload", "AI Analyst"])
with tab_dash:
    dashboard_view()
with tab_upload:
    upload_view()
with tab_chat:
    chat_view()
