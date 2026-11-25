from unittest.mock import Mock, patch

from sortd.classifier import GeminiClassifier, HeuristicClassifier, OllamaClassifier, _parse_json


def test_heuristic_travel_classifier() -> None:
    result = HeuristicClassifier().classify("train ticket", "Train_Ticket_Sample.pdf")
    assert result.category == "Travel"
    assert result.confidence > 0.75


def test_parse_structured_response() -> None:
    result = _parse_json(
        '{"category":"Work","suggested_filename":"2026-01-01_Report.pdf","confidence":0.8}'
    )
    assert result.category == "Work"


def test_ollama_backend_parses_response() -> None:
    response = Mock()
    body = '{"category":"Work","suggested_filename":"2026-01-01_Report.pdf","confidence":0.9}'
    response.json.return_value = {"response": body}
    with patch("sortd.classifier.httpx.post", return_value=response):
        result = OllamaClassifier("http://local", "test").classify("report", "report.pdf")
    assert result.category == "Work"


def test_gemini_backend_parses_response() -> None:
    response = Mock()
    body = '{"category":"Work","suggested_filename":"2026-01-01_Report.pdf","confidence":0.9}'
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": body}]}}]}
    with patch("sortd.classifier.httpx.post", return_value=response):
        result = GeminiClassifier("api-key").classify("report", "report.pdf")
    assert result.category == "Work"


def test_gemini_requires_key() -> None:
    try:
        GeminiClassifier("").classify("report", "report.pdf")
    except ValueError as error:
        assert "GOOGLE_API_KEY" in str(error)
    else:
        raise AssertionError("missing key should fail")
