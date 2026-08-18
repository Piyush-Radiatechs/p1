"""Streamlit frontend for AI-powered JD → LinkedIn candidate search.

COMPLIANCE: This UI displays search-engine metadata only. The LinkedIn button
opens the profile URL in the user's browser — no automated LinkedIn access.
"""

import asyncio
import logging
import re
from io import StringIO

import pandas as pd
import streamlit as st

from app.config import get_settings
from app.exceptions import AppError
from app.services.pipeline import process_jd_file, process_jd_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

st.set_page_config(
    page_title="AI Candidate Search",
    page_icon="🔍",
    layout="wide",
)


def _display_name_from_title(title: str) -> str:
    if not title:
        return "Unknown"
    cleaned = re.sub(r"\s*[|\-–—]\s*LinkedIn.*$", "", title, flags=re.IGNORECASE)
    for sep in [" | ", " – ", " — ", " - "]:
        if sep in cleaned:
            return cleaned.split(sep)[0].strip()
    return cleaned.strip() or "Unknown"


def _format_experience(requirements: dict) -> str:
    exp = requirements.get("experience") or {}
    min_y = exp.get("min_years")
    max_y = exp.get("max_years")
    if min_y is not None and max_y is not None:
        return f"{min_y}–{max_y} years"
    if min_y is not None:
        return f"{min_y}+ years"
    if max_y is not None:
        return f"Up to {max_y} years"
    return "Not specified"


def _run_pipeline_from_file(file_bytes: bytes, filename: str, serpapi_key: str) -> dict:
    return asyncio.run(
        process_jd_file(
            file_bytes,
            filename=filename,
            serpapi_key=serpapi_key,
        )
    )


def _run_pipeline_from_text(jd_text: str, serpapi_key: str) -> dict:
    return asyncio.run(
        process_jd_text(
            jd_text,
            filename="pasted_jd.txt",
            serpapi_key=serpapi_key,
        )
    )


def _candidates_dataframe(candidates: list[dict]) -> pd.DataFrame:
    rows = []
    for candidate in candidates:
        title = candidate.get("title") or ""
        rows.append(
            {
                "Name / Title": _display_name_from_title(title),
                "Search Title": title,
                "LinkedIn URL": candidate.get("linkedin_url") or "",
                "Snippet": candidate.get("snippet") or "",
                "Found In Queries": "; ".join(candidate.get("found_in_queries") or []),
            }
        )
    return pd.DataFrame(rows)


def _render_requirements(requirements: dict) -> None:
    titles = requirements.get("job_titles") or []
    skills = requirements.get("technical_skills") or []
    preferred = requirements.get("preferred_skills") or []
    locations = requirements.get("locations") or []

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Role:**")
        st.write(", ".join(titles) if titles else "—")

        st.markdown("**Skills:**")
        if skills:
            st.write(", ".join(skills))
        else:
            st.write("—")

        if preferred:
            st.markdown("**Preferred Skills:**")
            st.write(", ".join(preferred))

    with col2:
        st.markdown("**Locations:**")
        st.write(", ".join(locations) if locations else "—")

        st.markdown("**Experience:**")
        st.write(_format_experience(requirements))

        industries = requirements.get("industries") or []
        if industries:
            st.markdown("**Industries:**")
            st.write(", ".join(industries))


def _render_queries(queries: list[str]) -> None:
    for i, query in enumerate(queries, 1):
        st.markdown(f"**Query {i}**")
        st.code(query, language=None)


def _render_candidates(candidates: list[dict]) -> None:
    if not candidates:
        st.info(
            "No LinkedIn profiles found in search results. "
            "Try adjusting the JD or search settings."
        )
        return

    for candidate in candidates:
        title = candidate.get("title", "")
        name = _display_name_from_title(title)
        snippet = candidate.get("snippet") or ""
        url = candidate.get("linkedin_url", "")

        st.markdown("---")
        st.subheader(name)
        if title:
            st.caption(title)

        if snippet:
            st.markdown("**Search snippet:**")
            st.write(snippet)

        st.link_button("Open LinkedIn", url, type="primary")


def main() -> None:
    settings = get_settings()

    st.title("AI Candidate Search")
    st.caption(
        "Upload a Job Description (PDF, Word, or text) or paste the JD to extract "
        "requirements, generate X-Ray queries, and discover LinkedIn profiles via Google search."
    )

    with st.sidebar:
        st.header("API Keys")
        st.write(f"Mistral: {'✅' if settings.mistral_configured else '❌ Not configured'}")
        serpapi_key = st.text_input(
            "Your SerpApi Key",
            type="password",
            placeholder="Enter SerpApi key",
            help="Required for Google search. Your key is used only for this session.",
        )
        st.divider()
        st.markdown("**Limits**")
        st.write(f"Max queries per JD: {settings.max_queries_per_jd}")
        st.write(f"Max results per query: {settings.max_results_per_query}")

    source = st.radio(
        "Job description source",
        options=["Upload file", "Enter text"],
        horizontal=True,
    )

    uploaded = None
    pasted_text = ""
    if source == "Upload file":
        uploaded = st.file_uploader(
            "Upload Job Description",
            type=["pdf", "docx", "txt"],
            help="Accepted formats: PDF, Word (.docx), or plain text (.txt).",
        )
    else:
        pasted_text = st.text_area(
            "Paste Job Description",
            height=280,
            placeholder="Paste the full job description here...",
        )

    has_input = uploaded is not None or bool(pasted_text.strip())
    search_clicked = st.button(
        "Search Candidates",
        type="primary",
        disabled=not has_input,
    )

    if search_clicked and has_input:
        if not settings.mistral_configured:
            st.error(
                "MISTRAL_API_KEY is not configured. "
                "Add it to Streamlit Cloud Secrets (Manage app → Settings → Secrets) "
                "or to a local .env file."
            )
            return
        if not serpapi_key.strip():
            st.error("Please enter your SerpApi key in the sidebar.")
            return

        with st.spinner("Processing job description and searching candidates..."):
            try:
                if uploaded is not None:
                    file_bytes = uploaded.read()
                    if not file_bytes:
                        st.error("Uploaded file is empty.")
                        return
                    result = _run_pipeline_from_file(
                        file_bytes,
                        filename=uploaded.name,
                        serpapi_key=serpapi_key.strip(),
                    )
                else:
                    result = _run_pipeline_from_text(
                        pasted_text,
                        serpapi_key=serpapi_key.strip(),
                    )
                st.session_state["search_result"] = result
            except AppError as exc:
                logger.error("Pipeline error: %s", exc.message)
                st.error(exc.message)
                return
            except Exception:
                logger.exception("Unexpected UI error")
                st.error("Something went wrong. Please try again.")
                return

    result = st.session_state.get("search_result")
    if not result:
        return

    st.divider()
    st.subheader("Search Summary")
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("Searches used", result.get("searches_run", 0))
    summary_col2.metric("Unique profiles", result.get("candidates_found", 0))
    summary_col3.metric("Raw results", len(result.get("search_results") or []))

    with st.expander("JD Summary", expanded=True):
        _render_requirements(result.get("requirements") or {})

    with st.expander("Generated X-Ray Queries", expanded=False):
        _render_queries(result.get("queries") or [])

    candidates = result.get("candidates") or []
    st.subheader("Candidate Results")
    st.write(f"**{result.get('candidates_found', 0)} candidates found**")

    if candidates:
        df = _candidates_dataframe(candidates)
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download candidates table (CSV)",
            data=csv_buffer.getvalue(),
            file_name="candidates.csv",
            mime="text/csv",
            type="secondary",
        )

    _render_candidates(candidates)


if __name__ == "__main__":
    main()
