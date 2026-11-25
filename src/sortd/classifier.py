"""Pluggable semantic classification backends."""

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel, Field


class Classification(BaseModel):
    """Validated classifier response."""

    category: str
    suggested_filename: str
    confidence: float = Field(ge=0, le=1)


class BaseClassifier(Protocol):
    """Backend interface."""

    def classify(self, text: str, filename: str) -> Classification: ...


class HeuristicClassifier:
    """Offline classifier using title-weighted phrase signals.

    A neutral Documents result is preferred when the available text only mentions a
    specialized topic in passing. A single incidental word in page text is not enough.
    """

    SIGNALS: dict[str, tuple[str, ...]] = {
        "Travel": (
            "boarding pass",
            "flight itinerary",
            "travel itinerary",
            "train ticket",
            "plane ticket",
            "flight ticket",
            "hotel reservation",
            "travel booking",
            "booking confirmation",
            "db ticket",
            "bahn ticket",
            "fahrkarte",
            "airline",
            "departure time",
            "arrival time",
            "railway",
            "passport",
            "visa application",
            "travel insurance",
        ),
        "Education": (
            "assignment",
            "coursework",
            "lecture",
            "course syllabus",
            "syllabus",
            "university",
            "student",
            "transcript of records",
            "semester",
            "exam results",
            "examination",
            "homework",
            "exercise sheet",
            "lab report",
            "module handbook",
            "course materials",
            "professor",
            "grade report",
            "task description",
            "submission due date",
            "courses",
            "textbook",
            "workbook",
            "coursebook",
            "lehrwerk",
            "intensivlehrwerk",
            "language course",
            "kurs",
            "ubungsbuch",
        ),
        "Finance": (
            "invoice",
            "receipt",
            "bank statement",
            "account statement",
            "tax return",
            "tax assessment",
            "payslip",
            "pay slip",
            "balance sheet",
            "payment confirmation",
            "annual report",
            "expense report",
            "billing statement",
            "vat invoice",
        ),
        "Legal": (
            "contract",
            "agreement",
            "court order",
            "court judgment",
            "legal notice",
            "non disclosure agreement",
            "lease agreement",
            "rental agreement",
            "terms and conditions",
            "privacy policy",
            "power of attorney",
            "employment agreement",
            "settlement agreement",
        ),
        "Work": (
            "meeting minutes",
            "project plan",
            "project proposal",
            "business proposal",
            "status report",
            "quarterly report",
            "performance review",
            "job application",
            "cover letter",
            "curriculum vitae",
            "resume",
            "statement of work",
            "work order",
            "business plan",
            "technical specification",
            "meeting notes",
            "project report",
            "anschreiben",
            "bewerbung",
            "lebenslauf",
            "coverletter",
            "cv",
            "linkedin",
            "linkdin",
        ),
    }

    def classify(self, text: str, filename: str) -> Classification:
        """Classify using document-title cues and multiple content cues."""

        def normalize(value: str) -> str:
            ascii_text = unicodedata.normalize("NFKD", value.lower().replace("ß", "ss"))
            ascii_text = "".join(char for char in ascii_text if not unicodedata.combining(char))
            return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()

        title = normalize(Path(filename).stem)
        body = normalize(text[:1000])
        scores: dict[str, float] = {}
        for category, phrases in self.SIGNALS.items():
            score = 0.0
            if category == "Education" and re.search(r"\bex[0-9]{1,3}\b", title):
                score += 3.0
            for phrase in phrases:
                normalized_phrase = normalize(phrase)
                if f" {normalized_phrase} " in f" {title} ":
                    score += 3.0
                elif f" {normalized_phrase} " in f" {body} ":
                    score += 0.8
            scores[category] = score

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        category, score = ranked[0]
        second_score = ranked[1][1]
        # Require either a clear title cue or multiple independent body cues.
        # If categories compete, return the neutral folder instead of guessing.
        if score < 1.5 or score - second_score < 0.6:
            category, confidence = "Documents", 0.92
        else:
            confidence = min(0.99, 0.75 + score * 0.05)

        clean = re.sub(r"[^A-Za-z0-9]+", "_", Path(filename).stem).strip("_") or "Document"
        return Classification(
            category=category,
            suggested_filename=f"{date.today():%Y-%m-%d}_{clean}.pdf",
            confidence=confidence,
        )


class OllamaClassifier:
    """Local Ollama API classifier."""

    def __init__(self, url: str, model: str) -> None:
        self.url, self.model = url, model

    def classify(self, text: str, filename: str) -> Classification:
        prompt = _prompt(text, filename)
        response = httpx.post(
            self.url,
            json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60,
        )
        response.raise_for_status()
        return _parse_json(str(response.json()["response"]))


class GeminiClassifier:
    """Google Gemini generateContent backend."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash") -> None:
        self.api_key, self.model = api_key or os.getenv("GOOGLE_API_KEY", ""), model

    def classify(self, text: str, filename: str) -> Classification:
        if not self.api_key:
            raise ValueError("Set GOOGLE_API_KEY to use the Gemini classifier")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        response = httpx.post(
            url,
            params={"key": self.api_key},
            json={"contents": [{"parts": [{"text": _prompt(text, filename)}]}]},
            timeout=60,
        )
        response.raise_for_status()
        output = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_json(str(output))


def _prompt(text: str, filename: str) -> str:
    return (
        "Classify this document. Return only JSON with category, suggested_filename, confidence. "
        "Filename should be YYYY-MM-DD_Descriptive_Name.pdf. Confidence is 0 to 1. "
        f"Current date: {date.today().isoformat()}. Input filename: {filename}. Text: {text[:1000]}"
    )


def _parse_json(raw: str) -> Classification:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    return Classification.model_validate(json.loads(cleaned))


def make_classifier(
    kind: str, ollama_url: str, ollama_model: str, gemini_model: str
) -> BaseClassifier:
    """Construct a configured provider."""
    if kind == "ollama":
        return OllamaClassifier(ollama_url, ollama_model)
    if kind == "gemini":
        return GeminiClassifier(model=gemini_model)
    if kind == "heuristic":
        return HeuristicClassifier()
    raise ValueError(f"Unknown classifier: {kind}")
