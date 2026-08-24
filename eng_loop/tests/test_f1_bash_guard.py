"""F1.6 — C4: bash command guard (unit-level pattern matrix).

check_bash_command is the single gate before any shell execution. It must
block catastrophic commands and let normal development commands through.
"""

from __future__ import annotations

import pytest

from eng_loop.tools.sandbox import check_bash_command

SB = {"enabled": True, "root": "/proj", "allow_out_of_root": False}


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf $HOME",
        "rm -r -f /etc",
        "rm -fr /*",
        "rm --no-preserve-root -rf /",
        "sudo rm -rf /",
        "rm -rf / && echo done",
        "rm -rf ~ | tee /dev/null",
        ":(){ :|: & };:",
        "mkfs.ext4 /dev/sda1",
        "mkfs /dev/sdb",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        "echo garbage > /dev/sda",
        "cat /dev/urandom > /dev/nvme0n1",
        # RISK_KEYWORDS (work-item risk applied to commands — substring, so even
        # grep/echo of a keyword is blocked by design; opt out via sandbox.enabled)
        "chmod 777 /etc/shadow",
        "drop database production",
        "TRUNCATE TABLE users",
        "production deploy now",
        "cat ~/.aws/credentials",
        "grep -rn 'credentials' src/ -l",
        "echo 'production deploy' >> notes.txt",
    ],
)
def test_blocked_commands(command: str) -> None:
    result = check_bash_command(command, SB)
    assert result is not None, f"expected block for: {command}"
    assert "BLOCKED" in result


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "echo hello",
        "pytest -q",
        "npm install",
        "pip install requests",
        "git status",
        "git commit -m 'fix: thing'",
        "python -m pytest tests/ -x",
        "rm -rf ./build",
        "rm -rf dist",
        "rm -f output.txt",
        "rm file.txt",
        "npm run deploy:staging",
        "chmod 644 app.conf",
        "python script.py --truncate-table-flag",
        "chown root file.txt",
    ],
)
def test_allowed_commands(command: str) -> None:
    assert check_bash_command(command, SB) is None, f"should be allowed: {command}"


def test_disabled_sandbox_never_blocks() -> None:
    assert check_bash_command("rm -rf /", None) is None
    assert check_bash_command("rm -rf /", {"enabled": False, "root": "/x"}) is None


def test_case_insensitive() -> None:
    assert check_bash_command("RM -RF /", SB) is not None
    assert check_bash_command("CHMOD 777 /etc", SB) is not None
    assert check_bash_command("ChMod 644 app.conf", SB) is None
