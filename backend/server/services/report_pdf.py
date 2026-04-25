"""PDF assessment reports: shared by HTTP routes and scripts/generate_report.py."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, BinaryIO, Dict, List, Union

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger("bkp-server.report_pdf")

# ---------------------------------------------------------------------------
# Register a Unicode TrueType font that covers Cyrillic, Latin, etc.
# Lookup order: Windows Fonts → Linux system fonts → bundled fallback.
# ---------------------------------------------------------------------------
_FONT_SEARCH_PATHS = [
    # Windows
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    # Debian/Ubuntu (fonts-dejavu-core)
    "/usr/share/fonts/truetype/dejavu",
    # Alpine / generic
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
]

_VARIANTS = {
    "DejaVuSans":           "DejaVuSans.ttf",
    "DejaVuSans-Bold":      "DejaVuSans-Bold.ttf",
    "DejaVuSans-Oblique":   "DejaVuSans-Oblique.ttf",
    "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf",
}


def _find_font(filename: str) -> str:
    for d in _FONT_SEARCH_PATHS:
        candidate = os.path.join(d, filename)
        if os.path.isfile(candidate):
            return candidate
    return ""


_FONT_REGISTERED = False
_FONT_FAMILY = "Helvetica"


def _ensure_font() -> None:
    """Register DejaVuSans family once; fall back to Helvetica (no Cyrillic)."""
    global _FONT_REGISTERED, _FONT_FAMILY
    if _FONT_REGISTERED:
        return
    _FONT_REGISTERED = True

    regular = _find_font("DejaVuSans.ttf")
    if not regular:
        logger.warning(
            "DejaVuSans.ttf not found in %s – Cyrillic will NOT render. "
            "Install fonts-dejavu-core (apt) or DejaVu Sans (Windows).",
            _FONT_SEARCH_PATHS,
        )
        return

    for name, fname in _VARIANTS.items():
        path = _find_font(fname)
        if path:
            pdfmetrics.registerFont(TTFont(name, path))

    pdfmetrics.registerFontFamily(
        "DejaVuSans",
        normal="DejaVuSans",
        bold="DejaVuSans-Bold",
        italic="DejaVuSans-Oblique",
        boldItalic="DejaVuSans-BoldOblique",
    )
    _FONT_FAMILY = "DejaVuSans"
    logger.info("Registered DejaVuSans font family from %s", os.path.dirname(regular))


def _make_styles():
    _ensure_font()
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReportTitle", parent=base["Title"],
        fontName=_FONT_FAMILY, fontSize=18, spaceAfter=12,
    )
    heading = ParagraphStyle(
        "ReportHeading", parent=base["Heading2"],
        fontName=_FONT_FAMILY, fontSize=14, spaceAfter=8,
    )
    body = ParagraphStyle(
        "ReportBody", parent=base["Normal"],
        fontName=_FONT_FAMILY, fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "ReportSmall", parent=base["Normal"],
        fontName=_FONT_FAMILY, fontSize=8, textColor=colors.grey,
    )
    return title, heading, body, small


TITLE_STYLE: ParagraphStyle
HEADING_STYLE: ParagraphStyle
BODY_STYLE: ParagraphStyle
SMALL_STYLE: ParagraphStyle


def _init_styles() -> None:
    global TITLE_STYLE, HEADING_STYLE, BODY_STYLE, SMALL_STYLE
    TITLE_STYLE, HEADING_STYLE, BODY_STYLE, SMALL_STYLE = _make_styles()


_init_styles()


async def load_individual_data(session_id: str) -> Dict[str, Any]:
    from sqlalchemy import select

    from server.db import ensure_schema_initialized, make_session
    from server.models.assessment import Assessment
    from server.models.assessment_criterion import AssessmentCriterion
    from server.models.assessment_score import AssessmentScore
    from server.models.interviewee import Interviewee
    from server.models.interview_session import InterviewSession
    from server.models.message import Message
    from server.models.position import Position

    from sqlalchemy import or_

    await ensure_schema_initialized()
    async with make_session() as db:
        session = await db.scalar(select(InterviewSession).where(InterviewSession.id == session_id))
        if not session:
            raise ValueError(f"Session {session_id} not found")

        interviewee = await db.scalar(select(Interviewee).where(Interviewee.id == session.interviewee_id))
        position = None
        if interviewee and interviewee.position_id:
            position = await db.scalar(select(Position).where(Position.id == interviewee.position_id))

        assessment = await db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        scores = []
        if assessment:
            score_rows = list(await db.scalars(
                select(AssessmentScore).where(AssessmentScore.assessment_id == assessment.id)
            ))
            for s in score_rows:
                criterion = await db.scalar(
                    select(AssessmentCriterion).where(AssessmentCriterion.id == s.criterion_id)
                )
                scores.append({
                    "criterion": criterion.name if criterion else "Unknown",
                    "score": s.score,
                    "max_score": criterion.max_score if criterion else 10.0,
                    "weight": criterion.weight if criterion else 1.0,
                    "justification": s.justification or "",
                })

        # Transcript: rows for this session_id, plus same-user rows in the session time window
        # (covers voice saves that omitted session_id or landed on another in_progress session).
        by_id: Dict[str, Any] = {}
        q_session = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        for m in await db.scalars(q_session):
            by_id[m.id] = m

        if interviewee:
            t_end = session.ended_at or datetime.now(timezone.utc)
            q_user = (
                select(Message)
                .where(
                    Message.user_id == interviewee.user_id,
                    Message.created_at >= session.started_at,
                    Message.created_at <= t_end,
                    or_(Message.session_id.is_(None), Message.session_id == session_id),
                )
                .order_by(Message.created_at.asc())
            )
            for m in await db.scalars(q_user):
                by_id.setdefault(m.id, m)

        if not by_id and interviewee:
            for m in await db.scalars(
                select(Message)
                .where(Message.user_id == interviewee.user_id)
                .order_by(Message.created_at.asc())
            ):
                by_id.setdefault(m.id, m)

        messages = list(by_id.values())
        messages.sort(key=lambda m: m.created_at)

        user_msgs = [m for m in messages if m.role == "user"]
        if not user_msgs:
            raise ValueError(
                f"Session {session_id} has no user messages — cannot generate report"
            )

        return {
            "session": {
                "id": session.id,
                "type": session.session_type,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
                "duration_seconds": session.duration_seconds,
            },
            "interviewee": {
                "name": f"{interviewee.first_name} {interviewee.last_name}".strip() if interviewee else "Unknown",
                "email": interviewee.email if interviewee else "",
                "phone": interviewee.phone if interviewee else "",
            },
            "position": position.title if position else "General",
            "assessment": {
                "total_score": assessment.total_score if assessment else None,
                "summary": assessment.summary if assessment else "Не оценено",
                "assessed_at": assessment.assessed_at if assessment else None,
            },
            "scores": scores,
            "transcript": [
                {"role": m.role, "text": m.text, "timestamp": m.created_at}
                for m in messages
            ],
        }


async def load_position_data(position_id: str) -> Dict[str, Any]:
    from sqlalchemy import select

    from server.db import ensure_schema_initialized, make_session
    from server.models.assessment import Assessment
    from server.models.interviewee import Interviewee
    from server.models.interview_session import InterviewSession
    from server.models.position import Position

    await ensure_schema_initialized()
    async with make_session() as db:
        position = await db.scalar(select(Position).where(Position.id == position_id))
        if not position:
            raise ValueError(f"Position {position_id} not found")

        interviewees = list(await db.scalars(
            select(Interviewee).where(Interviewee.position_id == position_id)
        ))

        candidates = []
        for iv in interviewees:
            sessions = list(await db.scalars(
                select(InterviewSession).where(InterviewSession.interviewee_id == iv.id)
            ))
            best_score = None
            for s in sessions:
                a = await db.scalar(select(Assessment).where(Assessment.session_id == s.id))
                if a and a.total_score is not None:
                    if best_score is None or a.total_score > best_score:
                        best_score = a.total_score

            candidates.append({
                "name": f"{iv.first_name} {iv.last_name}",
                "email": iv.email,
                "status": iv.status,
                "sessions_count": len(sessions),
                "best_score": best_score,
            })

        candidates.sort(key=lambda c: c["best_score"] or 0, reverse=True)

        return {
            "position": {"title": position.title, "department": position.department},
            "candidates": candidates,
            "total_candidates": len(candidates),
            "assessed_count": sum(1 for c in candidates if c["best_score"] is not None),
        }


async def load_overall_data() -> Dict[str, Any]:
    from sqlalchemy import func, select

    from server.db import ensure_schema_initialized, make_session
    from server.models.assessment import Assessment
    from server.models.interviewee import Interviewee
    from server.models.interview_session import InterviewSession
    from server.models.position import Position

    await ensure_schema_initialized()
    async with make_session() as db:
        positions = list(await db.scalars(select(Position).where(Position.is_active == True)))
        total_interviewees = await db.scalar(select(func.count(Interviewee.id)))
        total_sessions = await db.scalar(select(func.count(InterviewSession.id)))
        total_assessments = await db.scalar(select(func.count(Assessment.id)))

        position_stats = []
        for p in positions:
            count = await db.scalar(
                select(func.count(Interviewee.id)).where(Interviewee.position_id == p.id)
            )
            assessed = await db.scalar(
                select(func.count(Interviewee.id)).where(
                    Interviewee.position_id == p.id,
                    Interviewee.status == "assessed",
                )
            )
            position_stats.append({
                "title": p.title,
                "department": p.department or "",
                "candidates": count or 0,
                "assessed": assessed or 0,
            })

        all_interviewees = list(await db.scalars(
            select(Interviewee).order_by(Interviewee.created_at.asc())
        ))
        candidates = []
        for iv in all_interviewees:
            best_score = None
            sessions = list(await db.scalars(
                select(InterviewSession).where(InterviewSession.interviewee_id == iv.id)
            ))
            for s in sessions:
                a = await db.scalar(select(Assessment).where(Assessment.session_id == s.id))
                if a and a.total_score is not None:
                    if best_score is None or a.total_score > best_score:
                        best_score = a.total_score
            candidates.append({
                "name": f"{iv.first_name} {iv.last_name}".strip(),
                "email": iv.email,
                "status": iv.status,
                "total_score": best_score,
            })

        return {
            "total_interviewees": total_interviewees or 0,
            "total_sessions": total_sessions or 0,
            "total_assessments": total_assessments or 0,
            "positions": position_stats,
            "candidates": candidates,
            "generated_at": datetime.now(timezone.utc),
        }


def build_individual_pdf(data: Dict[str, Any], output: Union[str, BinaryIO]) -> None:
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = []

    elements.append(Paragraph("Отчёт об интервью", TITLE_STYLE))
    elements.append(Spacer(1, 6 * mm))

    info_data = [
        ["Кандидат:", data["interviewee"]["name"]],
        ["Email:", data["interviewee"]["email"]],
        ["Вакансия:", data["position"]],
        ["Тип сессии:", data["session"]["type"]],
        ["Дата:", str(data["session"]["started_at"])[:19] if data["session"]["started_at"] else "Н/Д"],
        ["Статус:", data["session"]["status"]],
    ]
    bold = f"{_FONT_FAMILY}-Bold" if _FONT_FAMILY != "Helvetica" else bold
    t = Table(info_data, colWidths=[4 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT_FAMILY),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), bold),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8 * mm))

    if data["assessment"]["total_score"] is not None:
        score = data["assessment"]["total_score"]
        color = colors.green if score >= 7 else colors.orange if score >= 4 else colors.red
        elements.append(Paragraph(
            f"Итоговый балл: <font color='{color}'><b>{score:.1f}</b></font> / 10.0",
            ParagraphStyle("Score", parent=TITLE_STYLE, fontName=_FONT_FAMILY, fontSize=20),
        ))
        elements.append(Spacer(1, 6 * mm))

    if data["scores"]:
        elements.append(Paragraph("Оценки по критериям", HEADING_STYLE))
        score_table_data = [["Критерий", "Балл", "Макс", "Вес", "Обоснование"]]
        for s in data["scores"]:
            score_table_data.append([
                s["criterion"],
                f"{s['score']:.1f}",
                f"{s['max_score']:.0f}",
                f"{s['weight']:.1f}",
                Paragraph(s["justification"][:200], BODY_STYLE),
            ])

        t = Table(score_table_data, colWidths=[3 * cm, 1.5 * cm, 1.2 * cm, 1.3 * cm, 9 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _FONT_FAMILY),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6 * mm))

    if data["assessment"]["summary"]:
        elements.append(Paragraph("Заключение", HEADING_STYLE))
        elements.append(Paragraph(data["assessment"]["summary"], BODY_STYLE))
        elements.append(Spacer(1, 6 * mm))

    if data["transcript"]:
        elements.append(Paragraph("Транскрипция интервью", HEADING_STYLE))
        interviewer_style = ParagraphStyle(
            "Interviewer", parent=BODY_STYLE,
            textColor=colors.HexColor("#2c3e50"), leftIndent=0,
        )
        candidate_style = ParagraphStyle(
            "Candidate", parent=BODY_STYLE,
            textColor=colors.HexColor("#1a5276"), leftIndent=12,
        )
        chunk_size = 4000
        for msg in data["transcript"]:
            is_assistant = msg["role"] == "assistant"
            role_label = "Интервьюер" if is_assistant else "Кандидат"
            style = interviewer_style if is_assistant else candidate_style
            raw = (msg.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
            parts = [raw[i : i + chunk_size] for i in range(0, len(raw), chunk_size)] if raw else [""]
            for i, part in enumerate(parts):
                label = role_label if i == 0 else f"{role_label} (прод.)"
                safe = (
                    part.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br/>")
                )
                elements.append(Paragraph(f"<b>{label}:</b> {safe}", style))
                elements.append(Spacer(1, 2 * mm))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f"Сформирован: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        SMALL_STYLE,
    ))

    doc.build(elements)
    if isinstance(output, str):
        logger.info("Report saved to %s", output)
    else:
        logger.info("Report built to binary stream")


def build_position_pdf(data: Dict[str, Any], output: Union[str, BinaryIO]) -> None:
    bold = f"{_FONT_FAMILY}-Bold" if _FONT_FAMILY != "Helvetica" else "Helvetica-Bold"
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = []

    elements.append(Paragraph(f"Сводка по вакансии: {data['position']['title']}", TITLE_STYLE))
    if data["position"]["department"]:
        elements.append(Paragraph(f"Отдел: {data['position']['department']}", BODY_STYLE))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(
        f"Всего кандидатов: {data['total_candidates']} | Оценено: {data['assessed_count']}",
        BODY_STYLE,
    ))
    elements.append(Spacer(1, 8 * mm))

    if data["candidates"]:
        elements.append(Paragraph("Рейтинг кандидатов", HEADING_STYLE))
        table_data = [["#", "Имя", "Email", "Статус", "Сессии", "Лучший балл"]]
        for i, c in enumerate(data["candidates"], 1):
            score_str = f"{c['best_score']:.1f}" if c["best_score"] is not None else "Н/Д"
            table_data.append([
                str(i),
                c["name"],
                c["email"],
                c["status"],
                str(c["sessions_count"]),
                score_str,
            ])

        t = Table(table_data, colWidths=[1 * cm, 4 * cm, 5 * cm, 2.5 * cm, 1.8 * cm, 2.2 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _FONT_FAMILY),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f"Сформирован: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        SMALL_STYLE,
    ))

    doc.build(elements)
    if isinstance(output, str):
        logger.info("Report saved to %s", output)
    else:
        logger.info("Report built to binary stream")


def build_overall_pdf(data: Dict[str, Any], output: Union[str, BinaryIO]) -> None:
    bold = f"{_FONT_FAMILY}-Bold" if _FONT_FAMILY != "Helvetica" else "Helvetica-Bold"
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = []

    elements.append(Paragraph("Общая сводка по интервью", TITLE_STYLE))
    elements.append(Spacer(1, 6 * mm))

    summary_data = [
        ["Всего кандидатов:", str(data["total_interviewees"])],
        ["Всего сессий:", str(data["total_sessions"])],
        ["Всего оценок:", str(data["total_assessments"])],
    ]
    t = Table(summary_data, colWidths=[5 * cm, 4 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT_FAMILY),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("FONTNAME", (0, 0), (0, -1), bold),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8 * mm))

    if data.get("candidates"):
        elements.append(Paragraph("Кандидаты", HEADING_STYLE))
        table_data = [["#", "Имя", "Email", "Статус", "Балл"]]
        for i, c in enumerate(data["candidates"], 1):
            score_str = f"{c['total_score']:.1f}" if c["total_score"] is not None else "Н/Д"
            table_data.append([
                str(i),
                c["name"],
                c["email"],
                c["status"],
                score_str,
            ])

        t = Table(table_data, colWidths=[1 * cm, 4 * cm, 5.5 * cm, 2.5 * cm, 2 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _FONT_FAMILY),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 8 * mm))

    if data.get("positions"):
        elements.append(Paragraph("Обзор вакансий", HEADING_STYLE))
        table_data = [["Вакансия", "Отдел", "Кандидаты", "Оценено"]]
        for p in data["positions"]:
            table_data.append([p["title"], p["department"], str(p["candidates"]), str(p["assessed"])])

        t = Table(table_data, colWidths=[5 * cm, 4 * cm, 3 * cm, 3 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _FONT_FAMILY),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f"Сформирован: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        SMALL_STYLE,
    ))

    doc.build(elements)
    if isinstance(output, str):
        logger.info("Report saved to %s", output)
    else:
        logger.info("Report built to binary stream")


async def ensure_assessed(session_id: str) -> None:
    """Assess a session if it hasn't been assessed yet."""
    from sqlalchemy import select

    from server.db import ensure_schema_initialized, make_session
    from server.models.assessment import Assessment
    from server.models.interview_session import InterviewSession
    from server.services.assessment_service import assess_session

    await ensure_schema_initialized()
    async with make_session() as db:
        existing = await db.scalar(
            select(Assessment).where(Assessment.session_id == session_id)
        )
        if existing:
            logger.info("Session %s already assessed (score=%s)", session_id, existing.total_score)
            return

        session = await db.scalar(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        if not session:
            logger.warning("Session %s not found, skipping assessment", session_id)
            return

        logger.info("Assessing session %s...", session_id)
        assessment = await assess_session(db, session_id)
        logger.info("Assessment complete: score=%.1f", assessment.total_score)


async def get_all_session_ids() -> List[str]:
    """Return all interview session IDs that have messages."""
    from sqlalchemy import select

    from server.db import ensure_schema_initialized, make_session
    from server.models.interview_session import InterviewSession
    from server.models.message import Message

    await ensure_schema_initialized()
    async with make_session() as db:
        session_ids_with_messages = list(await db.scalars(
            select(InterviewSession.id)
            .where(
                InterviewSession.id.in_(
                    select(Message.session_id).where(Message.session_id.isnot(None)).distinct()
                )
            )
            .order_by(InterviewSession.started_at.asc())
        ))
        return session_ids_with_messages
