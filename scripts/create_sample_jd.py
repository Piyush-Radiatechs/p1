"""Generate a sample Windchill JD PDF for manual testing."""

import fitz

SAMPLE_JD = """
Job Title: Windchill Developer / PLM Developer

Location: Texas (Dallas, Houston, Austin preferred)

Experience: 3-8 years

About the Role:
We are seeking an experienced Windchill Developer to support PLM implementation
and customization projects for our manufacturing clients.

Required Skills:
- PTC Windchill (PDMLink)
- Java development
- Windchill customization (OIR, workflows, lifecycle templates)
- Experience with Windchill upgrade and migration projects

Preferred Skills:
- Teamcenter or other PLM platforms
- REST API integration
- Oracle or SQL Server databases

Requirements:
- Bachelor's degree in Engineering or Computer Science
- Strong communication skills
- Must be authorized to work in the United States
- No interns or freshers — experienced hires only

Industry: Manufacturing / Aerospace
"""


def main():
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in SAMPLE_JD.strip().split("\n"):
        page.insert_text((72, y), line.strip())
        y += 16
    doc.save("sample_windchill_jd.pdf")
    doc.close()
    print("Created sample_windchill_jd.pdf")


if __name__ == "__main__":
    main()
