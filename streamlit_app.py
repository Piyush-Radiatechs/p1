"""Streamlit frontend for AI-powered JD → LinkedIn candidate search.

COMPLIANCE: This UI displays search-engine metadata only. The LinkedIn button
opens the profile URL in the user's browser — no automated LinkedIn access.
"""

import asyncio
import logging
from io import StringIO

import pandas as pd
import streamlit as st

from app.config import get_settings
from app.db import init_db
from app.exceptions import AppError, AuthError, DatabaseError
from app.services.auth_service import (
    approve_account_request,
    is_admin,
    list_account_requests,
    list_users,
    login_user,
    reject_account_request,
    request_account,
    reset_user_password,
)
from app.services.history_service import list_searches, load_search, save_search
from app.services.pipeline import process_jd_file, process_jd_text
from app.utils.text_utils import display_name_from_title

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

st.set_page_config(
    page_title="AI Candidate Search",
    page_icon="🔍",
    layout="wide",
)


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
                "Name / Title": display_name_from_title(title),
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
        name = display_name_from_title(title)
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


def _render_result_section(result: dict) -> None:
    st.divider()
    st.subheader("Search Summary")
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("Searches used", result.get("searches_run", 0))
    summary_col2.metric("Unique profiles", result.get("candidates_found", 0))
    raw_count = result.get("raw_results_count")
    if raw_count is None:
        raw_count = len(result.get("search_results") or [])
    summary_col3.metric("Raw results", raw_count)

    with st.expander("JD Summary", expanded=True):
        _render_requirements(result.get("requirements") or {})

    with st.expander("Generated X-Ray Queries", expanded=False):
        _render_queries(result.get("queries") or [])

    candidates = result.get("candidates") or []
    st.subheader("Candidate Results")
    st.write(f"**{result.get('candidates_found', 0)} candidates found**")

    if candidates:
        df = _candidates_dataframe(candidates)
        st.dataframe(df, width="stretch", hide_index=True)

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


def _current_user() -> dict | None:
    user = st.session_state.get("user")
    if user and user.get("id") and user.get("username"):
        return user
    return None


def _logout() -> None:
    st.session_state.pop("user", None)
    st.session_state.pop("search_result", None)
    st.rerun()


def _render_login_page() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stSidebarCollapsedControl"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("AI Candidate Search")
    st.caption("Sign in if you already have access, or request an account for admin approval.")

    _, center, _ = st.columns([1, 2, 1])
    with center:
        login_tab, request_tab = st.tabs(["Log in", "Request access"])

        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary")
            if submitted:
                try:
                    user = login_user(username, password)
                    st.session_state["user"] = {"id": user.id, "username": user.username}
                    st.rerun()
                except AuthError as exc:
                    st.error(exc.message)

        with request_tab:
            st.caption("An admin must approve your request before you can log in.")
            with st.form("signup_form"):
                new_username = st.text_input("Choose a username")
                new_password = st.text_input("Choose a password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                requested = st.form_submit_button("Submit request", type="primary")
            if requested:
                if new_password != confirm:
                    st.error("Passwords do not match.")
                else:
                    try:
                        request_account(new_username, new_password)
                        st.success(
                            "Request submitted. You can log in after an admin approves it."
                        )
                    except AuthError as exc:
                        st.error(exc.message)


def _render_admin_dashboard(admin_username: str) -> None:
    st.caption("View users, reset passwords, and approve account requests. Passwords are never shown.")

    pending = list_account_requests(admin_username, status="pending")
    st.subheader(f"Pending requests ({len(pending)})")
    if not pending:
        st.info("No account requests waiting for review.")
    else:
        for item in pending:
            requested = item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "—"
            col_info, col_approve, col_reject = st.columns([4, 1, 1])
            with col_info:
                st.write(f"**{item.username}** · requested {requested}")
            with col_approve:
                if st.button("Approve", key=f"approve_{item.id}", type="primary"):
                    try:
                        approve_account_request(admin_username, item.id)
                        st.success(f"Approved {item.username}. They can log in now.")
                        st.rerun()
                    except AuthError as exc:
                        st.error(exc.message)
            with col_reject:
                if st.button("Reject", key=f"reject_{item.id}"):
                    try:
                        reject_account_request(admin_username, item.id)
                        st.warning(f"Rejected {item.username}.")
                        st.rerun()
                    except AuthError as exc:
                        st.error(exc.message)

    st.divider()
    st.subheader("Users")
    users = list_users(admin_username)
    if not users:
        st.info("No users found.")
        return

    rows = []
    for item in users:
        created = item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "—"
        rows.append(
            {
                "Username": item.username,
                "Role": "Admin" if is_admin(item.username) else "User",
                "Created": created,
                "Saved searches": item.search_count,
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.markdown("**Reset password**")
    reset_options = {f"{item.username} (id {item.id})": item.id for item in users}
    selected = st.selectbox("Select user", list(reset_options.keys()))
    with st.form("admin_reset_password"):
        new_password = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Reset password", type="secondary")
    if submitted:
        if new_password != confirm:
            st.error("Passwords do not match.")
        elif selected:
            try:
                username = reset_user_password(
                    admin_username,
                    reset_options[selected],
                    new_password,
                )
                st.success(f"Password reset for {username}.")
            except AuthError as exc:
                st.error(exc.message)


def _render_history_tab(user_id: int) -> None:
    summaries = list_searches(user_id)
    if not summaries:
        st.info("No saved searches yet. Run a search to store history and results here.")
        return

    options = {
        f"#{item.id} · {item.created_at.strftime('%Y-%m-%d %H:%M')} · "
        f"{item.filename or item.source} · {item.candidates_found} profiles": item.id
        for item in summaries
    }
    selected_label = st.selectbox("Saved searches", list(options.keys()))
    if not selected_label:
        return
    if st.button("Load selected search", type="secondary"):
        loaded = load_search(user_id, options[selected_label])
        if loaded is None:
            st.error("Could not load that search.")
            return
        st.session_state["search_result"] = loaded
        st.rerun()


def _render_search_tab(settings, serpapi_key: str, user_id: int) -> None:
    st.caption(
        "Upload a Job Description (PDF, Word, or text) or paste the JD to extract "
        "requirements, generate X-Ray queries, and discover LinkedIn profiles via Google search."
    )

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
        groq_configured = getattr(settings, "groq_configured", bool(getattr(settings, "groq_api_key", "").strip()))
        mistral_configured = getattr(settings, "mistral_configured", bool(getattr(settings, "mistral_api_key", "").strip()))
        llm_ready = getattr(settings, "llm_configured", False) or groq_configured or mistral_configured

        if not llm_ready:
            st.error(
                "Neither GROQ_API_KEY nor MISTRAL_API_KEY is configured. "
                "Add GROQ_API_KEY to Streamlit Cloud Secrets (Manage app → Settings → Secrets) "
                "or to your local .env file."
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
                    history_source = "file"
                else:
                    result = _run_pipeline_from_text(
                        pasted_text,
                        serpapi_key=serpapi_key.strip(),
                    )
                    history_source = "text"
                st.session_state["search_result"] = result
            except AppError as exc:
                logger.error("Pipeline error: %s", exc.message)
                st.error(exc.message)
                return
            except Exception:
                logger.exception("Unexpected UI error")
                st.error("Something went wrong. Please try again.")
                return

        try:
            save_search(user_id, result, source=history_source)
        except Exception:
            logger.exception("Failed to save search history")
            st.warning("Search completed, but history could not be saved.")


def main() -> None:
    try:
        init_db()
    except DatabaseError as exc:
        st.error(exc.message)
        st.info(
            "Set DATABASE_URL to a free Neon or Supabase Postgres URL, "
            "or use the default SQLite path for local runs."
        )
        return
    except Exception:
        logger.exception("Database initialization failed")
        st.error("Could not initialize the database. Check DATABASE_URL.")
        return

    user = _current_user()
    if user is None:
        _render_login_page()
        return

    settings = get_settings()

    st.title("AI Candidate Search")

    with st.sidebar:
        st.header("Account")
        st.write(f"Signed in as **{user['username']}**")
        if st.button("Log out"):
            _logout()

        st.divider()
        st.header("API Keys")
        groq_configured = getattr(settings, "groq_configured", bool(getattr(settings, "groq_api_key", "").strip()))
        mistral_configured = getattr(settings, "mistral_configured", bool(getattr(settings, "mistral_api_key", "").strip()))
        groq_model = getattr(settings, "groq_model", "openai/gpt-oss-120b")
        mistral_model = getattr(settings, "mistral_model", "mistral-small-latest")

        if groq_configured:
            st.write(f"LLM (Groq): ✅ `{groq_model}`")
        elif mistral_configured:
            st.write(f"LLM (Mistral): ✅ `{mistral_model}`")
        else:
            st.write("LLM: ❌ Not configured")
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

    if is_admin(user["username"]):
        admin_tab, search_tab, history_tab = st.tabs(
            ["Admin", "New Search", "Search History"]
        )
        with admin_tab:
            _render_admin_dashboard(user["username"])
        with search_tab:
            _render_search_tab(settings, serpapi_key, user["id"])
        with history_tab:
            _render_history_tab(user["id"])
    else:
        search_tab, history_tab = st.tabs(["New Search", "Search History"])
        with search_tab:
            _render_search_tab(settings, serpapi_key, user["id"])
        with history_tab:
            _render_history_tab(user["id"])

    result = st.session_state.get("search_result")
    if result:
        _render_result_section(result)


if __name__ == "__main__":
    main()
