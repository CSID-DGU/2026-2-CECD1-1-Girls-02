from datetime import date

from pydantic import Field

from app.db.models import GenerationPurpose, InquiryStatus
from app.schemas.common import CamelModel
from app.services.metrics_service import (
    AiMetrics,
    DashboardSummary,
    Period,
)


class PeriodData(CamelModel):
    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")

    @classmethod
    def from_period(
        cls, period: Period
    ) -> "PeriodData":
        return cls(
            date_from=period.date_from,
            date_to=period.date_to,
        )


# ---------- 대시보드 ----------

class InquiryCounts(CamelModel):
    total: int
    received: int
    ai_drafted: int
    in_review: int
    answered: int
    closed: int


class TopCategoryItem(CamelModel):
    category_id: str
    category_name: str
    count: int


class AiSummary(CamelModel):
    draft_generated_count: int
    handoff_count: int
    average_latency_ms: int | None


class DashboardData(CamelModel):
    period: PeriodData
    inquiry_counts: InquiryCounts
    top_categories: list[TopCategoryItem]
    ai_summary: AiSummary

    @classmethod
    def build(
        cls,
        period: Period,
        summary: DashboardSummary,
    ) -> "DashboardData":
        counts = summary.status_counts

        return cls(
            period=PeriodData.from_period(period),
            inquiry_counts=InquiryCounts(
                total=sum(counts.values()),
                received=counts[
                    InquiryStatus.DRAFT_GENERATING
                ],
                ai_drafted=counts[
                    InquiryStatus.PENDING_REVIEW
                ],
                in_review=counts[
                    InquiryStatus.IN_REVIEW
                ],
                answered=counts[
                    InquiryStatus.ANSWERED
                ],
                closed=counts[
                    InquiryStatus.CLOSED
                ],
            ),
            top_categories=[
                TopCategoryItem(
                    category_id=c.code,
                    category_name=c.name,
                    count=c.count,
                )
                for c in summary.top_categories
            ],
            ai_summary=AiSummary(
                draft_generated_count=(
                    summary.draft_generated_count
                ),
                handoff_count=summary.handoff_count,
                average_latency_ms=(
                    summary.average_latency_ms
                ),
            ),
        )


# ---------- AI 처리 성능 ----------

class AiMetricsData(CamelModel):
    period: PeriodData
    purpose: GenerationPurpose | None
    total_runs: int
    success_rate: float | None
    average_latency_ms: int | None
    p95_latency_ms: int | None
    average_input_tokens: int | None
    average_output_tokens: int | None
    average_tokens_per_second: float | None
    answer_rate: float | None
    handoff_rate: float | None
    source_attached_rate: float | None

    @classmethod
    def build(
        cls,
        period: Period,
        purpose: GenerationPurpose | None,
        metrics: AiMetrics,
    ) -> "AiMetricsData":
        return cls(
            period=PeriodData.from_period(period),
            purpose=purpose,
            **metrics.__dict__,
        )