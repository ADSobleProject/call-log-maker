"""텍스트 변환본(.txt) 파싱.

삼성 음성 녹음 / 갤럭시 AI / 클로바 노트 / 에이닷 등에서 내보낸 txt 는
화자 라벨과 타임스탬프 표기가 조금씩 다르다. 아래처럼 너그럽게 받아 준다.

    00:00
    화자 1
    안녕하세요, 잘 지내셨어요?

    00:05 화자 2: 네 덕분에 잘 지냈습니다.

    [00:12] 참석자 1 - 그럼 내일 오후 세 시에 봬요.
    Speaker 2: OK, see you then.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .filenames import clean_title, find_datetime

_TIMESTAMP = re.compile(
    r"^[\[\(]?(?P<h>\d{1,3}):(?P<mi>\d{2})(?::(?P<s>\d{2}))?(?:[.,]\d{1,3})?[\]\)]?$"
)
_TS_ANY = r"(?P<ts>\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)"
_SPEAKER = r"(?:화자|참석자|발화자|스피커|Speaker|SPEAKER)\s*\d+"
_NAME_LABEL = r"[^\s:：\[\]\(\)\{\}]{1,12}"

_TS_SPEAKER = re.compile(
    rf"^[\[\(]?{_TS_ANY}[\]\)]?\s*[,\-–·|]?\s*(?P<spk>{_SPEAKER})\s*[:：\-–]?\s*(?P<text>.*)$",
    re.I,
)
_SPEAKER_LINE = re.compile(
    rf"^[\[\(]?(?P<spk>{_SPEAKER})[\]\)]?\s*[:：\-–]?\s*(?P<text>.*)$", re.I
)
_NAME_LINE = re.compile(
    rf"^[\[\(]?(?P<spk>{_NAME_LABEL})[\]\)]?\s*[:：]\s*(?P<text>.+)$"
)
_META_LINE = re.compile(
    r"^(?P<key>녹음\s*일시|통화\s*일시|통화\s*날짜|녹음\s*날짜|일시|날짜|시각|시간|"
    r"제목|파일명|파일|상대방|통화\s*상대|상대|연락처|전화번호|번호|"
    r"길이|재생\s*시간|소요\s*시간|통화\s*시간|녹음\s*시간|작성일|변환일|모델)"
    r"\s*[:：]\s*(?P<value>.+)$"
)
_META_KEYS_SKIP_SPEAKER = {
    "금액", "날짜", "시간", "제목", "파일", "길이", "상대방", "장소", "내용",
    "비고", "요약", "메모", "일시", "연락처", "전화번호", "번호", "모델",
}
_HEADER_NOISE = re.compile(
    r"^(음성\s*녹음|통화\s*녹음|녹음|음성\s*인식|자동\s*변환|텍스트\s*변환|"
    r"STT|Transcript|Transcription|AI\s*음성\s*인식)\s*$",
    re.I,
)
_DURATION_TEXT = re.compile(
    r"(?:(?P<h>\d{1,2})\s*시간)?\s*(?:(?P<m>\d{1,3})\s*분)?\s*(?:(?P<s>\d{1,3})\s*초)?"
)
_DURATION_LINE = re.compile(
    r"^(?:길이|재생\s*시간|소요\s*시간|통화\s*시간|녹음\s*시간|duration|length)\s*[:：]?\s*"
    r"(?P<value>\d{1,2}:\d{2}(?::\d{2})?|\d{1,2}\s*시간.*|\d{1,3}\s*분.*|\d{1,3}\s*초.*)$",
    re.I,
)
_TITLE_LINE = re.compile(
    r"^(?P<kind>통화\s*녹음|음성\s*녹음|녹음|통화|회의\s*녹음)\s*[-–—:|]\s*(?P<title>.+)$"
)


@dataclass
class Segment:
    """한 사람이 한 번에 말한 덩어리 (또는 문단)."""

    text: str
    speaker: str | None = None
    start: float | None = None

    def clone(self) -> "Segment":
        return Segment(text=self.text, speaker=self.speaker, start=self.start)


@dataclass
class ParsedText:
    segments: list[Segment] = field(default_factory=list)
    title: str = ""
    when: datetime | None = None
    time_known: bool = False
    duration_sec: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def speakers(self) -> list[str]:
        seen: list[str] = []
        for seg in self.segments:
            if seg.speaker and seg.speaker not in seen:
                seen.append(seg.speaker)
        return seen

    @property
    def full_text(self) -> str:
        return "\n".join(seg.text for seg in self.segments if seg.text.strip())

    @property
    def char_count(self) -> int:
        return sum(len(seg.text) for seg in self.segments)


def parse_timestamp(text: str) -> float | None:
    """'00:12'(분:초), '1:02:03'(시:분:초) → 초."""
    match = _TIMESTAMP.match(text.strip())
    if not match:
        return None
    h = int(match.group("h"))
    m = int(match.group("mi"))
    s = match.group("s")
    if s is None:
        # 두 토막이면 '분:초'로 읽는다 (00:05 = 5초)
        return h * 60 + m
    return h * 3600 + m * 60 + int(s)


def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(round(seconds))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_duration(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    as_time = _TIMESTAMP.match(text)
    if as_time:
        return parse_timestamp(text)
    match = _DURATION_TEXT.search(text)
    if not match:
        return None
    h = int(match.group("h") or 0)
    m = int(match.group("m") or 0)
    s = int(match.group("s") or 0)
    if h == m == s == 0:
        return None
    return h * 3600 + m * 60 + s


def normalize_speaker(label: str) -> str:
    label = label.strip().strip("[](){}").strip()
    label = re.sub(r"\s{2,}", " ", label)
    low = label.lower()
    if low.startswith("speaker"):
        digits = re.sub(r"\D", "", label)
        return f"화자 {digits}" if digits else "화자"
    return label


def parse_text_file(path: str | Path) -> ParsedText:
    """txt 파일을 읽어 화자별 발화 목록으로 만든다."""
    p = Path(path)
    raw = _read_text(p)
    return parse_text(raw, source_name=p.name)


def _read_text(path: Path) -> str:
    return _decode_text_bytes(path.read_bytes())


def _guess_utf16(data: bytes) -> str | None:
    """널바이트가 한쪽 바이트 자리에만 몰려 있으면 UTF-16 으로 본다.

    화자 1 의 UTF-16LE = 54 D6 90 C7 20 00 31 00 처럼 홀수 자리에 0 이 온다.
    """
    sample = data[:8192]
    sample = sample[: len(sample) - len(sample) % 2]
    if len(sample) < 16:
        return None
    pairs = len(sample) // 2
    zeros_even = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
    zeros_odd = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
    minimum = max(2, -(-pairs * 5 // 100))
    if zeros_odd >= minimum and zeros_even <= zeros_odd * 0.1:
        return "utf-16-le"
    if zeros_even >= minimum and zeros_odd <= zeros_even * 0.1:
        return "utf-16-be"
    return None


def _decode_text_bytes(data: bytes) -> str:
    """텍스트 파일 바이트 → 문자열.

    삼성 통화녹음·음성녹음이 내보내는 UTF-16LE 파일을 cp949 로 읽어
    '화자 1' 이 'Tĭ 1' 처럼 깨지던 문제를 막는다.
    BOM → (BOM 이 없으면) 널바이트 배열 → UTF-8 → CP949/EUC-KR → 손실 UTF-8 순.
    """
    if not data:
        return ""

    if data.startswith(b"\xff\xfe") and not data.startswith(b"\xff\xfe\x00\x00"):
        order = ["utf-16"]  # BOM 이 있으면 바이트 순서를 알아서 잡는다
    elif data.startswith(b"\xfe\xff"):
        order = ["utf-16"]
    elif data.startswith(b"\xef\xbb\xbf"):
        order = ["utf-8-sig", "utf-8"]
    else:
        guessed = _guess_utf16(data)
        order = ([guessed, "utf-16"] if guessed else []) + ["utf-8", "cp949", "euc-kr"]

    text = None
    for encoding in order:
        try:
            text = data.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if text is None:
        text = data.decode("utf-8", errors="replace")

    return text.replace("\ufeff", "").replace("\x00", "")


def parse_text(raw: str, source_name: str = "") -> ParsedText:
    text = (raw or "").replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    result = ParsedText()
    segments: list[Segment] = []

    current: Segment | None = None
    pending_speaker: str | None = None
    pending_time: float | None = None
    para_break = True
    labels_used = False

    def add(speaker: str | None, timestamp: float | None, body: str) -> None:
        nonlocal current, para_break
        body = re.sub(r"\s{2,}", " ", body).strip()
        if not body:
            return
        if current is not None and not para_break and current.speaker == speaker:
            current.text = f"{current.text} {body}".strip()
            if current.start is None and timestamp is not None:
                current.start = timestamp
            return
        current = Segment(text=body, speaker=speaker, start=timestamp)
        segments.append(current)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            para_break = True
            current = None
            continue

        # 1) 문서 머리말의 날짜/시각 줄
        when, time_known, _matched = find_datetime(line)
        if len(line) <= 40 and (when is not None or _HEADER_NOISE.match(line)):
            if when is not None and result.when is None:
                result.when = when
                result.time_known = time_known
                continue
            if _HEADER_NOISE.match(line):
                continue

        # 2) '제목: ...', '길이: 03:21' 같은 정보 줄
        duration_line = _DURATION_LINE.match(line)
        if duration_line:
            duration = parse_duration(duration_line.group("value"))
            if duration and result.duration_sec is None:
                result.duration_sec = duration
            continue
        title_line = _TITLE_LINE.match(line)
        if title_line and not result.title:
            candidate = clean_title(title_line.group("title"), max_len=40)
            if candidate:
                result.title = candidate
                continue
        meta = _META_LINE.match(line)
        if meta:
            key = re.sub(r"\s+", "", meta.group("key"))
            value = meta.group("value").strip()
            if "일시" in key or "날짜" in key:
                parsed, known, _ = find_datetime(value)
                if parsed and result.when is None:
                    result.when = parsed
                    result.time_known = known
            elif key in {"길이", "재생시간", "소요시간", "통화시간", "녹음시간"}:
                duration = parse_duration(value)
                if duration and result.duration_sec is None:
                    result.duration_sec = duration
            elif key in {"제목", "상대방", "통화상대", "상대"}:
                title = clean_title(value, max_len=40)
                if title and not result.title:
                    result.title = title
            elif key in {"파일", "파일명"}:
                pass
            elif key in {"시간", "시각"}:
                parsed, known, _ = find_datetime(value)
                if parsed and result.when is None:
                    result.when = parsed
                    result.time_known = known
            continue

        # 3) '00:05 화자 2: ...'
        combo = _TS_SPEAKER.match(line)
        if combo:
            pending_time = parse_timestamp(combo.group("ts"))
            speaker = normalize_speaker(combo.group("spk"))
            labels_used = True
            body = combo.group("text")
            if body.strip():
                add(speaker, pending_time, body)
                pending_time = None
                para_break = False
            else:
                pending_speaker = speaker
            continue

        # 4) '화자 1' / '화자 1: ...' / '화자 1 (00:01)'
        speaker_line = _SPEAKER_LINE.match(line)
        if speaker_line:
            speaker = normalize_speaker(speaker_line.group("spk"))
            labels_used = True
            body = speaker_line.group("text")
            stamp = parse_timestamp(body) if body.strip() else None
            if stamp is not None:
                # 삼성 통화녹음은 화자 라벨 줄 끝에 상대 시각을 붙여 내보낸다
                pending_speaker = speaker
                pending_time = stamp
                continue
            if body.strip():
                add(speaker, pending_time, body)
                pending_time = None
                pending_speaker = None
                para_break = False
            else:
                pending_speaker = speaker
            continue

        # 5) 타임스탬프만 있는 줄
        timestamp = parse_timestamp(line)
        if timestamp is not None:
            pending_time = timestamp
            continue

        # 6) '[홍길동] ...' / '홍길동: ...' (일반 이름 라벨)
        name_line = _NAME_LINE.match(line)
        if name_line and name_line.group("spk").strip() not in _META_KEYS_SKIP_SPEAKER:
            speaker = normalize_speaker(name_line.group("spk"))
            labels_used = True
            add(speaker, pending_time, name_line.group("text"))
            pending_time = None
            pending_speaker = None
            para_break = False
            continue

        # 7) 보통 문장 — 화자 라벨이 쓰인 파일이면 앞사람 말이 이어지는 것으로 본다
        speaker = pending_speaker or (current.speaker if labels_used and current is not None else None)
        add(speaker, pending_time, line)
        pending_speaker = None
        pending_time = None
        para_break = False

    result.segments = _merge_segments(segments)
    if not result.segments:
        result.warnings.append("읽을 수 있는 대화 내용을 찾지 못했습니다.")
    return result


def _merge_segments(segments: list[Segment]) -> list[Segment]:
    """같은 화자가 이어서 말한 짧은 토막들을 한 문단으로 합친다."""
    merged: list[Segment] = []
    for seg in segments:
        text = re.sub(r"\s{2,}", " ", seg.text).strip()
        if not text:
            continue
        if merged and merged[-1].speaker and merged[-1].speaker == seg.speaker:
            prev = merged[-1]
            if not prev.text.endswith(("?", "!", ".", "…", ",")) and len(prev.text) > 20:
                prev.text = f"{prev.text}. {text}".strip()
            else:
                prev.text = f"{prev.text} {text}".strip()
            continue
        merged.append(Segment(text=text, speaker=seg.speaker, start=seg.start))
    return merged
