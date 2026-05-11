from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil


@dataclass(frozen=True)
class ShellLaunchSpec:
    argv: list[str]
    family: str
    shell_name: str


def _resolve_windows_shell(*, interactive: bool) -> tuple[str, str]:
    candidates: list[tuple[str, str]] = []
    if not interactive:
        candidates.extend(
            [
                ("bash.exe", "bash"),
                ("bash", "bash"),
            ]
        )
    candidates.extend(
        [
            ("pwsh", "powershell"),
            ("powershell.exe", "powershell"),
        ]
    )
    if not interactive:
        candidates.append(("cmd.exe", "cmd"))
    for binary, family in candidates:
        resolved = shutil.which(binary)
        if resolved:
            return resolved, family
    fallback = "cmd.exe" if not interactive else "powershell.exe"
    return fallback, "cmd" if fallback == "cmd.exe" else "powershell"


def build_exec_shell_launch(command: str) -> ShellLaunchSpec:
    normalized = str(command or "").strip()
    if os.name != "nt":
        return ShellLaunchSpec(
            argv=["bash", "-lc", normalized],
            family="bash",
            shell_name="bash",
        )
    binary, family = _resolve_windows_shell(interactive=False)
    if family == "bash":
        return ShellLaunchSpec(
            argv=[binary, "-lc", normalized],
            family=family,
            shell_name=Path(binary).name,
        )
    if family == "cmd":
        return ShellLaunchSpec(
            argv=[binary, "/d", "/s", "/c", normalized],
            family=family,
            shell_name=Path(binary).name,
        )
    return ShellLaunchSpec(
        argv=[binary, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", normalized],
        family=family,
        shell_name=Path(binary).name,
    )


def build_terminal_shell_launch(script_path: Path) -> ShellLaunchSpec:
    if os.name != "nt":
        return ShellLaunchSpec(
            argv=["bash", "--noprofile", "--rcfile", str(script_path), "-i"],
            family="bash",
            shell_name="bash",
        )
    binary, family = _resolve_windows_shell(interactive=True)
    if family == "powershell":
        return ShellLaunchSpec(
            argv=[binary, "-NoLogo", "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            family=family,
            shell_name=Path(binary).name,
        )
    return ShellLaunchSpec(
        argv=[binary, "/q", "/k", str(script_path)],
        family=family,
        shell_name=Path(binary).name,
    )
