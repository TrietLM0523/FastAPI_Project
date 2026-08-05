from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import CurrentUser, DBSession
from app.schemas.auth import LogoutRequest, RefreshTokenRequest, Token
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DBSession,
) -> Token:
    service = AuthService(session)
    user = await service.authenticate(form_data.username, form_data.password)

    access_token, refresh_token = await service.issue_tokens(user)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(payload: UserCreate, session: DBSession) -> UserResponse:
    user = await UserService(session).register(payload)
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshTokenRequest, session: DBSession) -> Token:
    access_token, refresh_token = await AuthService(session).refresh(
        payload.refresh_token
    )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, session: DBSession) -> Response:
    await AuthService(session).logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
