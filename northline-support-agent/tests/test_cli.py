import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_answers_a_shipping_question():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "support_agent.cli",
            "--mock",
            "How long does standard shipping take?",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "You: How long does standard shipping take?" in completed.stdout
    assert "4-7 business days" in completed.stdout
    assert "--- ticket" not in completed.stdout
