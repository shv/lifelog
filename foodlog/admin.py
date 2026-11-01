import datetime
import logging

from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    DailyIntake,
    Day,
    Dish,
    Meal,
    MealTitle,
    Note,
    Pill,
    Product,
    TakingPill,
)

logger = logging.getLogger(__name__)

admin.site.register(MealTitle)
admin.site.register(Pill)


class DayCopyForm(forms.ModelForm):
    copy_from = forms.ModelChoiceField(
        queryset=Day.objects.order_by("-date").all(),
        required=False,
        label="Copy meals from Day",
        help_text="Select an existing Day to copy meals and dishes from.",
    )

    class Meta:
        model = Day
        fields = "__all__"  # All model fields


class DishInline(admin.TabularInline):  # Or admin.StackedInline for vertical display
    model = Dish
    extra = 1  # Number of empty rows for adding new records


class MealInline(admin.TabularInline):
    model = Meal
    extra = 1
    inlines = (DishInline,)  # Nested inlines for displaying Dish within Meal
    ordering = ("time", "id")


class TakingPillInline(
    admin.TabularInline
):  # Or admin.StackedInline for vertical display
    model = TakingPill
    extra = 1  # Number of empty rows for adding new records
    ordering = ("time", "pill")


class NoteInline(admin.TabularInline):  # Or admin.StackedInline for vertical display
    model = Note
    extra = 1  # Number of empty rows for adding new records
    ordering = ("time",)


@admin.register(DailyIntake)
class DailyIntakeAdmin(admin.ModelAdmin):
    list_display = ("title", "default", "energy", "proteins", "fats", "carbs")

    ordering = ("-default", "-id")


def _colored_param(value, real_param, need_param, total=None):
    """
    Colored parameter
    """

    fraction = real_param / need_param
    status = "fl-good-color"
    if fraction > 1.10:
        status = "fl-fraction-more-110-color"
    elif fraction > 1.05:
        status = "fl-fraction-more-105-color"
    elif fraction < 0.90:
        status = "fl-fraction-less-090-color"
    elif fraction < 0.95:
        status = "fl-fraction-less-095-color"

    result = format_html('<span class="{}">{}</span>', status, value)
    if total is not None:
        result = format_html("{} / {}", result, total)
    return result


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "is_today",
        "daily_intake",
        "energy_colored",
        "proteins_colored",
        "fats_colored",
        "carbs_colored",
        "weight",
    )

    list_per_page = 10

    readonly_fields = (
        "is_today",
        "meals_and_dishes",
    )

    ordering = ("-date",)

    inlines = (
        TakingPillInline,
        NoteInline,
        MealInline,
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        Form with copy functionality for adding new Day
        """

        if obj is None:
            kwargs["form"] = DayCopyForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Copy from existing Day to new Day if possible
        """

        super().save_model(request, obj, form, change)

        copy_from = form.cleaned_data.get("copy_from")
        if copy_from and not change:
            for meal in copy_from.meal_set.order_by("time", "id").all():
                logger.debug("Copy meal: %s", meal)
                new_meal = Meal.objects.create(
                    day=obj,
                    title=meal.title,
                    time=meal.time,
                )
                new_dishes = []
                for dish in meal.dish_set.order_by("id").all():
                    logger.debug("Copy dish: %s", dish)
                    new_dishes.append(
                        Dish.objects.create(
                            meal=new_meal,
                            product=dish.product,
                            weight=dish.weight,
                            note=dish.note,
                        )
                    )

            for takingpill in copy_from.takingpill_set.order_by("time", "id").all():
                logger.debug("Copy meal: %s", takingpill)
                TakingPill.objects.create(
                    day=obj,
                    pill=takingpill.pill,
                    time=takingpill.time,
                    is_taken=False,
                    note=takingpill.note,
                )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "daily_intake":
            default_intake = DailyIntake.objects.filter(default=True).first()
            if default_intake:
                kwargs["initial"] = default_intake.id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Today", boolean=True)
    def is_today(self, obj: Day) -> bool:
        """
        Is today flag
        """

        return obj.date == datetime.date.today()

    @admin.display(description="Energy")
    def energy_colored(self, obj: Day) -> str:
        """
        Energy with color coding
        """

        if not (obj.daily_intake and obj.daily_intake.energy):
            return obj.energy

        return _colored_param(
            obj.energy, obj.energy, obj.daily_intake.energy, obj.daily_intake.energy
        )

    @admin.display(description="Proteins")
    def proteins_colored(self, obj: Day) -> str:
        """
        Proteins with color coding
        """

        if not (obj.daily_intake and obj.daily_intake.proteins):
            return obj.proteins

        return _colored_param(
            obj.proteins,
            obj.proteins,
            obj.daily_intake.proteins,
            obj.daily_intake.proteins,
        )

    @admin.display(description="Fats")
    def fats_colored(self, obj: Day) -> str:
        """
        Fats with color coding
        """

        if not (obj.daily_intake and obj.daily_intake.fats):
            return obj.fats

        return _colored_param(
            obj.fats, obj.fats, obj.daily_intake.fats, obj.daily_intake.fats
        )

    @admin.display(description="Carbs")
    def carbs_colored(self, obj: Day) -> str:
        """
        Carbs with color coding
        """

        if not (obj.daily_intake and obj.daily_intake.carbs):
            return obj.carbs

        return _colored_param(
            obj.carbs, obj.carbs, obj.daily_intake.carbs, obj.daily_intake.carbs
        )

    @admin.display(description="Dishes")
    def meals_and_dishes(self, obj: Day) -> str:
        """
        Display meals and dishes
        """

        day_url = reverse("admin:foodlog_day_change", args=[obj.pk])
        result = []

        def meal_rows(meal: Meal):
            meal_url = reverse("admin:foodlog_meal_change", args=[meal.pk])

            meal_a = format_html(
                '<a href="{}?next={}">{} ({})</a>',
                meal_url,
                day_url,
                meal.title.title,
                meal.time or "--:--",
            )
            result.append(
                f'<tr class="fl-meal-tr">'
                f"<td>{meal_a}</td>"
                f"<td>{meal.weight}</td>"
                f"<td>{meal.energy:.2f}</td>"
                f"<td>{meal.proteins:.2f}</td>"
                f"<td>{meal.fats:.2f}</td>"
                f"<td>{meal.carbs:.2f}</td>"
                f"<td>&nbsp;</td>"
                f"</tr>"
            )
            for dish in meal.dish_set.order_by("id").all():
                dish_url = reverse("admin:foodlog_dish_change", args=[dish.pk])
                dish_a = format_html(
                    '<a href="{}?next={}">{}</a>', dish_url, day_url, dish.product.title
                )
                lactose_free_icon = (
                    "yes"
                    if dish.lactose_free
                    else "unknown"
                    if dish.lactose_free is None
                    else "no"
                )

                result.append(
                    f'<tr class="fl-dish-tr">'
                    f"<td>{dish_a}</td>"
                    f"<td>{dish.weight}</td>"
                    f"<td>{dish.energy:.2f}</td>"
                    f"<td>{dish.proteins:.2f}</td>"
                    f"<td>{dish.fats:.2f}</td>"
                    f"<td>{dish.carbs:.2f}</td>"
                    f'<td><img src="/static/admin/img/icon-{lactose_free_icon}.svg"></td>'
                    f"</tr>"
                )

        def takingpill_rows(takingpill: TakingPill):
            takingpill_url = reverse(
                "admin:foodlog_takingpill_change", args=[takingpill.pk]
            )

            takingpill_a = format_html(
                '<a href="{}?next={}">{} ({})</a>',
                takingpill_url,
                day_url,
                takingpill.pill.title,
                takingpill.time or "--:--",
            )
            result.append(
                f'<tr class="fl-takingpill-tr">'
                f"<td>💊 {takingpill_a}</td>"
                f'<td><img src="/static/admin/img/icon-{"yes" if takingpill.is_taken else "no"}.svg"></td>'
                f"<td colspan=5>{takingpill.note or ''}</td>"
                f"</tr>"
            )

        def note_rows(note: Note):
            note_url = reverse("admin:foodlog_note_change", args=[note.pk])

            note_a = format_html(
                '<a href="{}?next={}">{}</a>', note_url, day_url, note.time or "--:--"
            )
            result.append(
                f'<tr class="fl-note-tr">'
                f"<td colspan=7>&#128221; {note_a} <span>{note.note or ''}</span></td>"
                f"</tr>"
            )

        items = []
        items.extend(obj.meal_set.order_by("time", "id").all())
        items.extend(obj.takingpill_set.order_by("time", "id").all())
        items.extend(obj.note_set.order_by("time", "id").all())
        items.sort(key=lambda i: i.time if i.time else datetime.datetime.now().time())
        for item in items:
            if isinstance(item, Meal):
                meal_rows(item)
            elif isinstance(item, TakingPill):
                takingpill_rows(item)
            elif isinstance(item, Note):
                note_rows(item)
            else:
                continue

        # Total
        result.append(
            f'<tr class="fl-total-tr">'
            f"<td>Total</td>"
            f"<td>{obj.weight}</td>"
            f"<td>{_colored_param(f'{obj.energy:.2f}', obj.energy, obj.daily_intake.energy)}</td>"
            f"<td>{_colored_param(f'{obj.proteins:.2f}', obj.proteins, obj.daily_intake.proteins)}</td>"
            f"<td>{_colored_param(f'{obj.fats:.2f}', obj.fats, obj.daily_intake.fats)}</td>"
            f"<td>{_colored_param(f'{obj.carbs:.2f}', obj.carbs, obj.daily_intake.carbs)}</td>"
            f"<td>&nbsp;</td>"
            f"</tr>"
        )

        # Daily intake
        result.append(
            f'<tr class="fl-total-tr">'
            f"<td>{obj.daily_intake}</td>"
            f"<td>-</td>"
            f"<td>{obj.daily_intake.energy:.2f}</td>"
            f"<td>{obj.daily_intake.proteins:.2f}</td>"
            f"<td>{obj.daily_intake.fats:.2f}</td>"
            f"<td>{obj.daily_intake.carbs:.2f}</td>"
            f"<td>&nbsp;</td>"
            f"</tr>"
        )

        # Diff
        result.append(
            f'<tr class="fl-total-tr">'
            f"<td>Diff</td>"
            f"<td>-</td>"
            f"<td>{
                _colored_param(
                    f'{obj.daily_intake.energy - obj.energy:.02f}',
                    obj.energy,
                    obj.daily_intake.energy,
                )
            }</td>"
            f"<td>{
                _colored_param(
                    f'{obj.daily_intake.proteins - obj.proteins:.2f}',
                    obj.proteins,
                    obj.daily_intake.proteins,
                )
            }</td>"
            f"<td>{_colored_param(f'{obj.daily_intake.fats - obj.fats:.2f}', obj.fats, obj.daily_intake.fats)}</td>"
            f"<td>{_colored_param(f'{obj.daily_intake.carbs - obj.carbs:.2f}', obj.carbs, obj.daily_intake.carbs)}</td>"
            f"<td>&nbsp;</td>"
            f"</tr>"
        )

        lines = "".join(result)
        header_row = (
            "<tr><th>Dish</th><th>Weight</th><th>Energy</th><th>Proteins</th><th>Fats</th><th>Carbs</th>"
            "<th>LF</th></tr>"
        )
        return mark_safe(
            f'<table class="fl-meal-dishes-table">{header_row}{lines}</table>'
        )


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = (
        "day",
        "title",
        "time",
        "energy",
        "proteins",
        "fats",
        "carbs",
        "weight",
    )

    list_filter = ("day", "title")

    readonly_fields = ("energy", "proteins", "fats", "carbs", "weight")

    inlines = (DishInline,)

    def response_change(self, request, obj):
        if "_save" in request.POST and request.GET.get("next"):
            return HttpResponseRedirect(request.GET.get("next"))
        return super().response_change(request, obj)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("product", "weight", "meal")

    list_filter = ("product", "meal")

    def response_change(self, request, obj):
        if "_save" in request.POST and request.GET.get("next"):
            return HttpResponseRedirect(request.GET.get("next"))
        return super().response_change(request, obj)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "no_lactose", "energy", "proteins", "fats", "carbs")

    list_filter = ("lactose_free",)

    search_fields = ("title",)

    @admin.display(description="No Lactose", boolean=True)
    def no_lactose(self, obj: Product) -> bool:
        """
        Lactose-free flag
        """

        return obj.lactose_free


@admin.register(TakingPill)
class TakingPillAdmin(admin.ModelAdmin):
    list_display = ("pill", "day", "time", "is_taken", "note")

    list_filter = ("pill", "day")

    search_fields = ("pill",)

    ordering = ("-day", "-time", "pill")

    def response_change(self, request, obj):
        if "_save" in request.POST and request.GET.get("next"):
            return HttpResponseRedirect(request.GET.get("next"))
        return super().response_change(request, obj)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_filter = ("day",)

    ordering = ("-day", "-time")

    search_fields = ("note",)

    def response_change(self, request, obj):
        if "_save" in request.POST and request.GET.get("next"):
            return HttpResponseRedirect(request.GET.get("next"))
        return super().response_change(request, obj)
