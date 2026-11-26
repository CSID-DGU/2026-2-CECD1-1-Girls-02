"""관리자 대시보드 요약과 AI 처리 성능 지표."""

import math
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.models import (
    DraftAction,
    EvidenceKind,
    GenerationStatus,
)
from app.core.errors import AppError, ErrorCode
from app.core.timezone import kst_date_range_to_utc, now_kst
from app.db.models import (
    AiGenerationLog,
    AnswerDraft,
    GenerationPurpose,
    Inquiry,
    InquiryCategory,
    InquiryStatus,
)


DEFAULT_PERIOD_DAYS = 30
TOP_CATEGORY_LIMIT = 5


@dataclass(frozen=True)
class Period:
    date_from: date
    date_to: date


def resolve_period(
    date_from: date | None,
    date_to: date | None,
) -> Period:
    """기간 미입력 시 오늘(KST)까지 최근 30일."""

    end = date_to or now_kst().date()
    start = date_from or end - timedelta(
        days=DEFAULT_PERIOD_DAYS - 1
    )

    if start > end:
        raise AppError(
            ErrorCode.INVALID_PARAMETER,
            "from은 to보다 늦을 수 없습니다.",
        )

    return Period(start, end)


# ---------- 대시보드 ----------

@dataclass(frozen=True)
class TopCategory:
    code: str
    name: str
    count: int


@dataclass(frozen=True)
class DashboardSummary:
    status_counts: dict[InquiryStatus, int]
    top_categories: list[TopCategory]
    draft_generated_count: int
    handoff_count: int
    average_latency_ms: int | None


def dashboard_summary(
    db: Session,
    period: Period,
) -> DashboardSummary:
    start, end = kst_date_range_to_utc(
        period.date_from,
        period.date_to,
    )

    in_period = (
        Inquiry.created_at >= start,
        Inquiry.created_at < end,
    )

    status_counts = {
        status: 0 for status in InquiryStatus
    }

    for status, count in db.execute(
        select(Inquiry.status, func.count())
        .where(*in_period)
        .group_by(Inquiry.status)
    ):
        status_counts[status] = count

    count_col = func.count(Inquiry.id)

    top_categories = [
        TopCategory(code, name, count)
        for code, name, count in db.execute(
            select(
                InquiryCategory.code,
                InquiryCategory.name,
                count_col,
            )
            .join(
                Inquiry,
                Inquiry.category_id == InquiryCategory.id,
            )
            .where(*in_period)
            .group_by(
                InquiryCategory.id,
                InquiryCategory.code,
                InquiryCategory.name,
            )
            .order_by(
                count_col.desc(),
                InquiryCategory.code,
            )
            .limit(TOP_CATEGORY_LIMIT)
        )
    ]

    action_counts = dict(
        db.execute(
            select(AnswerDraft.action, func.count())
            .join(
                Inquiry,
                Inquiry.id == AnswerDraft.inquiry_id,
            )
            .where(
                *in_period,
                AnswerDraft.action.is_not(None),
            )
            .group_by(AnswerDraft.action)
        ).all()
    )

    average_latency = db.scalar(
        select(func.avg(AiGenerationLog.latency_ms))
        .where(
            AiGenerationLog.purpose
            == GenerationPurpose.INQUIRY_DRAFT,
            AiGenerationLog.created_at >= start,
            AiGenerationLog.created_at < end,
        )
    )

    return DashboardSummary(
        status_counts=status_counts,
        top_categories=top_categories,
        draft_generated_count=action_counts.get(
            DraftAction.DRAFT_FOR_REVIEW, 0
        ),
        handoff_count=action_counts.get(
            DraftAction.ESCALATE, 0
        ),
        average_latency_ms=(
            round(average_latency)
            if average_latency is not None
            else None
        ),
    )


# ---------- AI 처리 성능 ----------

@dataclass(frozen=True)
class AiMetrics:
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


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _p95(values: list[int]) -> int | None:
    """nearest-rank 방식의 95번째 백분위수."""

    if not values:
        return None

    ordered = sorted(values)

    return ordered[
        math.ceil(0.95 * len(ordered)) - 1
    ]


def ai_metrics(
    db: Session,
    period: Period,
    purpose: GenerationPurpose | None,
) -> AiMetrics:
    start, end = kst_date_range_to_utc(
        period.date_from,
        period.date_to,
    )

    stmt = (
        select(AiGenerationLog)
        .options(
            selectinload(AiGenerationLog.sources)
        )
        .where(
            AiGenerationLog.created_at >= start,
            AiGenerationLog.created_at < end,
        )
    )

    if purpose is not None:
        stmt = stmt.where(
            AiGenerationLog.purpose == purpose
        )

    runs = list(db.scalars(stmt))
    total = len(runs)

    succeeded = [
        r for r in runs
        if r.status in (
            GenerationStatus.COMPLETED,
            GenerationStatus.RULE_ESCALATED,
        )
    ]

    answered = [
        r for r in runs
        if r.action is DraftAction.DRAFT_FOR_REVIEW
    ]

    handed_off = [
        r for r in runs
        if r.action is DraftAction.ESCALATE
    ]

    with_source = [
        r for r in answered
        if any(
            s.cited and s.kind is EvidenceKind.OFFICIAL
            for s in r.sources
        )
    ]

    latencies = [
        r.latency_ms for r in runs
    ]

    input_tokens = [
        r.input_tokens for r in runs
        if r.input_tokens is not None
    ]

    output_tokens = [
        r.output_tokens for r in runs
        if r.output_tokens is not None
    ]

    tokens_per_second = [
        r.output_tokens / (r.latency_ms / 1000)
        for r in runs
        if r.output_tokens is not None
        and r.latency_ms > 0
    ]

    average_latency = _average(latencies)
    average_input = _average(input_tokens)
    average_output = _average(output_tokens)
    average_tps = _average(tokens_per_second)

    return AiMetrics(
        total_runs=total,
        success_rate=_rate(len(succeeded), total),
        average_latency_ms=(
            round(average_latency)
            if average_latency is not None
            else None
        ),
        p95_latency_ms=_p95(latencies),
        average_input_tokens=(
            round(average_input)
            if average_input is not None
            else None
        ),
        average_output_tokens=(
            round(average_output)
            if average_output is not None
            else None
        ),
        average_tokens_per_second=(
            round(average_tps, 1)
            if average_tps is not None
            else None
        ),
        answer_rate=_rate(len(answered), total),
        handoff_rate=_rate(len(handed_off), total),
        source_attached_rate=_rate(
            len(with_source), len(answered)
        ),
    )