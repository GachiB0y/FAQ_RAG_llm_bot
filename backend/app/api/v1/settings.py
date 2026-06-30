from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_admin_user
from app.models.user import User
from app.models.settings import SystemSettings

router = APIRouter(prefix="/admin/settings", tags=["settings"])


@router.get("")
async def get_settings(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(SystemSettings))
    settings = {s.key: s.value for s in result.scalars().all()}
    return settings


@router.put("")
async def update_settings(
    data: dict,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    for key, value in data.items():
        result = await db.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
        else:
            setting = SystemSettings(key=key, value=value)
            db.add(setting)

    await db.commit()
    return {"message": "Settings updated successfully"}
