from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_administrator
from app.exceptions import BusinessError
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.external import ExternalAccessTokenListItem
from app.services.external_token import (
    external_access_token_to_response,
    list_unrevoked_unexpired_external_access_tokens,
    revoke_unrevoked_external_access_token,
)

router = APIRouter(
    prefix="/api/external-access-tokens",
    tags=["External Access Tokens"],
    dependencies=[Depends(require_administrator)],
)


@router.get("", response_model=PaginatedResponse[ExternalAccessTokenListItem])
def list_external_access_tokens_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ExternalAccessTokenListItem]:
    """列出未撤销、未过期的外部 API 访问令牌。"""
    tokens, total = list_unrevoked_unexpired_external_access_tokens(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=[
            ExternalAccessTokenListItem(**external_access_token_to_response(token, username, owner_is_active))
            for token, username, owner_is_active in tokens
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_external_access_token_endpoint(
    token_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> None:
    """撤销尚未撤销的外部 API 访问令牌。"""
    try:
        token = revoke_unrevoked_external_access_token(db, token_id, current_user.username)
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not token:
        raise HTTPException(status_code=404, detail="外部 API 访问令牌不存在")
