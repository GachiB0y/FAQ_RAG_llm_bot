from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_admin_user, get_auth_service
from app.services.auth_service import AuthService
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/admin/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)]
):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=data.email,
        password_hash=auth.hash_password(data.password),
        role=data.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)]
):
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.email is not None:
        target_user.email = data.email
    if data.password is not None:
        target_user.password_hash = auth.hash_password(data.password)
    if data.role is not None:
        target_user.role = data.role
    if data.is_active is not None:
        target_user.is_active = data.is_active

    await db.commit()
    await db.refresh(target_user)

    return UserResponse.model_validate(target_user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(target_user)
    await db.commit()

    return {"message": "User deleted successfully"}
