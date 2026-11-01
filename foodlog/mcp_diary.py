"""Read diary days and their related entries for MCP."""

from django.conf import settings
from django.db import close_old_connections
from django.db.models import F, Prefetch
from django.utils import timezone
from mcp.server.mcpserver.exceptions import ToolError

from foodlog.models import Day, Dish, Meal, Note, TakingPill


def _totals(record):
    return {
        field: getattr(record, field)
        for field in ("energy", "proteins", "fats", "carbs", "weight")
    }


def _serialize_day(day):
    intake = day.daily_intake
    return {
        "id": day.pk,
        "date": day.date.isoformat(),
        "daily_intake": (
            {
                "id": intake.pk,
                "title": intake.title,
                "note": intake.note,
                **{
                    field: getattr(intake, field)
                    for field in (
                        "energy",
                        "proteins",
                        "fats",
                        "carbs",
                        "sugar",
                        "salt",
                    )
                },
            }
            if intake is not None
            else None
        ),
        "notes": [
            {
                "id": note.pk,
                "time": note.time.isoformat() if note.time is not None else None,
                "text": note.note,
            }
            for note in day.note_set.all()
        ],
        "taking_pills": [
            {
                "id": taking.pk,
                "time": taking.time.isoformat() if taking.time is not None else None,
                "pill": {
                    "id": taking.pill_id,
                    "title": taking.pill.title,
                    "note": taking.pill.note,
                },
                "is_taken": taking.is_taken,
                "note": taking.note,
            }
            for taking in day.takingpill_set.all()
        ],
        "meals": [
            {
                "id": meal.pk,
                "title": meal.title.title,
                "time": meal.time.isoformat() if meal.time is not None else None,
                "dishes": [
                    {
                        "id": dish.pk,
                        "weight": dish.weight,
                        "note": dish.note,
                        "product": {
                            "id": dish.product_id,
                            "title": dish.product.title,
                            **{
                                field: getattr(dish.product, field)
                                for field in (
                                    "energy",
                                    "proteins",
                                    "fats",
                                    "carbs",
                                    "sugar",
                                    "salt",
                                    "note",
                                    "rate",
                                    "lactose_free",
                                )
                            },
                        },
                        "totals": _totals(dish),
                    }
                    for dish in meal.dish_set.all()
                ],
                "totals": _totals(meal),
            }
            for meal in day.meal_set.all()
        ],
        "totals": _totals(day),
    }


def read_days(start_date=None, end_date=None, limit=31, offset=0):
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ToolError("end_date must be on or after start_date.")
    if not 1 <= limit <= 31:
        raise ToolError("limit must be between 1 and 31 days.")
    if offset < 0:
        raise ToolError("offset must be non-negative.")

    close_old_connections()
    try:
        forward = start_date is not None and end_date is None
        upper_date = end_date if end_date is not None else timezone.localdate()
        queryset = Day.objects.filter(date__lte=upper_date)
        if start_date is not None:
            queryset = queryset.filter(date__gte=start_date)
        chronological = (F("time").asc(nulls_last=True), "pk")
        days = list(
            queryset.select_related("daily_intake")
            .prefetch_related(
                Prefetch("note_set", queryset=Note.objects.order_by(*chronological)),
                Prefetch(
                    "takingpill_set",
                    queryset=TakingPill.objects.select_related("pill").order_by(
                        *chronological
                    ),
                ),
                Prefetch(
                    "meal_set",
                    queryset=Meal.objects.select_related("title")
                    .order_by(*chronological)
                    .prefetch_related(
                        Prefetch(
                            "dish_set",
                            queryset=Dish.objects.select_related("product").order_by(
                                "pk"
                            ),
                        )
                    ),
                ),
            )
            .order_by("date" if forward else "-date")[offset : offset + limit + 1]
        )
        has_more = len(days) > limit
        page = days[:limit]
        if forward:
            page.reverse()
        return {
            "start_date": start_date.isoformat() if start_date is not None else None,
            "end_date": upper_date.isoformat(),
            "timezone": settings.TIME_ZONE,
            "days": [_serialize_day(day) for day in page],
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
        }
    finally:
        close_old_connections()
