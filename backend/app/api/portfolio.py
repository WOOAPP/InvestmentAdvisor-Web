"""Portfolio endpoints — CRUD for positions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.portfolio import PortfolioPosition
from backend.app.models.user import User
from backend.app.schemas.portfolio import PositionCreate, PositionResponse

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    tab_type: str = "zakupione",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PortfolioPosition)
        .where(
            PortfolioPosition.user_id == user.id,
            PortfolioPosition.tab_type == tab_type,
        )
        .order_by(PortfolioPosition.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=PositionResponse, status_code=201)
async def add_position(
    body: PositionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pos = PortfolioPosition(
        user_id=user.id,
        symbol=body.symbol,
        name=body.name or body.symbol,
        quantity=body.quantity,
        buy_price=body.buy_price,
        buy_currency=body.buy_currency,
        buy_fx_to_usd=body.buy_fx_to_usd,
        buy_price_usd=body.buy_price * body.buy_fx_to_usd,
        tab_type=body.tab_type,
    )
    db.add(pos)
    await db.commit()
    await db.refresh(pos)
    return pos


@router.delete("/{position_id}", status_code=204)
async def delete_position(
    position_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.id == position_id,
            PortfolioPosition.user_id == user.id,
        )
    )
    pos = result.scalar_one_or_none()
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")
    await db.delete(pos)
    await db.commit()
