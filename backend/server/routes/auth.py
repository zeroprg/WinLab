from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.middleware.auth import get_current_user as _get_current_user
from server.models.user import User
from server.services.auth_service import verify_password, create_jwt

logger = logging.getLogger("bkp-server.routes.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/check")
async def check_admin(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Check if an email belongs to an admin/superadmin user (needs password)."""
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    user = await db.scalar(select(User).where(User.id == email))
    is_admin = (
        user is not None
        and user.role in ("admin", "superadmin")
        and user.password_hash is not None
        and user.is_active
    )
    return {
        "is_admin": is_admin,
    }


@router.post("/login")
async def login(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticate admin/superadmin with email + password, return JWT."""
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    user = await db.scalar(select(User).where(User.id == email))

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Not an admin account")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(user.id, user.role)

    return {
        "token": token,
        "user_id": user.id,
        "role": user.role,
        "display_name": user.display_name,
    }


@router.get("/me")
async def me(
    user: User = Depends(_get_current_user),
) -> Dict[str, Any]:
    """Return current user info from JWT."""
    return {
        "user_id": user.id,
        "role": user.role,
        "display_name": user.display_name,
        "is_active": user.is_active,
    }
