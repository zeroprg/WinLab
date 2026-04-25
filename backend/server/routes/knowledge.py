"""Knowledge Base API routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.middleware.auth import get_current_user, require_admin
from server.models.knowledge import KnowledgeChunk, KnowledgeDocument, UnresolvedQuery
from server.models.user import User

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
public_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _doc_to_dict(d: KnowledgeDocument) -> Dict[str, Any]:
    return {
        "id": d.id,
        "title": d.title,
        "source_url": d.source_url,
        "status": d.status,
        "locale": d.locale,
        "content_preview": (d.content or "")[:200],
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.get("", dependencies=[Depends(require_admin)])
async def list_documents(
    status: Optional[str] = None,
    locale: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    if status:
        stmt = stmt.where(KnowledgeDocument.status == status)
    if locale:
        stmt = stmt.where(KnowledgeDocument.locale == locale)
    rows = list(await db.scalars(stmt))
    return [_doc_to_dict(d) for d in rows]


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
async def create_document(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    content = str(payload.get("content", "")).strip()
    now = datetime.now(timezone.utc)
    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        title=title,
        content=content,
        source_url=payload.get("source_url"),
        owner_id=current_user.id,
        status=payload.get("status", "draft"),
        locale=payload.get("locale", "ru"),
        created_at=now,
    )
    db.add(doc)
    if content:
        chunks = _chunk_text(content, chunk_size=800, overlap=100)
        for i, chunk_text in enumerate(chunks):
            db.add(KnowledgeChunk(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                chunk_index=i,
                text=chunk_text,
                created_at=now,
            ))
    await db.commit()
    await db.refresh(doc)
    return _doc_to_dict(doc)


@router.patch("/{doc_id}", dependencies=[Depends(require_admin)])
async def update_document(
    doc_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    doc = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for field in ("title", "content", "source_url", "status", "locale"):
        if field in payload:
            setattr(doc, field, payload[field])
    doc.updated_at = datetime.now(timezone.utc)
    if "content" in payload and payload["content"]:
        await db.execute(
            KnowledgeChunk.__table__.delete().where(KnowledgeChunk.document_id == doc_id)
        )
        for i, chunk_text in enumerate(_chunk_text(payload["content"], 800, 100)):
            db.add(KnowledgeChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=i,
                text=chunk_text,
                created_at=datetime.now(timezone.utc),
            ))
    await db.commit()
    await db.refresh(doc)
    return _doc_to_dict(doc)


@router.delete("/{doc_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)) -> None:
    doc = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()


@public_router.get("/search")
async def search_knowledge(
    q: str,
    locale: Optional[str] = "ru",
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Keyword-based search (RAG embeddings wired in Phase 3)."""
    if not q.strip():
        return {"results": [], "query": q}
    from sqlalchemy import text as sa_text
    # Use raw LIKE for SQLite compatibility with Unicode text
    pattern = f"%{q}%"
    stmt = (
        select(KnowledgeChunk)
        .join(KnowledgeDocument)
        .where(
            KnowledgeDocument.status == "published",
            KnowledgeChunk.text.like(pattern),
        )
        .limit(limit)
    )
    chunks = list(await db.scalars(stmt))
    # Also search document titles/content if no chunks found
    if not chunks:
        doc_stmt = (
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.status == "published",
                KnowledgeDocument.content.like(pattern),
            )
            .limit(limit)
        )
        docs = list(await db.scalars(doc_stmt))
        return {
            "results": [
                {
                    "chunk_id": None,
                    "document_id": d.id,
                    "text": d.content[:500],
                    "title": d.title,
                    "chunk_index": 0,
                }
                for d in docs
            ],
            "query": q,
        }
    return {
        "results": [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "text": c.text,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ],
        "query": q,
    }


@public_router.post("/unresolved")
async def submit_unresolved_query(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Employee submits an unresolved query with explicit consent."""
    question = str(payload.get("question", "")).strip()
    consent = bool(payload.get("consent_given", False))
    user_id = str(payload.get("user_id", "")).strip() or None
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if not consent:
        raise HTTPException(status_code=400, detail="consent_given must be true to forward the question")
    q = UnresolvedQuery(
        id=str(uuid.uuid4()),
        user_id=user_id,
        question=question,
        consent_given=1,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()
    return {"id": q.id, "status": q.status, "message": "Ваш вопрос отправлен HR-администратору."}


@router.get("/unresolved", dependencies=[Depends(require_admin)])
async def list_unresolved(
    status: Optional[str] = "open",
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(UnresolvedQuery).order_by(UnresolvedQuery.created_at.desc())
    if status:
        stmt = stmt.where(UnresolvedQuery.status == status)
    rows = list(await db.scalars(stmt))
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "question": r.question,
            "consent_given": bool(r.consent_given),
            "status": r.status,
            "assignee_id": r.assignee_id,
            "answer": r.answer,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.patch("/unresolved/{query_id}", dependencies=[Depends(require_admin)])
async def resolve_unresolved(
    query_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    q = await db.scalar(select(UnresolvedQuery).where(UnresolvedQuery.id == query_id))
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")
    if "answer" in payload:
        q.answer = payload["answer"]
    if "status" in payload:
        q.status = payload["status"]
    q.assignee_id = current_user.id
    if q.status == "resolved":
        q.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": q.id, "status": q.status}


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks
