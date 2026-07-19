from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_admin_user, get_gateway
from app.core.gateway.gateway import SecurityGateway
from app.models.user import User

router = APIRouter(prefix="/gateway", tags=["gateway"])


@router.get("/stats")
async def gateway_stats(
    gateway: Annotated[SecurityGateway, Depends(get_gateway)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    return await gateway.stats()
