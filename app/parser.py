from __future__ import annotations

import re
from dataclasses import dataclass, field


IGNORED_KNOWN_USER_NAMES = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by",
    "for", "from", "he", "her", "his", "i", "if", "in", "is", "it",
    "me", "my", "of", "on", "or", "our", "she", "that", "the",
    "their", "them", "there", "this", "to", "was", "we", "who",
    "whom", "with", "you", "your", "authors", "copyright", "players",
    "tapestries", "muck", "please", "verify", "email", "password",
}

ALLOWED_WS_GENDERS = {
    "boy", "girl", "male", "female", "man", "woman", "herm",
    "neuter", "none", "unknown", "maleherm", "femaleherm",
}


@dataclass
class HighlightSpan:
    start: int
    end: int
    style: str
    tooltip: str = ""


@dataclass
class ParsedLine:
    raw: str
    spans: list[HighlightSpan] = field(default_factory=list)
    is_whisper: bool = False
    is_page: bool = False
    is_look_or_smell: bool = False
    mentions_self: bool = False
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class KeywordRule:
    keyword: str
    case_sensitive: bool = False
    whole_word: bool = True
    color: str = "#a8e6a3"


@dataclass
class KnownUserRule:
    username: str
    gender: str | None = None
    color: str | None = None


class LineParser:
    def __init__(self) -> None:
        self.my_username = ""
        self.known_users: dict[str, KnownUserRule] = {}
        self.keywords: list[KeywordRule] = []

    def set_username(self, username: str) -> None:
        self.my_username = username.strip()

    def set_keywords(self, rules: list[KeywordRule]) -> None:
        self.keywords = rules

    def set_known_users(self, known_users: dict[str, tuple[str | None, str | None] | str | None]) -> None:
        parsed: dict[str, KnownUserRule] = {}
        for username, value in known_users.items():
            clean_username = username.strip()
            if not self._is_valid_username(clean_username):
                continue
            if isinstance(value, tuple):
                gender, color = value
            else:
                gender, color = value, None
            parsed[clean_username] = KnownUserRule(username=clean_username, gender=gender, color=color)
        self.known_users = parsed

    def parse_outgoing_connect(self, text: str) -> str | None:
        match = re.match(r"^\s*(?:connect|co)\s+(\S+)\s+.+$", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def parse_line(self, line: str) -> ParsedLine:
        parsed = ParsedLine(raw=line)
        lower = line.lower()

        if self._is_received_whisper(lower):
            parsed.is_whisper = True
            parsed.spans.append(HighlightSpan(0, len(line), "whisper_received", "Received whisper"))
        elif self._is_sent_whisper(lower):
            parsed.is_whisper = True
            parsed.spans.append(HighlightSpan(0, len(line), "whisper_sent", "Sent whisper"))

        if self._is_received_page(lower):
            parsed.is_page = True
            parsed.spans.append(HighlightSpan(0, len(line), "page_received", "Received page"))
        elif self._is_sent_page(lower):
            parsed.is_page = True
            parsed.spans.append(HighlightSpan(0, len(line), "page_sent", "Sent page"))

        if self._is_looked_at(lower):
            parsed.is_look_or_smell = True
            parsed.spans.append(HighlightSpan(0, len(line), "looked_at", "Looked at you"))
        elif self._is_smelled(lower):
            parsed.is_look_or_smell = True
            parsed.spans.append(HighlightSpan(0, len(line), "smelled", "Smelled/sniffed you"))

        if self.my_username:
            pattern = rf"(?<!\w){re.escape(self.my_username)}(?!\w)"
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                parsed.mentions_self = True
                parsed.spans.append(HighlightSpan(match.start(), match.end(), "self", "Your name"))

        for rule in self.keywords:
            if not rule.keyword:
                continue
            pattern = re.escape(rule.keyword)
            if rule.whole_word:
                pattern = rf"(?<!\w){pattern}(?!\w)"
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            for match in re.finditer(pattern, line, flags=flags):
                parsed.matched_keywords.append(rule.keyword)
                parsed.spans.append(HighlightSpan(match.start(), match.end(), f"keyword:{rule.color}", rule.keyword))

        for username, rule in sorted(self.known_users.items(), key=lambda item: len(item[0]), reverse=True):
            if not username:
                continue
            pattern = rf"(?<!\w){re.escape(username)}(?!\w)"
            color = rule.color or ""
            gender = (rule.gender or "unknown").lower()
            style = f"user:{gender}:{color}" if color else f"user:{gender}"
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                parsed.spans.append(HighlightSpan(match.start(), match.end(), style, username))

        parsed.spans = self._dedupe_and_sort_spans(parsed.spans)
        return parsed

    def _is_received_whisper(self, lower: str) -> bool:
        return " whispers," in lower and " to you" in lower and not lower.startswith("you whisper")

    def _is_sent_whisper(self, lower: str) -> bool:
        return lower.startswith("you whisper") or lower.startswith("you whispered")

    def _is_received_page(self, lower: str) -> bool:
        return (
            (" pages:" in lower and ("/to you" in lower or " to you" in lower))
            or (" pages," in lower and " to you" in lower)
        ) and not lower.startswith("you page")

    def _is_sent_page(self, lower: str) -> bool:
        return lower.startswith("you page") or lower.startswith("you paged")

    def _is_looked_at(self, lower: str) -> bool:
        return (
            " looks at you" in lower
            or " looked at you" in lower
            or " is looking at you" in lower
        )

    def _is_smelled(self, lower: str) -> bool:
        return (
            " smells you" in lower
            or " smelled you" in lower
            or " sniffs you" in lower
            or " sniffed you" in lower
            or " smells at you" in lower
            or " sniffed at you" in lower
            or bool(re.match(r"^\[[^\]]+\s+sniffs the air nearby\.\]$", lower.strip()))
        )

    def _dedupe_and_sort_spans(self, spans: list[HighlightSpan]) -> list[HighlightSpan]:
        seen: set[tuple[int, int, str]] = set()
        result: list[HighlightSpan] = []
        for span in spans:
            key = (span.start, span.end, span.style)
            if key in seen:
                continue
            seen.add(key)
            result.append(span)
        result.sort(key=lambda s: (s.start, s.end))
        return result

    def is_ws_header(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("Name=") and "Gender" in stripped and "Species" in stripped

    def is_ws_total_line(self, line: str) -> bool:
        return line.strip().startswith("== Total:")

    def _is_valid_username(self, username: str) -> bool:
        if not username:
            return False
        lowered = username.lower()
        if lowered in IGNORED_KNOWN_USER_NAMES:
            return False
        if len(username) < 3:
            return False
        # MUCK names contain no spaces and may be styled with leading underscores.
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-'`]*", username))


    def is_who_line(self, line: str) -> bool:
        """Return True for standardized Tapestries who/whom room-list lines.

        Examples:
            The players awake here are Zephie, Salavin, Kippiko.
            The player awake here is Zephie.
            The sleepers here are SnickerDoodle, OrionBeauTucker, and Saunti.
        """
        stripped = line.strip()
        lowered = stripped.lower()
        return (
            lowered.startswith("the players awake here are ")
            or lowered.startswith("the player awake here is ")
            or lowered.startswith("the sleepers here are ")
            or lowered.startswith("the sleeper here is ")
            or bool(re.match(r"^only\s+[a-z_][a-z0-9_\-'`]*\s+is asleep here\.$", lowered))
            or lowered == "you are the only one awake here."
            or lowered == "there are no sleepers here."
        )

    def try_parse_who_line(self, line: str) -> list[tuple[str, str | None]]:
        """Parse usernames from standardized `who`/`whom` room-list sentences.

        This learns names only from the exact awake/sleeper list sentences, not
        from ordinary prose or from the less-regular `ws` table.
        """
        stripped = line.strip()
        lowered = stripped.lower()

        prefixes = (
            "the players awake here are ",
            "the player awake here is ",
            "the sleepers here are ",
            "the sleeper here is ",
        )

        names_text = ""
        for prefix in prefixes:
            if lowered.startswith(prefix):
                names_text = stripped[len(prefix):]
                break
        only_asleep_match = re.match(r"^only\s+([A-Za-z_][A-Za-z0-9_\-'`]*)\s+is asleep here\.$", stripped, flags=re.IGNORECASE)
        if only_asleep_match:
            names_text = only_asleep_match.group(1)

        if not names_text:
            return []

        names_text = names_text.strip().rstrip(".")
        names_text = re.sub(r"\s+and\s+", ", ", names_text, flags=re.IGNORECASE)

        users: list[tuple[str, str | None]] = []
        for piece in names_text.split(","):
            name = piece.strip()
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_\-'`]*)\b", name)
            if not match:
                continue
            username = match.group(1)
            if self._is_valid_username(username):
                users.append((username, None))

        deduped: dict[str, str | None] = {}
        for name, gender in users:
            deduped[name] = gender
        return list(deduped.items())

    def try_parse_ws_line(self, line: str) -> list[tuple[str, str | None]]:
        """
        Parse one line from the Tapestries `ws` table.

        IMPORTANT: call this only while a real `ws` table is active. It is
        intentionally strict so ordinary prose like "The wizards reserve..."
        does not get mistaken for a user listing.

        Example lines:
            Zephie             PF Boy      Kittiefox
            SnickerDoodle      -S- --- boy Flying Fox
            OrionBeauTucker    -S- --- Male Kangaroo
        """
        stripped = line.strip()
        if not stripped or self.is_ws_header(line) or self.is_ws_total_line(line):
            return []

        # Match the first table columns only. The species column may contain
        # spaces, so it is deliberately ignored after the gender field.
        match = re.match(
            r"^\s*([A-Za-z_][A-Za-z0-9_\-'`]*)\s+\S+\s+(?:(?:---|--)\s+)?([A-Za-z]+)\b",
            line,
        )
        if not match:
            return []

        name = match.group(1).strip()
        gender = match.group(2).strip().lower()

        if gender not in ALLOWED_WS_GENDERS:
            return []
        if not self._is_valid_username(name):
            return []

        return [(name, gender)]
