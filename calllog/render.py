"""통화록을 .md 와 .docx 로 그린다."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import CallDocument
from .parsers import format_timestamp

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def _when_label(when: datetime | None) -> str:
    if not when:
        return "일시 미상"
    return f"{when:%Y-%m-%d} ({WEEKDAYS[when.weekday()]}) {when:%H:%M}"


def _duration_label(seconds: float | None) -> str:
    if not seconds:
        return "-"
    total = int(round(seconds))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h}시간 {m:02d}분 {s:02d}초"
    if m:
        return f"{m}분 {s:02d}초"
    return f"{s}초"


def _speaker_label(doc: CallDocument, speaker: str | None) -> str:
    if not speaker:
        return "통화"
    return speaker


def _info_rows(doc: CallDocument) -> list[tuple[str, str]]:
    speakers = ", ".join(doc.speakers) if doc.speakers else "구분 없음"
    engine = doc.engine or "-"
    rows = [
        ("일시", _when_label(doc.when)),
        ("상대방/제목", doc.title),
        ("원본 파일", doc.source_name),
        ("소요 시간", _duration_label(doc.duration_sec)),
        ("변환 방식", f"{doc.mode} ({engine})" if engine and engine != "-" else doc.mode),
        ("화자", speakers),
        ("분량", f"{doc.utterance_count}개 발화 · {doc.char_count:,}자"),
        ("작성", doc.created_at.strftime("%Y-%m-%d %H:%M")),
    ]
    return rows


# ---------------------------------------------------------------- Markdown
def to_markdown(doc: CallDocument) -> str:
    lines: list[str] = []
    lines.append(f"# 📞 {doc.heading()}")
    lines.append("")
    if doc.mode.startswith("음성"):
        lines.append("> 음성 파일을 무료 로컬 음성인식(faster-whisper)으로 옮긴 통화록입니다.")
    else:
        lines.append("> 이미 텍스트로 변환된 기록을 정리한 통화록입니다.")
    lines.append("")

    lines.append("## 📋 기본 정보")
    lines.append("")
    lines.append("| 항목 | 내용 |")
    lines.append("| --- | --- |")
    for key, value in _info_rows(doc):
        safe = str(value).replace("|", "\\|")
        lines.append(f"| {key} | {safe} |")
    lines.append("")

    lines.append("## 🔑 주요 키워드")
    lines.append("")
    if doc.keywords:
        lines.append(" · ".join(f"`{k}`" for k in doc.keywords))
    else:
        lines.append("_추출된 키워드가 없습니다._")
    lines.append("")

    lines.append("## 📌 핵심 요약")
    lines.append("")
    if doc.summary:
        for i, sentence in enumerate(doc.summary, 1):
            lines.append(f"{i}. {sentence}")
    else:
        lines.append("_요약할 문장을 찾지 못했습니다. 아래 전체 대화 기록을 확인해 주세요._")
    lines.append("")

    if doc.amounts or doc.dates:
        lines.append("## 💰 금액·일정")
        lines.append("")
        if doc.amounts:
            lines.append(f"- **금액**: {' · '.join(doc.amounts)}")
        if doc.dates:
            lines.append(f"- **일정**: {' · '.join(doc.dates)}")
        lines.append("")

    lines.append("## ✅ 후속 할 일")
    lines.append("")
    if doc.actions:
        for item in doc.actions:
            extra = []
            if item.owner:
                extra.append(item.owner)
            if item.due:
                extra.append(item.due)
            suffix = f"  _({' · '.join(extra)})_" if extra else ""
            lines.append(f"- [ ] {item.text}{suffix}")
    else:
        lines.append("_뚜렷한 요청·약속 문장이 없습니다._")
    lines.append("")

    lines.append("## 💬 전체 대화 기록")
    lines.append("")
    if not doc.segments:
        lines.append("_대화 내용이 없습니다._")
    for seg in doc.segments:
        stamp = format_timestamp(seg.start)
        head = f"**{_speaker_label(doc, seg.speaker)}**"
        if stamp:
            head += f" `{stamp}`"
        lines.append(head)
        lines.append("")
        lines.append(seg.text)
        lines.append("")

    if doc.warnings:
        lines.append("---")
        lines.append("")
        lines.append("## ⚠️ 참고")
        lines.append("")
        for warning in doc.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*call-log-maker 로 자동 생성 · 내용은 원본 기록을 확인해 주세요.*")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- DOCX
def _set_korean_font(style, name: str = "맑은 고딕") -> None:  # pragma: no cover - 렌더링 세부
    from docx.oxml.ns import qn
    from docx.shared import Pt

    style.font.name = name
    style.font.size = Pt(10.5)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)


def _shade(cell, hex_color: str = "F2F4F7") -> None:  # pragma: no cover - 렌더링 세부
    from docx.oxml.ns import qn

    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.makeelement(qn("w:shd"), {qn("w:fill"): hex_color})
    tc_pr.append(shd)


def write_docx(doc: CallDocument, path: str | Path) -> Path:  # pragma: no cover - 파일 생성
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    document = Document()
    _set_korean_font(document.styles["Normal"])
    for name in ("Heading 1", "Heading 2"):
        try:
            _set_korean_font(document.styles[name])
        except KeyError:
            pass
    for section in document.sections:
        section.top_margin = section.top_margin
        section.bottom_margin = section.bottom_margin

    title = document.add_heading(f"📞 {doc.heading()}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    note = document.add_paragraph()
    note_run = note.add_run(
        "음성 파일을 무료 로컬 음성인식(faster-whisper)으로 옮긴 통화록입니다."
        if doc.mode.startswith("음성")
        else "이미 텍스트로 변환된 기록을 정리한 통화록입니다."
    )
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    document.add_heading("📋 기본 정보", level=1)
    rows = _info_rows(doc)
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for key, value in rows:
        cells = table.add_row().cells
        cells[0].text = ""
        cells[1].text = ""
        run = cells[0].paragraphs[0].add_run(key)
        run.bold = True
        cells[1].paragraphs[0].add_run(str(value))
        _shade(cells[0])
    table.columns[0].width = None

    document.add_heading("🔑 주요 키워드", level=1)
    if doc.keywords:
        p = document.add_paragraph()
        p.add_run(" · ".join(doc.keywords)).bold = True
    else:
        document.add_paragraph("추출된 키워드가 없습니다.")

    document.add_heading("📌 핵심 요약", level=1)
    if doc.summary:
        for sentence in doc.summary:
            document.add_paragraph(sentence, style="List Number")
    else:
        document.add_paragraph("요약할 문장을 찾지 못했습니다. 아래 전체 대화 기록을 확인해 주세요.")

    if doc.amounts or doc.dates:
        document.add_heading("💰 금액·일정", level=1)
        if doc.amounts:
            p = document.add_paragraph(style="List Bullet")
            p.add_run("금액: ").bold = True
            p.add_run(" · ".join(doc.amounts))
        if doc.dates:
            p = document.add_paragraph(style="List Bullet")
            p.add_run("일정: ").bold = True
            p.add_run(" · ".join(doc.dates))

    document.add_heading("✅ 후속 할 일", level=1)
    if doc.actions:
        for item in doc.actions:
            p = document.add_paragraph()
            run = p.add_run("☐ ")
            run.font.name = "Segoe UI Symbol"
            p.add_run(item.text)
            extra = [x for x in (item.owner, item.due) if x]
            if extra:
                tail = p.add_run(f"  ({' · '.join(extra)})")
                tail.italic = True
                tail.font.size = Pt(9)
                tail.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    else:
        document.add_paragraph("뚜렷한 요청·약속 문장이 없습니다.")

    document.add_heading("💬 전체 대화 기록", level=1)
    if not doc.segments:
        document.add_paragraph("대화 내용이 없습니다.")
    for seg in doc.segments:
        stamp = format_timestamp(seg.start)
        head = document.add_paragraph()
        speaker_run = head.add_run(_speaker_label(doc, seg.speaker))
        speaker_run.bold = True
        if stamp:
            time_run = head.add_run(f"  {stamp}")
            time_run.font.size = Pt(8.5)
            time_run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        body = document.add_paragraph(seg.text)
        body.paragraph_format.space_after = Pt(8)

    if doc.warnings:
        document.add_heading("⚠️ 참고", level=1)
        for warning in doc.warnings:
            document.add_paragraph(warning, style="List Bullet")

    footer = document.add_paragraph()
    run = footer.add_run("call-log-maker 로 자동 생성 · 내용은 원본 기록을 확인해 주세요.")
    run.italic = True
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))
    return path


def write_markdown(doc: CallDocument, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(doc), encoding="utf-8")
    return path
