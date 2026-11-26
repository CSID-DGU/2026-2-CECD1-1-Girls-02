"""서비스 기준 시간대: KST (+09:00)."""

from datetime import date, datetime, time, timedelta, timezone


KST = timezone(timedelta(hours=9), "KST")


def now_kst() -> datetime:
    return datetime.now(KST)


def kst_date_range_to_utc(
    date_from: date,
    date_to: date,
) -> tuple[datetime, datetime]:
    """KST 기준 시작일과 종료일을 UTC 조회 범위로 변환한다."""

    start = datetime.combine(date_from, time.min, KST)
    end = datetime.combine(
        date_to + timedelta(days=1),
        time.min,
        KST,
    )

    return (
        start.astimezone(timezone.utc),
        end.astimezone(timezone.utc),
    )