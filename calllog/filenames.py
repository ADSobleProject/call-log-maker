"""파일명에서 상대방/제목·날짜·시각을 뽑아낸다.

삼성 통화 녹음 기본 이름 예:
  통화 녹음 홍길동_261117_210000.m4a
  통화녹음_01012345678_20231117_210000.m4a
  녹음_20261117_1430.m4a
  KakaoTalk_Audio_20261117_143000.m4a
  회의 2026-11-17 14.30.m4a
  통화 녹음 2026. 11. 17. 오후 9:00.m4a
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_TITLE = "통화 녹음"

# 파일명 앞뒤에 붙는 군더더기 (긴 것부터 지운다)
_PREFIXES = [
    "삼성 통화 녹음", "통화 녹음", "통화녹음", "음성 녹음", "음성녹음", "새 녹음", "새녹음",
    "voice recorder", "voice recording", "voice memo", "call recording", "call recorder",
    "kakaotalk_audio", "kakaotalk", "recording", "record", "audio", "voice", "memo",
    "통화", "녹음", "음성", "회의록", "회의", "녹취",
]
_STOP_TITLES = {"", "-", "_", "new", "untitled", "제목 없음", "무제", "녹음", "통화", "음성"}

_DATE_TIME_PATTERNS: list[re.Pattern[str]] = [
    # 20261117_210000 / 20261117-2100-30 / 2026.11.17 21.00.00
    re.compile(
        r"(?<!\d)(?P<y>20\d{2})(?P<mo>\d{2})(?P<d>\d{2})"
        r"[_\-\s.]*(?P<h>\d{2})[:\-.]?(?P<mi>\d{2})[:\-.]?(?P<s>\d{2})(?!\d)"
    ),
    # 20261117_2100
    re.compile(
        r"(?<!\d)(?P<y>20\d{2})(?P<mo>\d{2})(?P<d>\d{2})"
        r"[_\-\s.]*(?P<h>\d{2})[:\-.]?(?P<mi>\d{2})(?!\d)"
    ),
    # 261117_210000
    re.compile(
        r"(?<!\d)(?P<y>\d{2})(?P<mo>\d{2})(?P<d>\d{2})"
        r"[_\-\s.]*(?P<h>\d{2})[:\-.]?(?P<mi>\d{2})[:\-.]?(?P<s>\d{2})(?!\d)"
    ),
    # 261117_2100
    re.compile(
        r"(?<!\d)(?P<y>\d{2})(?P<mo>\d{2})(?P<d>\d{2})"
        r"[_\-\s.]*(?P<h>\d{2})[:\-.]?(?P<mi>\d{2})(?!\d)"
    ),
    # 2026-11-17 21:00 / 2026. 11. 17. 오후 9:00 / 2026/11/17 21.00
    re.compile(
        r"(?<!\d)(?P<y>20\d{2})\s*[-./]\s*(?P<mo>\d{1,2})\s*[-./]\s*(?P<d>\d{1,2})"
        r"(?:\.)?[T\s_]*"
        r"(?:(?P<ampm>오전|오후|am|pm)\s*)?"
        r"(?P<h>\d{1,2})\s*[:.]\s*(?P<mi>\d{2})"
        r"(?:\s*[:.]\s*(?P<s>\d{2}))?"
    ),
    # 2026년 11월 17일 오후 9시 30분
    re.compile(
        r"(?<!\d)(?P<y>20\d{2})년\s*(?P<mo>\d{1,2})월\s*(?P<d>\d{1,2})일"
        r"(?:\s*(?P<ampm>오전|오후)\s*)?(?:\s*(?P<h>\d{1,2})시(?:\s*(?P<mi>\d{1,2})분?)?)?"
    ),
]

_DATE_ONLY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?<!\d)(?P<y>20\d{2})(?P<mo>\d{2})(?P<d>\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>20\d{2})\s*[-./]\s*(?P<mo>\d{1,2})\s*[-./]\s*(?P<d>\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>20\d{2})년\s*(?P<mo>\d{1,2})월\s*(?P<d>\d{1,2})일"),
]


@dataclass
class NameInfo:
    """파일명 해석 결과."""

    title: str
    when: datetime | None = None
    time_known: bool = False
    matched: str = ""          # 제목에서 덜어낸 날짜/시각 문자열
    title_from_name: bool = False


def _year(value: str) -> int:
    y = int(value)
    if len(value) == 2:
        return 2000 + y if y < 70 else 1900 + y
    return y


def _ampm(hour: int, ampm: str | None) -> int:
    if not ampm:
        return hour
    token = ampm.lower()
    if token in {"오후", "pm"} and hour < 12:
        return hour + 12
    if token in {"오전", "am"} and hour == 12:
        return 0
    return hour


def _build(match: re.Match[str], with_time: bool) -> datetime | None:
    groups = match.groupdict()
    try:
        year = _year(groups.get("y", ""))
        month = int(groups.get("mo", 1))
        day = int(groups.get("d", 1))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        if with_time:
            hour = _ampm(int(groups.get("h") or 0), groups.get("ampm"))
            minute = int(groups.get("mi") or 0)
            second = int(groups.get("s") or 0)
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return None
        else:
            hour = minute = second = 0
        return datetime(year, month, day, hour, minute, second)
    except (TypeError, ValueError):
        return None


def _find_when(stem: str) -> tuple[datetime | None, bool, str]:
    """(일시, 시각까지 있는지, 파일명에서 덜어낼 문자열)"""
    for pattern in _DATE_TIME_PATTERNS:
        for match in pattern.finditer(stem):
            when = _build(match, with_time=True)
            # '20261117' 처럼 날짜만 있는데 시/분 그룹이 0으로 잡힌 경우도 통과하므로
            # 시·분이 실제로 적혀 있었는지 확인한다.
            if when is None:
                continue
            has_time = bool(match.groupdict().get("h"))
            return when, has_time, match.group(0)
    for pattern in _DATE_ONLY_PATTERNS:
        for match in pattern.finditer(stem):
            when = _build(match, with_time=False)
            if when is not None:
                return when, False, match.group(0)
    return None, False, ""


def find_datetime(text: str) -> tuple[datetime | None, bool, str]:
    """문자열 안의 날짜·시각을 찾는다 (파일명·문서 머리말 공용)."""
    return _find_when(text)


def clean_title(text: str, max_len: int = 40) -> str:
    """제목 후보 문자열을 사람이 읽기 좋게 다듬는다."""
    title = text.strip()
    title = re.sub(r"\.(m4a|mp3|wav|ogg|flac|aac|wma|opus|webm|m4b|txt)$", "", title, flags=re.I)
    title = re.sub(r"[\u200b\ufeff]", "", title)
    # 앞쪽 군더더기 제거 (통화 녹음, Voice Recorder ...)
    changed = True
    while changed:
        changed = False
        low = title.lower().lstrip(" _-–—.")
        for prefix in _PREFIXES:
            if low.startswith(prefix):
                cut = len(title) - len(low) + len(prefix)
                rest = title[cut:]
                # '회의'처럼 제목 자체일 수 있는 말은 뒤에 다른 글자가 있을 때만 지운다
                if prefix in {"회의", "녹취", "통화", "녹음", "음성"} and rest.strip(" _-–—."):
                    pass
                elif prefix in {"회의", "녹취"} and not rest.strip(" _-–—."):
                    continue
                title = rest
                changed = True
                break
    # 괄호·구분자 정리
    title = re.sub(r"^[\s_\-–—.,:\[\]()]+", "", title)
    title = re.sub(r"[\s_\-–—.,:\[\]()]+$", "", title)
    title = re.sub(r"[_\s]{2,}", " ", title).replace("_", " ")
    title = re.sub(r"\s{2,}", " ", title)
    # '김지훈_2' 처럼 중복 표시로 붙은 꼬리 숫자, 숫자만 남은 제목은 버린다
    title = re.sub(r"\s\d{1,2}$", "", title)
    if re.fullmatch(r"[\d\s\-–—.]+", title or "") and len(re.sub(r"\D", "", title)) in (6, 8):
        title = ""  # 날짜만 남은 제목
    title = re.sub(r"^[_\-–—]+", "", title)
    if title.lower() in _STOP_TITLES:
        title = ""
    if len(title) > max_len:
        title = title[:max_len].rstrip(" _-–—.,")
    return title


def parse_filename(path: str | Path, max_len: int = 40) -> NameInfo:
    """파일명에서 제목과 일시를 뽑는다. 날짜가 없으면 파일 수정 시각을 쓴다."""
    p = Path(path)
    stem = p.stem
    when, time_known, matched = _find_when(stem)

    title_source = stem
    if matched:
        title_source = stem.replace(matched, " ", 1)
    title = clean_title(title_source, max_len=max_len)

    from_mtime = False
    if when is None:
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            when = mtime.replace(second=0, microsecond=0)
            time_known = True
            from_mtime = True
        except OSError:
            when = None
    elif not time_known:
        # 날짜만 있으면 파일 수정 시각의 '시:분'을 빌려 온다 (같은 날일 때만)
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime.date() == when.date():
                when = when.replace(hour=mtime.hour, minute=mtime.minute)
        except OSError:
            pass

    if not title:
        title = DEFAULT_TITLE
    return NameInfo(
        title=title,
        when=when,
        time_known=time_known and not from_mtime,
        matched=matched,
        title_from_name=bool(title and title != DEFAULT_TITLE),
    )


_ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def safe_filename(text: str, max_len: int = 40) -> str:
    name = _ILLEGAL.sub(" ", text or "")
    name = re.sub(r"\s{2,}", " ", name).strip(" ._-")
    if len(name) > max_len:
        name = name[:max_len].rstrip(" ._-")
    return name or DEFAULT_TITLE
