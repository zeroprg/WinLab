"""Knowledge Base domain models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False, default="")
    source_url = Column(String(512), nullable=True)
    owner_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), nullable=False, default="draft")
    locale = Column(String(8), nullable=False, default="ru")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)

    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    document = relationship("KnowledgeDocument", back_populates="chunks")


class UnresolvedQuery(Base):
    __tablename__ = "unresolved_queries"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    consent_given = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="open")
    assignee_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
