"""
Minimal LLM Analysis — Stage 2 (BRD Section 5).

This is the ONLY LLM call in the entire pipeline. It reads the resume
once and extracts a structured candidate profile. Every later stage
(query building, search, scraping, filtering, date-range filtering,
duplicate removal, relevance scoring) is pure Python — no further model
calls, per the BRD's "minimum LLM/API usage" requirement.
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings


llm = ChatGoogleGenerativeAI(
    model=settings.MODEL_NAME,
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=settings.TEMPERATURE,
)


prompt = ChatPromptTemplate.from_template(
    """
You are a technical recruiter analyzing a resume ONE TIME to build a
structured candidate profile. This is the only analysis pass — be
thorough and accurate since no further AI calls will refine this data.

Resume:
{resume}

Return ONLY valid JSON in this exact format:

{{
    "role": "",
    "experience_level": "",
    "location": "",
    "employment_type": "",
    "skills": [],
    "search_queries": []
}}

Rules:

- "role": the candidate's most suitable job title (e.g. "Python Developer").
- "experience_level": one of "Internship", "Entry Level", "Junior",
  "Mid Level", "Senior" based on years of experience / seniority in the resume.
- "location": candidate's city/country if stated, else "Remote".
- "employment_type": candidate's apparent preference if stated
  (Full-time / Part-time / Contract / Internship / Remote), else "Full-time".
- "skills": the most important technical skills/technologies only
  (max 10), exactly as named in the resume (e.g. "Python", "FastAPI",
  "Django", "PostgreSQL").
- "search_queries": 5-7 baseline job-search query seeds (these will be
  further optimized by Python logic afterward — keep them simple,
  containing role + top skills).
- Do not invent skills, experience, or location not present in the resume.
- Do not explain your answer. Return JSON only.
"""
)


parser = JsonOutputParser()

analyzer_chain = prompt | llm | parser
