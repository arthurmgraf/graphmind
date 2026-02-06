from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import streamlit as st


def _api_url() -> str:
    return st.session_state.get("api_url", "http://localhost:8000")


def _post(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{_api_url()}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()


def _get(path: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{_api_url()}{path}")
        resp.raise_for_status()
        return resp.json()


def _render_query_page() -> None:
    st.header("Query the Knowledge Base")

    question = st.text_input("Question", placeholder="Ask anything about the ingested documents...")
    top_k = st.slider("Top K sources", min_value=1, max_value=50, value=10)

    if st.button("Ask", type="primary"):
        if not question.strip():
            st.warning("Please enter a question.")
            return

        with st.spinner("Querying..."):
            try:
                data = _post("/api/v1/query", {"question": question, "top_k": top_k})
            except Exception as exc:
                st.error(f"API request failed: {exc}")
                return

        st.subheader("Answer")
        st.markdown(data.get("answer", ""))

        col1, col2, col3 = st.columns(3)
        col1.metric("Eval Score", f"{data.get('eval_score', 0.0):.2f}")
        col2.metric("Latency", f"{data.get('latency_ms', 0.0):.0f} ms")
        col3.metric("Sources Used", data.get("sources_used", 0))

        citations = data.get("citations", [])
        if citations:
            with st.expander(f"Citations ({len(citations)})"):
                for i, cite in enumerate(citations, 1):
                    st.markdown(f"**[{i}]** {cite.get('source', 'unknown source')}")
                    st.caption(cite.get("text_snippet", ""))
                    st.divider()


def _render_ingest_page() -> None:
    st.header("Ingest Documents")

    uploaded = st.file_uploader("Upload a file (optional)", type=["md", "pdf", "html", "txt", "py", "ts", "js"])

    filename = st.text_input("Filename", value=uploaded.name if uploaded else "")
    doc_type = st.selectbox("Document type", ["md", "pdf", "html", "txt", "py", "ts", "js"])
    content = st.text_area(
        "Content",
        value=uploaded.read().decode("utf-8", errors="replace") if uploaded else "",
        height=300,
    )

    if st.button("Ingest", type="primary"):
        if not content.strip():
            st.warning("Please provide content to ingest.")
            return
        if not filename.strip():
            st.warning("Please provide a filename.")
            return

        with st.spinner("Ingesting..."):
            try:
                data = _post(
                    "/api/v1/ingest",
                    {"content": content, "filename": filename, "doc_type": doc_type},
                )
            except Exception as exc:
                st.error(f"Ingestion failed: {exc}")
                return

        st.success("Document ingested successfully!")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Document ID", data.get("document_id", "")[:8] + "...")
        col2.metric("Chunks", data.get("chunks_created", 0))
        col3.metric("Entities", data.get("entities_extracted", 0))
        col4.metric("Relations", data.get("relations_extracted", 0))


def _render_knowledge_graph_page() -> None:
    st.header("Knowledge Graph")

    try:
        stats = _get("/api/v1/stats")
    except Exception as exc:
        st.error(f"Failed to fetch graph stats: {exc}")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entities", stats.get("total_entities", 0))
    col2.metric("Total Relations", stats.get("total_relations", 0))
    col3.metric("Total Documents", stats.get("total_documents", 0))
    col4.metric("Total Chunks", stats.get("total_chunks", 0))

    entity_types = stats.get("entity_types", {})
    if entity_types:
        st.subheader("Entity Types")
        st.bar_chart(pd.DataFrame({"count": entity_types}, index=entity_types.keys()))

    relation_types = stats.get("relation_types", {})
    if relation_types:
        st.subheader("Relation Types")
        st.bar_chart(pd.DataFrame({"count": relation_types}, index=relation_types.keys()))


def _render_system_page() -> None:
    st.header("System Health")

    try:
        health = _get("/api/v1/health")
    except Exception as exc:
        st.error(f"Failed to fetch health status: {exc}")
        return

    status = health.get("status", "unknown")
    if status == "ok":
        st.success(f"Overall status: **{status}**")
    else:
        st.error(f"Overall status: **{status}**")

    st.metric("Version", health.get("version", "unknown"))

    services = health.get("services", {})
    if services:
        st.subheader("Services")
        for name, svc_status in services.items():
            indicator = "\U0001f7e2" if svc_status == "ok" else "\U0001f534"
            st.markdown(f"{indicator} **{name}**: {svc_status}")


_PAGES = {
    "Query": _render_query_page,
    "Ingest": _render_ingest_page,
    "Knowledge Graph": _render_knowledge_graph_page,
    "System": _render_system_page,
}


def _run_dashboard() -> None:
    st.set_page_config(page_title="GraphMind", page_icon="\U0001f9e0", layout="wide")

    with st.sidebar:
        st.title("GraphMind")
        page = st.selectbox("Navigation", list(_PAGES.keys()))
        st.text_input(
            "API URL",
            value="http://localhost:8000",
            key="api_url",
        )

    _PAGES[page]()


def main() -> None:
    from streamlit.web.cli import main_run

    main_run([str(Path(__file__).resolve())])


if __name__ == "__main__":
    _run_dashboard()
