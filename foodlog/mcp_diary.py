"""Read diary days and record notes and medications through MCP."""

from datetime import datetime, timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import F, Prefetch
from django.utils import timezone
from mcp.server.mcpserver.exceptions import ToolError

from foodlog.models import DailyIntake, Day, Dish, Meal, Note, Pill, TakingPill

PILL_MATCH_WINDOW_HOURS = 3


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
                    "is_active": taking.pill.is_active,
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


def _resolve_entry_time(entry_date, entry_time, allow_future=False):
    if entry_date is not None and entry_time is None:
        raise ToolError(
            "A date was provided without a time. Ask the user for the time."
        )
    if entry_time is not None and entry_time.tzinfo is not None:
        raise ToolError("Use local diary time without a timezone offset.")

    now = timezone.localtime()
    entry_date = entry_date if entry_date is not None else now.date()
    entry_time = entry_time if entry_time is not None else now.time()
    entry_time = entry_time.replace(microsecond=0)
    if not allow_future and datetime.combine(entry_date, entry_time) > now.replace(
        tzinfo=None
    ):
        raise ToolError("Cannot record an event as completed in the future.")
    return entry_date, entry_time


def _get_or_create_day(entry_date):
    default_intake = DailyIntake.objects.filter(default=True).first()
    return Day.objects.get_or_create(
        date=entry_date, defaults={"daily_intake": default_intake}
    )


def create_note(text, note_date=None, note_time=None):
    if not text.strip():
        raise ToolError("Note text must not be empty.")
    note_date, note_time = _resolve_entry_time(note_date, note_time)

    for index, character in enumerate(text):
        if character.isalpha():
            text = text[:index] + character.upper() + text[index + 1 :]
            break

    close_old_connections()
    try:
        with transaction.atomic():
            day, day_created = _get_or_create_day(note_date)
            note = Note.objects.create(day=day, time=note_time, note=text)
        return {
            "day_id": day.pk,
            "date": day.date.isoformat(),
            "timezone": settings.TIME_ZONE,
            "day_created": day_created,
            "note": {
                "id": note.pk,
                "time": note.time.isoformat(),
                "text": note.note,
            },
        }
    finally:
        close_old_connections()


def read_pills(include_inactive=False):
    close_old_connections()
    try:
        pills = Pill.objects.all()
        if not include_inactive:
            pills = pills.filter(is_active=True)
        return {
            "pills": list(
                pills.order_by("title", "pk").values("id", "title", "note", "is_active")
            )
        }
    finally:
        close_old_connections()


def create_pill_intake(
    pill_id,
    is_taken,
    note=None,
    intake_date=None,
    intake_time=None,
    separate_intake=False,
):
    if not isinstance(is_taken, bool):
        raise ToolError("is_taken must be true for a taken pill or false for a plan.")
    if note is not None and len(note) > 150:
        raise ToolError("The medication comment must be at most 150 characters.")
    if not isinstance(separate_intake, bool):
        raise ToolError("separate_intake must be true or false.")
    if separate_intake and not is_taken:
        raise ToolError(
            "separate_intake is only for an explicitly confirmed additional intake."
        )
    intake_date, intake_time = _resolve_entry_time(
        intake_date, intake_time, allow_future=not is_taken
    )

    close_old_connections()
    try:
        with transaction.atomic():
            pill = _get_active_pill(pill_id, for_update=True)
            if is_taken and not separate_intake:
                nearby = _nearby_pill_intakes(
                    pill, intake_date, intake_time, for_update=True
                )
                taken = [taking for taking in nearby if taking.is_taken]
                if taken:
                    return _pill_confirmation(
                        "already_taken", pill, intake_date, intake_time, note, taken
                    )
                planned = [taking for taking in nearby if not taking.is_taken]
                if len(planned) > 1:
                    return _pill_confirmation(
                        "multiple_plans", pill, intake_date, intake_time, note, planned
                    )
                if planned:
                    taking = planned[0]
                    if (taking.note or "").strip() and (
                        (taking.note or "").strip().casefold()
                        != (note or "").strip().casefold()
                    ):
                        return _pill_confirmation(
                            "review_comment",
                            pill,
                            intake_date,
                            intake_time,
                            note,
                            planned,
                        )
                    return _complete_pill_intake(taking, intake_date, intake_time, note)
            day, day_created = _get_or_create_day(intake_date)
            taking = TakingPill.objects.create(
                pill=pill, day=day, time=intake_time, is_taken=is_taken, note=note
            )
            return _pill_intake_result(taking, day_created, "created")
    finally:
        close_old_connections()


def _get_active_pill(pill_id, for_update=False):
    pills = Pill.objects.all()
    if for_update:
        pills = pills.select_for_update()
    try:
        pill = pills.get(pk=pill_id)
    except Pill.DoesNotExist:
        raise ToolError(
            "Pill not found. Use get_pills and ask the user to clarify the name "
            "or add the pill in Django Admin."
        ) from None
    if not pill.is_active:
        raise ToolError(
            "This pill is inactive. Use get_pills and ask the user which "
            "active pill they mean. The catalogue is managed in Django Admin."
        )
    return pill


def _nearby_pill_intakes(pill, intake_date, intake_time, for_update=False):
    target = datetime.combine(intake_date, intake_time)
    window = timedelta(hours=PILL_MATCH_WINDOW_HOURS)
    try:
        start = target - window
        end = target + window
    except OverflowError:
        raise ToolError(
            "The intake date is outside the supported search range."
        ) from None
    records = TakingPill.objects.filter(
        pill=pill, time__isnull=False, day__date__range=(start.date(), end.date())
    ).select_related("day", "pill")
    if for_update:
        records = records.select_for_update(of=("self",))
    matches = [
        taking
        for taking in records
        if abs(datetime.combine(taking.day.date, taking.time) - target) <= window
    ]
    return sorted(
        matches,
        key=lambda taking: (
            abs(datetime.combine(taking.day.date, taking.time) - target),
            taking.day.date,
            taking.time,
            taking.pk,
        ),
    )


def _pill_intake_result(taking, day_created, status):
    return {
        "status": status,
        "day_id": taking.day_id,
        "date": taking.day.date.isoformat(),
        "timezone": settings.TIME_ZONE,
        "day_created": day_created,
        "taking_pill": {
            "id": taking.pk,
            "time": taking.time.isoformat() if taking.time is not None else None,
            "pill": {
                "id": taking.pill_id,
                "title": taking.pill.title,
                "note": taking.pill.note,
                "is_active": taking.pill.is_active,
            },
            "is_taken": taking.is_taken,
            "note": taking.note,
        },
    }


def _pill_confirmation(reason, pill, intake_date, intake_time, note, records):
    messages = {
        "already_taken": (
            "This pill is already recorded as taken nearby. Tell the user the recorded "
            "date, time and comment below. Ask whether they took another dose or mean "
            "the existing record. Do not change or add anything without clarification."
        ),
        "multiple_plans": (
            "Several plans for this pill are nearby. Ask the user which plan they "
            "mean or whether this is a separate intake. Do not guess."
        ),
        "review_comment": (
            "Review this plan's comment against the user's reported intake. If the "
            "dose or meaning conflicts or is ambiguous, ask whether this is the "
            "planned intake with a changed dose or an additional intake. After "
            "clarification use mark_pill_taken for the selected plan, passing the "
            "confirmed actual comment. If clearly compatible, retain the plan's "
            "relevant details and add the user's comment. Never infer a dose."
        ),
    }
    return {
        "status": "needs_confirmation",
        "reason": reason,
        "message": messages[reason],
        "window_hours": PILL_MATCH_WINDOW_HOURS,
        "pill_id": pill.pk,
        "pill_title": pill.title,
        "intake_date": intake_date.isoformat(),
        "intake_time": intake_time.isoformat(),
        "timezone": settings.TIME_ZONE,
        "note": note,
        "records": [
            _pill_intake_result(taking, False, "existing") for taking in records
        ],
    }


def _complete_pill_intake(taking, intake_date, intake_time, note):
    planned = {
        "date": taking.day.date.isoformat(),
        "time": taking.time.isoformat() if taking.time is not None else None,
        "note": taking.note,
    }
    day, day_created = _get_or_create_day(intake_date)
    taking.day = day
    taking.time = intake_time
    taking.is_taken = True
    if note is not None:
        taking.note = note
    taking.save(update_fields=("day", "time", "is_taken", "note", "updated_at"))
    result = _pill_intake_result(taking, day_created, "marked_taken")
    result["matched_plan"] = planned
    return result


def read_nearby_pill_intakes(pill_id, intake_date=None, intake_time=None):
    intake_date, intake_time = _resolve_entry_time(
        intake_date, intake_time, allow_future=True
    )
    close_old_connections()
    try:
        pill = _get_active_pill(pill_id)
        nearby = _nearby_pill_intakes(pill, intake_date, intake_time)
        return {
            "pill_id": pill.pk,
            "pill_title": pill.title,
            "intake_date": intake_date.isoformat(),
            "intake_time": intake_time.isoformat(),
            "timezone": settings.TIME_ZONE,
            "window_hours": PILL_MATCH_WINDOW_HOURS,
            "planned_intakes": [
                _pill_intake_result(taking, False, "planned")
                for taking in nearby
                if not taking.is_taken
            ],
            "taken_intakes": [
                _pill_intake_result(taking, False, "taken")
                for taking in nearby
                if taking.is_taken
            ],
        }
    finally:
        close_old_connections()


def complete_pill_intake(
    pill_id,
    intake_id,
    note=None,
    intake_date=None,
    intake_time=None,
    confirm_repeat=False,
):
    if note is not None and len(note) > 150:
        raise ToolError("The medication comment must be at most 150 characters.")
    if not isinstance(confirm_repeat, bool):
        raise ToolError("confirm_repeat must be true or false.")
    intake_date, intake_time = _resolve_entry_time(intake_date, intake_time)
    close_old_connections()
    try:
        with transaction.atomic():
            pill = _get_active_pill(pill_id, for_update=True)
            try:
                taking = (
                    TakingPill.objects.select_for_update(of=("self",))
                    .select_related("day", "pill")
                    .get(pk=intake_id, pill=pill)
                )
            except TakingPill.DoesNotExist:
                raise ToolError(
                    "Intake not found for this pill. Reload its nearby records and "
                    "ask the user which plan they mean."
                ) from None
            if taking.is_taken:
                return _pill_confirmation(
                    "already_taken", pill, intake_date, intake_time, note, [taking]
                )
            if not confirm_repeat:
                taken = [
                    record
                    for record in _nearby_pill_intakes(
                        pill, intake_date, intake_time, for_update=True
                    )
                    if record.is_taken
                ]
                if taken:
                    return _pill_confirmation(
                        "already_taken", pill, intake_date, intake_time, note, taken
                    )
            return _complete_pill_intake(taking, intake_date, intake_time, note)
    finally:
        close_old_connections()
