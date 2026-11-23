"""ONB-06: Aadhaar, PAN and bank account numbers are removed from chat; ordinary numbers are left alone."""
import pytest

from readiness.pii import redact, refusal_message


@pytest.mark.parametrize("text,kinds,secret", [
    ("My PAN is ABCDE1234F", ["PAN"], "ABCDE1234F"),
    ("pan abcde1234f", ["PAN"], "abcde1234f"),
    ("Aadhaar 2345 6789 0123", ["AADHAAR"], "2345 6789 0123"),
    ("aadhaar: 234567890123", ["AADHAAR"], "234567890123"),
    ("uid 2345-6789-0123 please", ["AADHAAR"], "2345-6789-0123"),
    ("Aadhaar 1234 5678 9012", ["AADHAAR"], "1234 5678 9012"),          # invalid start, but labelled
    ("4567 8901 2345", ["AADHAAR"], "4567 8901 2345"),                  # bare 12 digits starting 2-9
    ("my bank account no. 123456789012345 at SBI", ["BANK_ACCOUNT"], "123456789012345"),
    ("a/c 50100123456789", ["BANK_ACCOUNT"], "50100123456789"),
    ("Account number: 3456 7812 9012 34", ["BANK_ACCOUNT"], "3456 7812 9012 34"),
    ("ref 501001234567890", ["BANK_ACCOUNT"], "501001234567890"),       # 11-18 digit run, no context
])
def test_redacted(text, kinds, secret):
    clean, found = redact(text)
    assert found == kinds and secret not in clean and "[REDACTED" in clean


@pytest.mark.parametrize("text", [
    "The loan is Rs 1,42,00,000",
    "Call me on 9876543210",
    "Requested amount 20000000",
    "CASE-001 and EMP-014",
    "Employee ID 1234-5678-9012-3456 is wrong",
    "ref 2345 6789 0123 4567",
    "Training expired on 2026-01-15",
])
def test_left_alone(text):
    assert redact(text) == (text, [])


def test_several_kinds_in_one_message():
    clean, found = redact("PAN ABCDE1234F and a/c 50100123456789 and aadhar 2345 6789 0123")
    assert found == ["PAN", "BANK_ACCOUNT", "AADHAAR"]
    assert clean.count("[REDACTED") == 3


def test_refusal_names_what_was_removed():
    text = refusal_message(["PAN", "AADHAAR"])
    assert "PAN" in text and "Aadhaar" in text and "HR portal" in text
