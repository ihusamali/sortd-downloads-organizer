"""Pluggable semantic classification backends."""

import json
import os
import re
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
    """Offline keyword classifier."""

    def classify(self, text: str, filename: str) -> Classification:
        content = f"{filename} {text}".lower()
        rules = [
            ("Travel", ("ticket", "boarding", "train station", "railway", "flight", "itinerary")),
            ("Education", ("lecture", "course", "assignment", "university", "student")),
            ("Finance", ("invoice", "receipt", "statement", "payment")),
            ("Legal", ("contract", "agreement", "court", "legal")),
            ("Work", ("proposal", "meeting", "project", "report")),
        ]
        category, confidence = "Documents", 0.42
        for candidate, words in rules:
            if any(re.search(rf"\b{re.escape(word)}\b", content) for word in words):
                category, confidence = candidate, 0.83
                break
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
