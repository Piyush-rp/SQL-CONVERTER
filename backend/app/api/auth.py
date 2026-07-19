from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.core.responses import APIResponse
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas import TokenPair, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=APIResponse[UserOut], status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    user = AuthService(db).register(payload)
    return APIResponse.ok(UserOut.model_validate(user))


@router.post("/login", response_model=APIResponse[TokenPair])
def login(payload: UserLogin, db: Session = Depends(get_db)):
    tokens = AuthService(db).login(payload)
    return APIResponse.ok(tokens)


@router.post("/refresh", response_model=APIResponse[TokenPair])
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    tokens = AuthService(db).refresh(refresh_token)
    return APIResponse.ok(tokens)


@router.get("/me", response_model=APIResponse[UserOut])
def me(user: User = Depends(get_current_user)):
    return APIResponse.ok(UserOut.model_validate(user))
