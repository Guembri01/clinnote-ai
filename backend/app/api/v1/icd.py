from __future__ import annotations
"""
ClinNote AI — ICD-10 Code Search API
=======================================
Endpoints:
  GET /icd/search?q=       — Search ICD-10 codes by keyword or code prefix
  GET /icd/{code}          — Get single ICD-10 code details
"""


from typing import List

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.deps import CurrentUser
from app.schemas.icd_code import ICDCodeSearch
from app.services.icd_service import ICDService

router = APIRouter(prefix="/icd", tags=["ICD Codes"])


@router.get(
    "/search",
    response_model=List[ICDCodeSearch],
    summary="Search ICD-10-CM codes",
    description=(
        "Search ICD-10-CM diagnosis codes by keyword (e.g. 'chest pain') or "
        "code prefix (e.g. 'J06'). Returns up to 20 results ranked by relevance."
    ),
)
async def search_icd(
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Search query: keyword or code prefix"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum results to return"),
) -> List[ICDCodeSearch]:
    """
    Search ICD-10-CM codes by keyword or code prefix.

    Args:
        q    : Search query string.
        limit: Maximum number of results (1-50).

    Returns:
        List of ICDCodeSearch results ordered by relevance.

    Examples:
        GET /icd/search?q=hypertension       → returns I10, I11.*, etc.
        GET /icd/search?q=J06                → returns J06.0, J06.9
        GET /icd/search?q=chest%20pain       → returns R07.*, I20.*, etc.
    """
    svc = ICDService()
    results = svc.search(q, limit=limit)
    return [ICDCodeSearch(**r) for r in results]


@router.get(
    "/{code}",
    response_model=ICDCodeSearch,
    summary="Get ICD-10-CM code details",
    description="Retrieve details for a specific ICD-10-CM code.",
)
async def get_icd_code(
    code: str,
    current_user: CurrentUser,
) -> ICDCodeSearch:
    """
    Look up a specific ICD-10-CM code.

    Args:
        code: ICD-10-CM code string (e.g. "I10", "J06.9").

    Returns:
        ICDCodeSearch with code, description, and category.

    Raises:
        404: If the code is not found in the local dictionary.
    """
    svc = ICDService()
    result = svc.get_by_code(code)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ICD-10-CM code '{code}' not found",
        )

    return ICDCodeSearch(**result)
