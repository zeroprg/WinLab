"""Knowledge domain service — DB operations for KB search."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.knowledge import KnowledgeChunk, KnowledgeDocument


@dataclass
class KBSearchResult:
    document_id: str
    title: str
    text: str
    chunk_id: str | None = None
    chunk_index: int = 0
    source_url: str | None = None


@dataclass
class ChatReply:
    text: str
    card_type: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeService:
    async def search(
        self,
        db: AsyncSession,
        question: str,
        limit: int = 3,
    ) -> list[KBSearchResult]:
        pattern = f"%{question[:120]}%"

        chunk_stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeDocument.status == "published",
                KnowledgeChunk.text.like(pattern),
            )
            .limit(limit)
        )
        rows = list(await db.execute(chunk_stmt))
        if rows:
            return [
                KBSearchResult(
                    document_id=doc.id,
                    title=doc.title,
                    text=chunk.text[:500],
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    source_url=doc.source_url,
                )
                for chunk, doc in rows
            ]

        doc_stmt = (
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.status == "published",
                KnowledgeDocument.content.like(pattern),
            )
            .limit(limit)
        )
        docs = list(await db.scalars(doc_stmt))
        return [
            KBSearchResult(
                document_id=d.id,
                title=d.title,
                text=d.content[:500],
                source_url=d.source_url,
            )
            for d in docs
        ]

    def format_reply(self, results: list[KBSearchResult]) -> ChatReply:
        if not results:
            return ChatReply(
                text="По вашему вопросу информация не найдена в базе знаний. Хотите отправить вопрос HR-администратору?",
                card_type="quick_replies",
                metadata={"choices": ["Да, отправить", "Нет, спасибо"]},
            )
        excerpts = "\n".join(f"• [{r.title}] {r.text[:200]}" for r in results[:2])
        return ChatReply(
            text=f"Нашёл в базе знаний:\n{excerpts}",
            card_type="kb_result",
            metadata={
                "sources": [
                    {
                        "document_id": r.document_id,
                        "title": r.title,
                        "source_url": r.source_url,
                        "excerpt": r.text[:200],
                    }
                    for r in results[:2]
                ]
            },
        )
