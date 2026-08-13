# AI-Powered JD → LinkedIn Candidate Search Tool

Upload a Job Description PDF, extract structured requirements with Mistral, generate Google X-Ray queries targeting `site:linkedin.com/in/`, search via SerpApi, and discover publicly surfaced LinkedIn profile URLs from search-engine metadata.

## Compliance Boundary

This tool **does NOT**:

- Log into LinkedIn
- Scrape or crawl LinkedIn profile pages
- Use browser automation against LinkedIn
- Collect profile data by visiting LinkedIn URLs automatically

This tool **only**:

1. Generates search queries
2. Sends queries to SerpApi (Google)
3. Inspects returned search-engine metadata (title, link, snippet)
4. Identifies URLs matching `linkedin.com/in/...`
5. Displays discovered URLs for manual review by the recruiter

## Architecture

```text
PDF JD → PyMuPDF → Mistral JD Extraction → JobRequirements
       → X-Ray Query Generator → SerpApi/Google → LinkedIn URL Filter → FastAPI
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your API keys:

```env
MISTRAL_API_KEY=your_mistral_key
MISTRAL_MODEL=mistral-small-latest
SERPAPI_KEY=your_serpapi_key
MAX_QUERIES_PER_JD=5
MAX_RESULTS_PER_QUERY=10
```

## Run Streamlit UI

```powershell
streamlit run streamlit_app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).

## Run FastAPI

```powershell
uvicorn app.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

## API: POST /search-candidates

**Request** (multipart/form-data):

```powershell
curl -X POST "http://127.0.0.1:8000/search-candidates" `
  -F "file=@windchill_jd.pdf"
```

**Response** (abbreviated):

```json
{
  "filename": "windchill_jd.pdf",
  "requirements": {
    "job_titles": ["Windchill Developer", "PLM Developer"],
    "technical_skills": ["Windchill", "PDMLink", "Java"],
    "locations": ["Texas", "Dallas"],
    "experience": {"min_years": 3, "max_years": 8}
  },
  "queries": ["site:linkedin.com/in/ ..."],
  "searches_run": 5,
  "search_results": [{"position": 1, "title": "...", "link": "...", "snippet": "..."}],
  "candidates_found": 12,
  "candidates": [{"linkedin_url": "https://www.linkedin.com/in/...", "title": "...", "snippet": "..."}]
}
```

## Streamlit Cloud secrets

GitHub Actions secrets are **not** used by Streamlit Cloud.

On the deployed app, open **Manage app → Settings → Secrets** and add:

```toml
MISTRAL_API_KEY = "your_mistral_key"
MISTRAL_MODEL = "mistral-small-latest"
MAX_QUERIES_PER_JD = 5
MAX_RESULTS_PER_QUERY = 10
GOOGLE_DOMAIN = "google.com"
GOOGLE_GL = "us"
GOOGLE_HL = "en"
```

Then reboot the app. SerpApi can stay as a sidebar input, or you can also add `SERPAPI_KEY` here.

## Run Tests

```powershell
pytest
```

## Known Limitations (V1)

- No OCR for scanned PDFs
- No LinkedIn profile scraping
- Search quality depends on Google index coverage
- Match scores are sourcing signals only — not hiring decisions

## Next Steps

- Expanded deployment docs
- Optional FastAPI-only mode for headless integrations
