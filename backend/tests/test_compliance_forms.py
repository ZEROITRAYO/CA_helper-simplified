"""Every form's content in content/forms/ reads cleanly (compliance.get_form_content)."""

import pytest

from app.compliance import get_form_content
from app.models import FormCode


@pytest.mark.parametrize("form_code", [form.value for form in FormCode])
def test_every_form_has_its_texts_and_checklist(form_code):
    body = get_form_content(form_code)

    assert body["form_code"] == form_code
    assert body["status"] in ("TODO", "DRAFT", "DONE")
    assert body["explanation"].startswith("# ")  # the front matter is gone
    assert body["instructions"].startswith("# ")
    assert "<!--" not in body["explanation"] + body["instructions"]  # writers' notes are gone
    assert len(body["checklist"]) > 0
    keys = [entry["key"] for entry in body["checklist"]]
    assert len(keys) == len(set(keys))  # keys are unique within a form
    assert any(entry["required"] for entry in body["checklist"])
