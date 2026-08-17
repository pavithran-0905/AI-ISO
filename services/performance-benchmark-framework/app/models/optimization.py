"""AI-assisted optimization recommendations."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import OptimizationCategory, RecommendationStatus


class OptimizationRecommendation(BaseModel):
    """``optimization_recommendations`` -- one generated suggestion for
    improving performance, capacity, or cost."""

    __tablename__ = "optimization_recommendations"
    __table_args__ = (Index("ix_optimization_recommendation_category", "category"),)

    category: Mapped[OptimizationCategory] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(256))
    detail: Mapped[str] = mapped_column(Text, default="")
    impact_score: Mapped[float] = mapped_column(Float)
    status: Mapped[RecommendationStatus] = mapped_column(
        String(16), default=RecommendationStatus.PENDING, index=True
    )


__all__ = ["OptimizationRecommendation"]
