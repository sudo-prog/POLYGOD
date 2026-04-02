"""
API routes for the LLM Hub.

Provides endpoints for managing LLM providers, agent configurations,
testing provider health, viewing usage logs, and generating usage heatmaps.
"""

import logging
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import get_db
from src.backend.models.llm import AgentConfig, Provider, UsageLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["LLM Hub"])


# ─── Pydantic schemas ─────────────────────────────────────────────────────────


class ProviderOut(BaseModel):
    """Response model for a provider."""

    id: int
    name: str
    base_url: str | None
    models: list[str]
    status: str
    uptime_24h: str
    avg_speed: int | None
    tokens_today: int

    class Config:
        from_attributes = True


class ProviderCreate(BaseModel):
    """Request model for creating/updating a provider."""

    name: str
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] = []
    status: str = "unknown"


class ProviderTestResult(BaseModel):
    """Response model for provider health test."""

    status: str  # ✅ / ⚠️ / 🔴
    latency_ms: int
    error: str | None = None


class AgentConfigOut(BaseModel):
    """Response model for agent config."""

    id: int
    agent_name: str
    provider_id: int | None
    model_name: str | None
    overrides: dict

    class Config:
        from_attributes = True


class AgentConfigCreate(BaseModel):
    """Request model for creating/updating an agent config."""

    agent_name: str
    provider_id: int | None = None
    model_name: str | None = None
    overrides: dict = {}


class UsageLogOut(BaseModel):
    """Response model for a usage log entry."""

    id: int
    timestamp: str | None
    provider: str
    tokens_used: int | None
    latency_ms: int | None
    agent_name: str | None
    market_id: str | None

    class Config:
        from_attributes = True


class HeatmapEntry(BaseModel):
    """Single heatmap cell — tokens used for a provider on a given date."""

    provider: str
    date: str
    tokens: int


# ─── Provider endpoints ────────────────────────────────────────────────────────


@router.get("/providers", response_model=list[ProviderOut])
async def get_providers(db: AsyncSession = Depends(get_db)) -> list[ProviderOut]:
    """
    List all LLM providers with their current status and stats.

    Returns:
        List of providers.
    """
    result = await db.execute(select(Provider).order_by(Provider.name))
    providers = result.scalars().all()
    return [
        ProviderOut(
            id=p.id,
            name=p.name,
            base_url=p.base_url,
            models=p.models_json or [],
            status=p.status,
            uptime_24h=p.uptime_24h,
            avg_speed=p.avg_speed,
            tokens_today=p.tokens_today,
        )
        for p in providers
    ]


@router.post("/providers", response_model=ProviderOut, status_code=201)
async def create_or_update_provider(
    payload: ProviderCreate,
    db: AsyncSession = Depends(get_db),
) -> ProviderOut:
    """
    Create a new provider or update an existing one by name.

    If a provider with the same name exists, it will be updated.
    """
    result = await db.execute(select(Provider).where(Provider.name == payload.name))
    existing = result.scalar_one_or_none()

    if existing:
        existing.base_url = payload.base_url
        existing.models_json = payload.models
        existing.status = payload.status
        if payload.api_key:
            existing.encrypt_key(payload.api_key)
        provider = existing
    else:
        provider = Provider(
            name=payload.name,
            base_url=payload.base_url,
            models_json=payload.models,
            status=payload.status,
        )
        if payload.api_key:
            provider.encrypt_key(payload.api_key)
        db.add(provider)

    await db.commit()
    await db.refresh(provider)

    return ProviderOut(
        id=provider.id,
        name=provider.name,
        base_url=provider.base_url,
        models=provider.models_json or [],
        status=provider.status,
        uptime_24h=provider.uptime_24h,
        avg_speed=provider.avg_speed,
        tokens_today=provider.tokens_today,
    )


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a provider by ID.
    """
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
    await db.commit()


@router.post("/providers/test", response_model=ProviderTestResult)
async def test_provider_health(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProviderTestResult:
    """
    Test a provider's health by sending a lightweight completion request.

    Updates the provider's status, latency, and 24h uptime on success.
    """
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        from src.backend.llm_router import router as llm_router

        test_model = provider.models_json[0] if provider.models_json else "test"
        start = time.time()
        await llm_router.router.acompletion(
            model=test_model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5,
        )
        latency_ms = int((time.time() - start) * 1000)

        provider.status = "✅"
        provider.avg_speed = latency_ms
        await db.commit()

        return ProviderTestResult(status="✅", latency_ms=latency_ms)

    except Exception as e:
        logger.warning(f"Provider {provider.name} health check failed: {e}")
        provider.status = "🔴"
        await db.commit()

        return ProviderTestResult(status="🔴", latency_ms=0, error=str(e))


# ─── Agent config endpoints ────────────────────────────────────────────────────


@router.get("/agents", response_model=list[AgentConfigOut])
async def get_agent_configs(
    db: AsyncSession = Depends(get_db),
) -> list[AgentConfigOut]:
    """
    List all agent configurations.
    """
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.agent_name))
    agents = result.scalars().all()
    return [AgentConfigOut.model_validate(a) for a in agents]


@router.post("/agents", response_model=AgentConfigOut, status_code=201)
async def create_or_update_agent(
    payload: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentConfigOut:
    """
    Create a new agent config or update an existing one by agent_name.

    If an agent with the same name exists, it will be updated.
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == payload.agent_name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.provider_id = payload.provider_id
        existing.model_name = payload.model_name
        existing.overrides_json = payload.overrides
        agent = existing
    else:
        agent = AgentConfig(
            agent_name=payload.agent_name,
            provider_id=payload.provider_id,
            model_name=payload.model_name,
            overrides_json=payload.overrides,
        )
        db.add(agent)

    await db.commit()
    await db.refresh(agent)

    return AgentConfigOut.model_validate(agent)


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an agent config by ID.
    """
    result = await db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent config not found")
    await db.delete(agent)
    await db.commit()


# ─── Usage logs endpoints ──────────────────────────────────────────────────────


@router.get("/usage", response_model=list[UsageLogOut])
async def get_usage_logs(
    agent_name: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[UsageLogOut]:
    """
    Get usage logs with optional filtering by agent, provider, and date range.
    """
    query = select(UsageLog)
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = query.where(UsageLog.timestamp >= cutoff)

    if agent_name:
        query = query.where(UsageLog.agent_name == agent_name)
    if provider:
        query = query.where(UsageLog.provider == provider)

    query = query.order_by(UsageLog.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [UsageLogOut.model_validate(log) for log in logs]


# ─── Usage heatmap endpoint ────────────────────────────────────────────────────


@router.get("/heatmap", response_model=list[HeatmapEntry])
async def get_usage_heatmap(
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> list[HeatmapEntry]:
    """
    Get aggregated usage heatmap data — tokens per provider per day.

    Returns:
        List of {provider, date, tokens} entries suitable for a heatmap chart.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = (
        select(
            UsageLog.provider,
            cast(UsageLog.timestamp, Date).label("date"),
            func.coalesce(func.sum(UsageLog.tokens_used), 0).label("tokens"),
        )
        .where(UsageLog.timestamp >= cutoff)
        .group_by(UsageLog.provider, cast(UsageLog.timestamp, Date))
        .order_by("date")
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        HeatmapEntry(
            provider=row.provider,
            date=row.date.isoformat() if row.date else "",
            tokens=int(row.tokens or 0),
        )
        for row in rows
    ]