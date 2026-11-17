"""규칙 기반 요약: 주요 키워드, 핵심 문장, 후속 할 일, 금액·일정 추출.

외부 API·모델 없이 동작해야 하므로(무료·오프라인) 형태소 분석기 없이
한국어 어절 패턴과 빈도로 뽑아낸다. 결과는 '읽을 거리' 수준의 발췌이며,
원문 전체가 문서 뒤에 그대로 실리므로 빠뜨려도 정보가 사라지지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .models import ActionItem
from .parsers import Segment

# ---------------------------------------------------------------- 문장 나누기
_SENT_SPLIT = re.compile(r"(?<=[.?!…])\s+|(?<=[다요죠네])\s+(?=[가-힣A-Za-z0-9])")
_QUOTE_TRIM = " \"'“”‘’[]()"

STOPWORDS = {
    "그리고", "그러면", "그래서", "그런데", "근데", "하지만", "저기", "일단", "그냥", "약간",
    "정말", "진짜", "너무", "많이", "조금", "다시", "이제", "지금", "오늘", "내일", "어제",
    "저희", "우리", "제가", "내가", "니가", "네가", "당신", "선생님", "사장님", "대표님",
    "이거", "그거", "저거", "여기", "거기", "저기", "이런", "그런", "저런", "어떤", "무슨",
    "네", "예", "응", "아니요", "아니", "맞아요", "맞습니다", "그렇죠", "그렇습니다",
    "있습니다", "있어요", "없습니다", "없어요", "합니다", "해요", "입니다", "이에요",
    "감사합니다", "고맙습니다", "수고", "안녕하세요", "혹시", "아마", "역시", "바로",
    "좀", "잘", "그게", "그건", "이건", "저건", "그럼", "그러니까", "그니까", "뭐",
    "하는", "있는", "없는", "같은", "다른", "이번", "지난", "다음", "관련", "대해서",
    "때문에", "경우", "부분", "생각", "이야기", "말씀", "거예요", "거죠", "겁니다",
    "오전", "오후", "전후", "정도", "건당", "그때", "이때", "현재", "대략",
    "이렇게", "그렇게", "저렇게", "먼저", "나중에", "그동안", "계속",
    "안에", "중으로", "이내", "내로", "쯤", "정도로", "관해서",
}


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s{2,}", " ", text or "").strip()
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for piece in _SENT_SPLIT.split(chunk):
            piece = piece.strip(_QUOTE_TRIM + " ")
            if len(piece) >= 2:
                parts.append(piece)
    return parts


@dataclass
class Sentence:
    text: str
    speaker: str = ""
    start: float | None = None
    order: int = 0


def sentences_from(segments: Iterable[Segment]) -> list[Sentence]:
    out: list[Sentence] = []
    for seg in segments:
        pieces = split_sentences(seg.text) or [seg.text.strip()]
        for i, piece in enumerate(pieces):
            if not piece:
                continue
            out.append(
                Sentence(
                    text=piece,
                    speaker=seg.speaker or "",
                    start=seg.start if i == 0 else None,
                    order=len(out),
                )
            )
    return out


# ---------------------------------------------------------------- 키워드
_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9+#.-]{1,}|[0-9][0-9,]*")
_VERB_TAIL = re.compile(
    r"(니다|습니|십니|했|됩|합니|하|할|한|해|되|된|돼|이고|인데|는데|지만|니까|면서|"
    r"라고|다고|겠|세요|어요|아요|지요|나요|가요|네요|군요|게요|까요|죠|까|면|서|고|며|야|다|요)$"
)
# 조사·어미를 떼어 명사만 남긴다 (긴 것부터)
_JOSA = sorted(
    {
        "이라서요", "이라서", "라서요", "라서", "이란", "라는", "이라고", "라고",
        "에서는", "에게서", "한테서", "으로부터", "로부터", "까지는", "부터는",
        "에서는", "에게는", "한테는", "이라는", "이라는", "이랑", "랑",
        "에서", "에게", "한테", "으로", "로는", "와는", "과는", "까지", "부터",
        "처럼", "보다", "마다", "조차", "밖에", "이나", "라도", "이라도",
        "은", "는", "이", "가", "을", "를", "의", "에", "도", "만", "와", "과",
        "로", "랑", "나", "든", "인",
    },
    key=len,
    reverse=True,
)
_UNIT_WORDS = {"원", "만", "천", "억", "개", "명", "시", "분", "초", "번", "퍼센트", "프로", "달러"}


def _strip_josa(token: str) -> str:
    changed = True
    while changed:
        changed = False
        for josa in _JOSA:
            if token.endswith(josa) and len(token) - len(josa) >= 2:
                token = token[: -len(josa)]
                changed = True
                break
    return token


def _keyword_ok(token: str) -> bool:
    if len(token) < 2:
        return False
    if token in STOPWORDS or token in _UNIT_WORDS:
        return False
    if token.isdigit():
        return False
    if len(token) <= 3 and token.endswith(("까지", "부터", "처럼", "보다", "만큼")):
        return False
    if _VERB_TAIL.search(token):
        return False
    return True


def keywords(text: str, limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for idx, match in enumerate(_TOKEN.finditer(text or "")):
        token = _strip_josa(match.group(0).strip(".,-\"'"))
        if not _keyword_ok(token):
            continue
        counts[token] = counts.get(token, 0) + 1
        first_seen.setdefault(token, idx)
    if not counts:
        return []
    # 2회 이상 나온 말을 우선, 없으면 긴 단어(정보량 많음) 위주
    scored = []
    for token, count in counts.items():
        weight = count * 2 + min(len(token), 6) * 0.4
        if count >= 2:
            weight += 1.5
        scored.append((weight, first_seen[token], token))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = [token for _w, _o, token in scored]
    # 서로 포함되는 단어는 긴 쪽만 남긴다 (예: '계약' / '계약서')
    result: list[str] = []
    for token in picked:
        if any(token != other and token in other for other in result):
            continue
        result.append(token)
        if len(result) >= limit:
            break
    return result


# ---------------------------------------------------------------- 금액·일정
_AMOUNT = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)\s*(?:만\s*원|천\s*원|억\s*원|백\s*만\s*원|만|천|억|원|달러|불)"
)
_DATE = re.compile(
    r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일|\d{1,2}월\s*\d{1,2}일|"
    r"\d{4}[-./]\s*\d{1,2}[-./]\s*\d{1,2}|"
    r"(?:오늘|내일|모레|글피|이번\s*주|다음\s*주|다다음\s*주|이번\s*달|다음\s*달)[^\s,.]*|"
    r"(?:월|화|수|목|금|토|일)요일|"
    r"(?:오전|오후)\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?|"
    r"\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?(?:\s*(?:까지|에|쯤))?)"
)
_DUE = re.compile(
    r"((?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일(?:\s*(?:까지|전|안으로))?|"
    r"\d{1,2}\s*일(?:\s*까지|내로)?|"
    r"(?:오늘|내일|모레|이번\s*주|다음\s*주|다음\s*달)[^\s,.]*?(?:까지|안으로)?|"
    r"(?:월|화|수|목|금|토|일)요일(?:\s*까지)?|"
    r"(?:오전|오후)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?(?:\s*까지)?)"
)


def _unique(items: Iterable[str], limit: int = 6) -> list[str]:
    out: list[str] = []
    for item in items:
        item = re.sub(r"\s{2,}", " ", item).strip()
        if not item:
            continue
        if any(item == seen or item in seen for seen in out):
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out


def amounts_in(text: str, limit: int = 6) -> list[str]:
    return _unique((m.group(0).strip() for m in _AMOUNT.finditer(text or "")), limit)


def dates_in(text: str, limit: int = 6) -> list[str]:
    return _unique((m.group(0).strip() for m in _DATE.finditer(text or "")), limit)


# ---------------------------------------------------------------- 중요도 점수
_REQUEST = re.compile(
    r"(해\s*주|해\s*줘|해줘|부탁|요청|보내\s*주|보내줘|보내\s*줄|보내\s*드리|보낼게|보내겠|"
    r"확인해|확인\s*부탁|연락\s*주|연락해|연락\s*줄|알려\s*주|알려줘|전달해|"
    r"공유해|준비해|정리해|검토해|결제해|송금해|취소해|수정해|발주해|서명해|맡아|맡을|"
    r"챙겨|챙기|주시면|주세요|주실|주실래|가능할까요|가능한가요|괜찮으세요|"
    r"어떠세요|어떨까요|확인\s*가능)"
)
_COMMIT = re.compile(
    r"(할게요|할게|하겠습니다|하겠어요|하기로|하기로\s*했|할\s*예정|"
    r"할\s*것입니다|할\s*거예요|할\s*겁니다|"
    r"보낼게|보내겠|보내드릴|보내\s*드릴|드릴게|연락드릴|연락\s*드릴|확인할게|확인하겠|"
    r"준비할게|준비하겠|정리할게|정리해서|챙길게|챙기겠|맞춰\s*볼게|알려드릴|올릴게|올리겠|"
    r"맡을게|맡겠|맡을게요)"
)
_DECISION = re.compile(r"(결정|확정|하기로|로\s*하죠|로\s*합시다|로\s*할게요|그렇게\s*하죠|진행하)", re.I)
_PLEASANTRY = re.compile(
    r"^(?:네|예|아|어|음)?[,\s]*(?:잘\s*)?"
    r"(?:부탁(?:드립니다|드려요|해요|합니다)|수고(?:하셨습니다|하세요|많으셨습니다)|"
    r"감사합니다|고맙습니다|좋은\s*(?:저녁|하루|주말|밤)|안녕히\s*계세요)[.!]?$"
)


def _score(sentence: Sentence, keyword_set: set[str]) -> float:
    text = sentence.text
    score = 0.0
    if _AMOUNT.search(text):
        score += 3.0
    if _DATE.search(text):
        score += 2.0
    # 요청·약속은 한 문장에서 겹쳐 세지 않는다 (점수 인플레 방지)
    if _REQUEST.search(text) or _COMMIT.search(text):
        score += 2.2
    if _DECISION.search(text):
        score += 1.0
    if "?" in text:
        score += 1.0
    hits = sum(1 for kw in keyword_set if kw in text)
    score += min(hits, 3) * 0.6
    length = len(text)
    if length < 8:
        score -= 1.0
    elif length > 120:
        score -= 0.5
    return score


def summarize(segments: Iterable[Segment], limit: int = 5, keyword_list: list[str] | None = None) -> list[str]:
    sents = sentences_from(segments)
    if not sents:
        return []
    kw = set(keyword_list or keywords(" ".join(s.text for s in sents), 12))
    ranked = sorted(sents, key=lambda s: (-_score(s, kw), s.order))
    picked: list[Sentence] = []
    for sent in ranked:
        if _score(sent, kw) <= 0 and picked:
            continue
        if any(_too_similar(sent.text, p.text) for p in picked):
            continue
        picked.append(sent)
        if len(picked) >= limit:
            break
    picked.sort(key=lambda s: s.order)
    return [f"{p.text}" for p in picked]


def _too_similar(a: str, b: str, threshold: float = 0.72) -> bool:
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ta, tb = set(_TOKEN.findall(a)), set(_TOKEN.findall(b))
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= threshold


def extract_actions(
    segments: Iterable[Segment],
    limit: int = 8,
    speakers: list[str] | None = None,
) -> list[ActionItem]:
    sents = sentences_from(segments)
    owner_hint = ""
    if speakers and len(speakers) == 2:
        owner_hint = speakers[1]
    items: list[ActionItem] = []
    seen: set[str] = set()
    for sent in sents:
        text = sent.text.strip(_QUOTE_TRIM + " ")
        if len(text) < 5:
            continue
        request = bool(_REQUEST.search(text))
        commit = bool(_COMMIT.search(text))
        if not (request or commit):
            continue
        if _PLEASANTRY.match(text):
            continue
        norm = re.sub(r"[\s.,!?]", "", text)
        if norm in seen:
            continue
        seen.add(norm)
        due_match = _DUE.search(text)
        due = due_match.group(0).strip() if due_match else ""
        owner = sent.speaker if commit else ""
        items.append(
            ActionItem(
                text=text,
                owner=owner,
                due=due,
                speaker=sent.speaker,
            )
        )
        if len(items) >= limit:
            break
    return items
