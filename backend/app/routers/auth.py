from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import BusinessError
from app.models.user import User
from app.schemas.user import CurrentUserResponse, LoginRequest, LoginResponse, PasswordChange
from app.services.auth import authenticate_user, change_password, create_access_token
from app.services.user import current_user_to_response

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Login with username and password."""
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(
        access_token=create_access_token(user),
        user=CurrentUserResponse(**current_user_to_response(user)),
    )


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """Get current user profile and permissions."""
    return CurrentUserResponse(**current_user_to_response(current_user))


@router.put("/password", response_model=CurrentUserResponse)
def change_my_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    """Change current user's password."""
    try:
        user = change_password(db, current_user, data.current_password, data.new_password)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CurrentUserResponse(**current_user_to_response(user))
