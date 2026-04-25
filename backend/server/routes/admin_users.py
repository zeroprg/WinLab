from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.middleware.auth import require_superadmin
from server.models.admin_position import admin_positions
from server.models.position import Position
from server.models.user import User
from server.services.auth_service import hash_password

logger = logging.getLogger("bkp-server.routes.admin_users")

router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_superadmin)],
)


def _user_to_dict(u: User) -> Dict[str, Any]:
    return {
        "id": u.id,
        "display_name": u.display_name,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "position_ids": [p.id for p in u.assigned_positions],
    }


@router.get("")
async def list_admin_users(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all admin and superadmin users."""
    rows = list(
        await db.scalars(
            select(User)
            .where(or_(User.role == "admin", User.role == "superadmin"))
            .order_by(User.created_at.asc())
        )
    )
    return [_user_to_dict(u) for u in rows]


@router.post("", status_code=201)
async def create_admin_user(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new admin user."""
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "admin").strip()
    display_name = (payload.get("display_name") or email).strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    if role not in ("admin", "superadmin"):
        raise HTTPException(status_code=400, detail="role must be admin or superadmin")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")

    existing = await db.scalar(select(User).where(User.id == email))
    if existing and existing.role in ("admin", "superadmin"):
        raise HTTPException(status_code=409, detail="Admin user with this email already exists")

    if existing:
        existing.role = role
        existing.password_hash = hash_password(password)
        existing.display_name = display_name or existing.display_name
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return _user_to_dict(existing)

    user = User(
        id=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_to_dict(user)


@router.patch("/{user_id}")
async def update_admin_user(
    user_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update role, password, or is_active for an admin user."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "role" in payload:
        new_role = payload["role"]
        if new_role not in ("candidate", "admin", "superadmin"):
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = new_role

    if "password" in payload:
        pwd = payload["password"]
        if len(pwd) < 6:
            raise HTTPException(status_code=400, detail="password must be at least 6 characters")
        user.password_hash = hash_password(pwd)

    if "is_active" in payload:
        user.is_active = bool(payload["is_active"])

    if "display_name" in payload:
        user.display_name = (payload["display_name"] or "").strip() or user.display_name

    await db.commit()
    await db.refresh(user)
    return _user_to_dict(user)


@router.delete("/{user_id}")
async def delete_admin_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Delete an admin user. Cannot delete superadmins."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Cannot delete a super-admin")

    if user.role not in ("admin",):
        raise HTTPException(status_code=400, detail="User is not an admin")

    user.role = "candidate"
    user.password_hash = None
    await db.commit()
    return {"detail": f"Admin rights revoked for {user_id}"}


@router.get("/{user_id}/positions")
async def list_user_positions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List positions assigned to an admin user."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return [
        {"id": p.id, "title": p.title, "department": p.department}
        for p in user.assigned_positions
    ]


@router.put("/{user_id}/positions")
async def set_user_positions(
    user_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Replace the full set of positions assigned to an admin user.

    Expects: {"position_ids": ["id1", "id2", ...]}
    """
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=400, detail="User is not an admin")

    position_ids: List[str] = payload.get("position_ids", [])

    positions = list(
        await db.scalars(
            select(Position).where(Position.id.in_(position_ids))
        )
    ) if position_ids else []

    user.assigned_positions = positions
    await db.commit()
    await db.refresh(user)

    return {
        "user_id": user.id,
        "position_ids": [p.id for p in user.assigned_positions],
    }
