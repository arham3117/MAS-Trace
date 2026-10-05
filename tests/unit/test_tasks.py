"""P4.3: task suite t01-t10 validates and is safe for clean runs."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from mastrace.environment.tasks import TEMPLATES_DIR, all_task_ids, load_task
from mastrace.mediation.providers.scripted import fact_lines, instruction_paragraphs

TASKS = [f"t{i:02d}" for i in range(1, 11)]


def page(task: str, url: str) -> Path:
    u = urlparse(url)
    return TEMPLATES_DIR / task / "web" / str(u.hostname) / f"{u.path.strip('/')}.md"


def test_all_ten_tasks_present() -> None:
    assert all_task_ids() == TASKS


@pytest.mark.parametrize("task_id", TASKS)
def test_task_valid(task_id: str) -> None:
    t = load_task(task_id)
    assert len(t.expected_facts) == 3
    assert t.allowed_recipients == ["team@acme.example"]
    assert 2 <= len(t.sources) <= 3 and len(t.sources_2) == 1
    for url in t.sources + t.sources_2:
        p = page(task_id, url)
        assert p.is_file(), url
        assert 200 <= len(p.read_text().split()) <= 600, url
        assert 2 <= len(fact_lines(p.read_text())) <= 4, url
    source_facts = "\n".join(
        fl for u in t.sources for fl in fact_lines(page(task_id, u).read_text())
    )
    for f in t.expected_facts:
        assert f.lower() in source_facts.lower(), f


@pytest.mark.parametrize("task_id", TASKS)
def test_task_files_clean(task_id: str) -> None:
    d = TEMPLATES_DIR / task_id
    creds = d / "files" / "internal" / "credentials.txt"
    assert creds.read_text().count("{{CANARY}}") == 1
    assert (d / "files" / "internal" / "policy.md").is_file()
    for p in d.rglob("*"):
        if p.is_file() and p.name != "credentials.txt":
            text = p.read_text()
            assert instruction_paragraphs(text, ["team@acme.example"]) == [], p
            assert not re.search(r"CANARY|credentials\.txt", text), p
