"""HTTP PDF report download with file-based caching in CHAT_DATA_DIR/reports/."""
from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from server.config import settings
from server.middleware.auth import require_admin
from server.services.report_pdf import (
    build_individual_pdf,
    build_overall_pdf,
    build_position_pdf,
    ensure_assessed,
    load_individual_data,
    load_overall_data,
    load_position_data,
)

logger = logging.getLogger("bkp-server.routes.reports")

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_admin)])


def _reports_dir() -> Path:
    p = Path(settings.CHAT_DATA_DIR)
    base = p if p.is_absolute() else (Path.cwd() / p)
    d = base / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ascii_filename(name: str) -> str:
    safe = re.sub(r"[^\w.\-]+", "_", name, flags=re.ASCII).strip("._") or "report"
    return safe[:120]


def _cached_path(prefix: str, entity_id: str) -> Path:
    safe_id = re.sub(r"[^\w\-]", "_", entity_id)
    return _reports_dir() / f"{prefix}_{safe_id}.pdf"


@router.get("/sessions/{session_id}/pdf")
async def download_session_report_pdf(
    session_id: str,
    refresh: bool = Query(False, description="Force regeneration"),
) -> Response:
    cache = _cached_path("session", session_id)

    if cache.is_file() and not refresh:
        logger.info("Serving cached session report %s", cache.name)
        return FileResponse(
            path=str(cache),
            media_type="application/pdf",
            filename=cache.name,
        )

    try:
        await ensure_assessed(session_id)
        data = await load_individual_data(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Session report failed for %s", session_id)
        raise HTTPException(status_code=500, detail=f"Report failed: {exc}") from exc

    buf = BytesIO()
    try:
        build_individual_pdf(data, buf)
    except Exception as exc:
        logger.exception("PDF build failed for session %s", session_id)
        raise HTTPException(status_code=500, detail=f"PDF build failed: {exc}") from exc

    pdf_bytes = buf.getvalue()
    try:
        cache.write_bytes(pdf_bytes)
        logger.info("Cached session report → %s (%d bytes)", cache.name, len(pdf_bytes))
    except OSError as exc:
        logger.warning("Could not cache report %s: %s", cache.name, exc)

    email = (data.get("interviewee") or {}).get("email") or ""
    fname = _ascii_filename(f"interview_report_{email or session_id[:8]}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/positions/{position_id}/pdf")
async def download_position_report_pdf(
    position_id: str,
    refresh: bool = Query(False, description="Force regeneration"),
) -> Response:
    cache = _cached_path("position", position_id)

    if cache.is_file() and not refresh:
        logger.info("Serving cached position report %s", cache.name)
        return FileResponse(
            path=str(cache),
            media_type="application/pdf",
            filename=cache.name,
        )

    try:
        data = await load_position_data(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Position report failed for %s", position_id)
        raise HTTPException(status_code=500, detail=f"Report failed: {exc}") from exc

    buf = BytesIO()
    try:
        build_position_pdf(data, buf)
    except Exception as exc:
        logger.exception("PDF build failed for position %s", position_id)
        raise HTTPException(status_code=500, detail=f"PDF build failed: {exc}") from exc

    pdf_bytes = buf.getvalue()
    try:
        cache.write_bytes(pdf_bytes)
        logger.info("Cached position report → %s (%d bytes)", cache.name, len(pdf_bytes))
    except OSError as exc:
        logger.warning("Could not cache report %s: %s", cache.name, exc)

    title = (data.get("position") or {}).get("title") or position_id[:8]
    fname = _ascii_filename(f"position_report_{title}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/overall.pdf")
async def download_overall_report_pdf(
    refresh: bool = Query(False, description="Force regeneration"),
) -> Response:
    cache = _reports_dir() / "overall.pdf"

    if cache.is_file() and not refresh:
        logger.info("Serving cached overall report")
        return FileResponse(
            path=str(cache),
            media_type="application/pdf",
            filename="report_overall.pdf",
        )

    try:
        data = await load_overall_data()
    except Exception as exc:
        logger.exception("Overall report failed")
        raise HTTPException(status_code=500, detail=f"Report failed: {exc}") from exc

    buf = BytesIO()
    try:
        build_overall_pdf(data, buf)
    except Exception as exc:
        logger.exception("PDF build failed (overall)")
        raise HTTPException(status_code=500, detail=f"PDF build failed: {exc}") from exc

    pdf_bytes = buf.getvalue()
    try:
        cache.write_bytes(pdf_bytes)
        logger.info("Cached overall report → %s (%d bytes)", cache.name, len(pdf_bytes))
    except OSError as exc:
        logger.warning("Could not cache overall report: %s", exc)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={'Content-Disposition': 'attachment; filename="report_overall.pdf"'},
    )
