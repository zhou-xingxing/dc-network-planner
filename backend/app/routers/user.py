from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_administrator
from app.exceptions import BusinessError
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import PasswordReset, UserCreate, UserResponse, UserUpdate
from app.services.auth import create_user, delete_user, list_users, reset_password, update_user, user_to_response

router = APIRouter(prefix="/api/users", tags=["Users"], dependencies=[Depends(require_administrator)])


@router.get("", response_model=PaginatedResponse[UserResponse])
def list_users_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    """List local users."""
    users, total = list_users(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=[UserResponse(**user_to_response(user)) for user in users],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=UserResponse, status_code=201)
def create_user_endpoint(data: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """Create a local user."""
    try:
        user = create_user(db, data)
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserResponse(**user_to_response(user))


@router.put("/{user_id}", response_model=UserResponse)
def update_user_endpoint(user_id: str, data: UserUpdate, db: Session = Depends(get_db)) -> UserResponse:
    """Update a local user."""
    try:
        user = update_user(db, user_id, data)
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user_to_response(user))


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def reset_password_endpoint(user_id: str, data: PasswordReset, db: Session = Depends(get_db)) -> UserResponse:
    """Reset a user's password."""
    user = reset_password(db, user_id, data.password)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user_to_response(user))


@router.delete("/{user_id}", status_code=204)
def delete_user_endpoint(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> None:
    """Delete a local user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=409, detail="不能删除当前登录用户")
    try:
        deleted = delete_user(db, user_id)
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
