from unittest.mock import Mock, patch

from sortd.classifier import GeminiClassifier, HeuristicClassifier, OllamaClassifier, _parse_json


def test_heuristic_travel_classifier() -> None:
    result = HeuristicClassifier().classify("train ticket", "Train_Ticket_Sample.pdf")
    assert result.category == "Travel"
    assert result.confidence > 0.75


def test_training_text_is_not_misclassified_as_travel() -> None:
    text = "In this assignment, you will train a binary logistic regression model."
    result = HeuristicClassifier().classify(
        text, "Readability Analysis | SS26 Software Analysis.pdf"
    )
    assert result.category == "Documents"


BENCHMARK_CASES = [
    ("Flight Itinerary.pdf", "", "Travel"),
    ("boarding_pass.pdf", "", "Travel"),
    ("Train_Ticket_Sample.pdf", "", "Travel"),
    ("hotel-reservation.pdf", "", "Travel"),
    ("Visa Application.pdf", "", "Travel"),
    ("Airline Booking Confirmation.pdf", "", "Travel"),
    ("Assignment_02.pdf", "", "Education"),
    ("Lecture_04_AI.pdf", "", "Education"),
    ("Course_Syllabus.pdf", "", "Education"),
    ("Transcript of Records.pdf", "", "Education"),
    ("Semester Exam Results.pdf", "", "Education"),
    ("Lab Report.pdf", "", "Education"),
    ("Invoice_2026.pdf", "", "Finance"),
    ("Receipt_March.pdf", "", "Finance"),
    ("Bank Statement.pdf", "", "Finance"),
    ("Tax Return 2025.pdf", "", "Finance"),
    ("Payslip_November.pdf", "", "Finance"),
    ("Annual Report.pdf", "", "Finance"),
    ("Employment Contract.pdf", "", "Legal"),
    ("NDA Agreement.pdf", "", "Legal"),
    ("Lease Agreement.pdf", "", "Legal"),
    ("Court Order.pdf", "", "Legal"),
    ("Privacy Policy.pdf", "", "Legal"),
    ("Power of Attorney.pdf", "", "Legal"),
    ("Meeting Minutes.pdf", "", "Work"),
    ("Project Plan.pdf", "", "Work"),
    ("Business Proposal.pdf", "", "Work"),
    ("Status Report.pdf", "", "Work"),
    ("Resume.pdf", "", "Work"),
    ("Technical Specification.pdf", "", "Work"),
    (
        "Readability Analysis | SS26 Software Analysis.pdf",
        "In this assignment, you will train a binary logistic regression model. "
        "Submission due date. Task Description. The aim of this assignment is to "
        "evaluate readability.",
        "Education",
    ),
    ("Model Training Notes.pdf", "We train the model and evaluate its performance.", "Documents"),
    ("Training a model.pdf", "Training data and model training pipeline.", "Documents"),
    ("Project Report.pdf", "The report discusses flight itinerary classification.", "Work"),
    ("Invoice for a course.pdf", "Payment for the course registration.", "Finance"),
    ("University Annual Report.pdf", "Annual report on university finances.", "Documents"),
    ("Readability Analysis.pdf", "Methods and results for a readability analysis.", "Documents"),
    ("Research Notes.pdf", "Notes about a court judgment mentioned in class.", "Documents"),
    ("Meeting notes.pdf", "We discussed a train model in the meeting.", "Work"),
    ("Trip Summary.pdf", "A short personal journal about the weekend.", "Documents"),
    ("Payment Confirmation.pdf", "Payment confirmation for the order.", "Finance"),
    ("Anschreiben_Husam_Ali.pdf", "", "Work"),
    ("Bewerbung_DevOps.pdf", "", "Work"),
    ("Lebenslauf_Husam.pdf", "", "Work"),
    ("DB_Ticket_588910983066.pdf", "", "Travel"),
    ("Ex01_solutions_merged.pdf", "", "Education"),
    ("kurs_daf_a1_kurs_und_ubungsbuch.pdf", "", "Education"),
    ("Haseeb-Ramzan-LinkdIn.pdf", "", "Work"),
    ("Akademie-Deutsch-A1-Intensivlehrwerk.pdf", "", "Education"),
    ("Deutsch_A1_Textbook.pdf", "", "Education"),
    ("Bahn_Ticket.pdf", "", "Travel"),
]


def test_classifier_benchmark_matrix() -> None:
    classifier = HeuristicClassifier()
    mismatches = []
    for filename, text, expected in BENCHMARK_CASES:
        actual = classifier.classify(text, filename).category
        if actual != expected:
            mismatches.append((filename, expected, actual))
    assert not mismatches, mismatches


def test_train_ticket_phrase_is_still_classified_as_travel() -> None:
    result = HeuristicClassifier().classify("train ticket", "Train_Ticket_Sample.pdf")
    assert result.category == "Travel"


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
