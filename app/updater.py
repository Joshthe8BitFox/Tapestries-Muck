from __future__ import annotations

import platform
import re

RELEASES_URL = "https://github.com/Joshthe8BitFox/Tapestries-Muck/releases"
LATEST_RELEASE_API = "https://api.github.com/repos/Joshthe8BitFox/Tapestries-Muck/releases/latest"


def version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value.lstrip("vV").split("-", 1)[0])
    return tuple(int(number) for number in numbers) if numbers else (0,)


def is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def select_asset(assets: list[dict]) -> dict | None:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_terms = {"windows": ("windows", "win"), "darwin": ("macos", "mac", "osx"), "linux": ("linux",)}.get(system, ())
    arch_terms = ("arm64", "aarch64") if machine in {"arm64", "aarch64"} else ("x64", "x86_64", "amd64")
    ranked = []
    for asset in assets:
        name = asset.get("name", "").lower()
        if not any(term in name for term in os_terms):
            continue
        score = 2 if any(term in name for term in arch_terms) else 1
        ranked.append((score, asset))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None
