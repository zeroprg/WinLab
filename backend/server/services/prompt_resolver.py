from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.models.interviewee import Interviewee
from server.models.interview_prompt import InterviewPrompt
from server.models.position import Position

logger = logging.getLogger("bkp-server.prompt_resolver")

_RU_LOCALE_SUFFIX = (
    "\n\n[Локаль] Веди весь диалог интервьюера только на русском языке: приветствие, вопросы и ответы — по-русски. "
    "Дай кандидату полностью закончить мысль: не перебивай, не ускоряйся, договаривай фразы до конца. "
    "Если кандидат говорит на другом языке, вежливо продолжай по-русски, пока явно не попросят иной язык."
)

_EN_LOCALE_SUFFIX = (
    "\n\n[Locale] Conduct the entire interview in English only: greeting, questions, and responses — in English. "
    "Let the candidate finish their thought completely: do not interrupt, do not rush, finish phrases fully. "
    "If the candidate speaks another language, politely continue in English unless they explicitly ask for a different language."
)


def finalize_interview_instructions(instructions: str, *, locale: Optional[str] = None) -> str:
    """Append forced-locale rules based on client locale (falls back to CHATBOT_DEFAULT_LOCALE)."""
    if "[Локаль]" in instructions or "[Locale]" in instructions:
        return instructions
    loc = (locale or "").strip().lower()
    if not loc:
        loc = (getattr(settings, "CHATBOT_DEFAULT_LOCALE", "") or "").strip().lower()
    if loc == "ru":
        return instructions + _RU_LOCALE_SUFFIX
    if loc == "en":
        return instructions + _EN_LOCALE_SUFFIX
    return instructions


async def resolve_prompt(
    db: AsyncSession,
    *,
    interviewee_id: Optional[str] = None,
    user_id: Optional[str] = None,
    locale: Optional[str] = None,
) -> str:
    """Resolve interview prompt with priority: interviewee > position > default.

    Lookup chain:
      1. Interviewee-specific override (interview_prompts.interviewee_id)
      2. Position-level default (interview_prompts.position_id, no interviewee_id)
      3. System default from config.py

    Either interviewee_id or user_id must be provided. If user_id is given,
    the interviewee is looked up by user_id first.
    """
    if not interviewee_id and not user_id:
        return finalize_interview_instructions(settings.OPENAI_REALTIME_INSTRUCTIONS, locale=locale)

    interviewee: Optional[Interviewee] = None

    if interviewee_id:
        interviewee = await db.scalar(
            select(Interviewee).where(Interviewee.id == interviewee_id)
        )
    elif user_id:
        interviewee = await db.scalar(
            select(Interviewee).where(Interviewee.user_id == user_id)
        )

    if not interviewee:
        logger.debug("No interviewee found, using system default prompt")
        return finalize_interview_instructions(settings.OPENAI_REALTIME_INSTRUCTIONS, locale=locale)

    # 1. Check interviewee-specific override
    override = await db.scalar(
        select(InterviewPrompt)
        .where(
            InterviewPrompt.interviewee_id == interviewee.id,
            InterviewPrompt.is_active == True,
        )
        .order_by(InterviewPrompt.version.desc())
        .limit(1)
    )
    if override:
        logger.info(f"Using interviewee-specific prompt for {interviewee.id}")
        result = finalize_interview_instructions(override.instructions, locale=locale)
        return await _inject_position_description(db, result, interviewee.position_id, locale)

    # 2. Check position-level default
    if interviewee.position_id:
        position_prompt = await db.scalar(
            select(InterviewPrompt)
            .where(
                InterviewPrompt.position_id == interviewee.position_id,
                InterviewPrompt.interviewee_id == None,
                InterviewPrompt.is_active == True,
            )
            .order_by(InterviewPrompt.version.desc())
            .limit(1)
        )
        if position_prompt:
            logger.info(
                f"Using position-level prompt for position={interviewee.position_id}"
            )
            result = finalize_interview_instructions(position_prompt.instructions, locale=locale)
            return await _inject_position_description(db, result, interviewee.position_id, locale)

    # 3. Fall back to system default
    logger.debug("No custom prompts found, using system default")
    result = finalize_interview_instructions(settings.OPENAI_REALTIME_INSTRUCTIONS, locale=locale)
    return await _inject_position_description(db, result, interviewee.position_id if interviewee else None, locale)


async def _inject_position_description(
    db: AsyncSession,
    instructions: str,
    position_id: Optional[str],
    locale: Optional[str] = None,
) -> str:
    """Prepend vacancy description block so the bot mentions it in the intro."""
    if not position_id:
        return instructions
    pos = await db.scalar(select(Position).where(Position.id == position_id))
    if not pos or not pos.description or not pos.description.strip():
        return instructions
    loc = (locale or "").strip().lower() or "ru"
    if loc == "en":
        block = (
            f"[Position Description]\n{pos.description.strip()}\n"
            "In your opening, briefly describe this position to the candidate.\n\n"
        )
    else:
        block = (
            f"[Описание вакансии]\n{pos.description.strip()}\n"
            "В своём вступлении кратко опишите кандидату эту вакансию.\n\n"
        )
    return block + instructions
