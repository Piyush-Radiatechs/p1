"""Demo: extract PDF text and generate X-Ray queries without API keys."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.jd import ExperienceRange, JobRequirements
from app.services.pdf_parser import extract_pdf_text
from app.services.query_generator import generate_xray_queries

# Simulated Mistral output for Windchill JD validation
WINDCHILL_REQUIREMENTS = JobRequirements(
    job_titles=["Windchill Developer", "PLM Developer", "Windchill Consultant"],
    technical_skills=["Windchill", "PDMLink", "Java", "OIR", "Workflows"],
    preferred_skills=["Teamcenter", "REST API"],
    locations=["Texas", "Dallas", "Houston", "Austin"],
    experience=ExperienceRange(min_years=3, max_years=8),
    exclusions=["intern", "fresher"],
    industries=["Manufacturing", "Aerospace"],
)


def main():
    pdf_path = Path("sample_windchill_jd.pdf")
    if pdf_path.exists():
        text = extract_pdf_text(pdf_path.read_bytes())
        print(f"--- Extracted JD text ({len(text)} chars) ---")
        print(text[:500], "...\n")

    queries = generate_xray_queries(WINDCHILL_REQUIREMENTS, max_queries=5)
    print("--- Generated X-Ray Queries ---")
    for i, q in enumerate(queries, 1):
        print(f"\nQuery {i}:\n{q}")


if __name__ == "__main__":
    main()
