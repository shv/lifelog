from django.db import models


class Product(models.Model):
    """
    Product. Contains all information about product's calories, proteins, fats, and carbs.
    """

    title = models.CharField(
        "Title", max_length=150, unique=True, null=False, blank=False
    )
    energy = models.FloatField("Energy", null=False, blank=False)
    proteins = models.FloatField("Proteins", null=False, blank=False)
    fats = models.FloatField("Fats", null=False, blank=False)
    carbs = models.FloatField("Carbs", null=False, blank=False)
    sugar = models.FloatField("Sugar", null=True, blank=True)
    salt = models.FloatField("Salt", null=True, blank=True)
    note = models.CharField("Note", max_length=150, null=True, blank=True)
    rate = models.IntegerField("Rate", null=True, blank=True)
    lactose_free = models.BooleanField(
        "Lactose-free", null=True, blank=True, default=None
    )
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    def __str__(self) -> str:
        """
        String representation
        """

        return str(self.title)

    class Meta:
        """
        Model configuration
        """

        ordering = ("title",)
        verbose_name = "Product"
        verbose_name_plural = "Products"


class DailyIntake(models.Model):
    """
    Daily consumption norm
    """

    title = models.CharField(
        "Title", max_length=150, unique=True, null=False, blank=False
    )
    default = models.BooleanField("Default", null=False, blank=False, default=False)
    energy = models.FloatField("Energy", null=False, blank=False)
    proteins = models.FloatField("Proteins", null=False, blank=False)
    fats = models.FloatField("Fats", null=False, blank=False)
    carbs = models.FloatField("Carbs", null=False, blank=False)
    sugar = models.FloatField("Sugar", null=True, blank=True)
    salt = models.FloatField("Salt", null=True, blank=True)
    note = models.CharField("Note", max_length=150, null=True, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    def save(self, *args, **kwargs) -> None:
        """
        There must be only 1 default intake
        """

        if self.default:
            DailyIntake.objects.update(default=False)
        else:
            another = DailyIntake.objects.filter(default=True).first()
            if not another:
                self.default = True

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """
        String representation
        """

        return str(self.title)

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Daily Intake"
        verbose_name_plural = "Daily Intakes"


class Day(models.Model):
    """
    Day
    """

    date = models.DateField("Date", unique=True, null=False, blank=False)
    daily_intake = models.ForeignKey(
        DailyIntake,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Daily Intake",
    )
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    @property
    def energy(self):
        return round(sum([meal.energy for meal in self.meal_set.all()]), 2)

    @property
    def proteins(self):
        return round(sum([meal.proteins for meal in self.meal_set.all()]), 2)

    @property
    def fats(self):
        return round(sum([meal.fats for meal in self.meal_set.all()]), 2)

    @property
    def carbs(self):
        return round(sum([meal.carbs for meal in self.meal_set.all()]), 2)

    @property
    def weight(self):
        return round(sum([meal.weight for meal in self.meal_set.all()]), 2)

    def __str__(self) -> str:
        """
        String representation
        """

        return str(self.date)

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Day"
        verbose_name_plural = "Days"


class MealTitle(models.Model):
    """
    Meal name
    """

    title = models.CharField(
        "Title", max_length=150, unique=True, null=False, blank=False
    )
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    def __str__(self) -> str:
        """
        String representation
        """

        return str(self.title)

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Meal Title"
        verbose_name_plural = "Meal Titles"


class Meal(models.Model):
    """
    Meal
    """

    title = models.ForeignKey(
        MealTitle,
        null=False,
        blank=False,
        on_delete=models.RESTRICT,
        verbose_name="Title",
    )
    day = models.ForeignKey(
        Day, null=False, blank=False, on_delete=models.RESTRICT, verbose_name="Day"
    )
    time = models.TimeField("Time", null=True, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    @property
    def energy(self):
        return round(sum([dish.energy for dish in self.dish_set.all()]), 2)

    @property
    def proteins(self):
        return round(sum([dish.proteins for dish in self.dish_set.all()]), 2)

    @property
    def fats(self):
        return round(sum([dish.fats for dish in self.dish_set.all()]), 2)

    @property
    def carbs(self):
        return round(sum([dish.carbs for dish in self.dish_set.all()]), 2)

    @property
    def weight(self):
        return round(sum([dish.weight for dish in self.dish_set.all()]), 2)

    def __str__(self) -> str:
        """
        String representation
        """

        return f"{self.day} {self.title}"

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Meal"
        verbose_name_plural = "Meals"


class Dish(models.Model):
    """
    Dish in a meal
    """

    product = models.ForeignKey(
        Product,
        null=False,
        blank=False,
        on_delete=models.RESTRICT,
        verbose_name="Product",
    )
    meal = models.ForeignKey(
        Meal, null=False, blank=False, on_delete=models.RESTRICT, verbose_name="Meal"
    )
    weight = models.IntegerField("Weight", null=False, blank=False)
    note = models.CharField("Note", max_length=150, null=True, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    @property
    def energy(self):
        return round(self.product.energy * self.weight / 100, 2)

    @property
    def proteins(self):
        return round(self.product.proteins * self.weight / 100, 2)

    @property
    def fats(self):
        return round(self.product.fats * self.weight / 100, 2)

    @property
    def carbs(self):
        return round(self.product.carbs * self.weight / 100, 2)

    @property
    def lactose_free(self):
        return self.product.lactose_free

    def __str__(self) -> str:
        """
        String representation
        """

        return f"{self.product} {self.weight}"

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Dish"
        verbose_name_plural = "Dishes"


class Pill(models.Model):
    """
    Pill.
    """

    title = models.CharField(
        "Title", max_length=150, unique=True, null=False, blank=False
    )
    note = models.CharField("Note", max_length=150, null=True, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    def __str__(self) -> str:
        """
        String representation
        """

        return str(self.title)

    class Meta:
        """
        Model configuration
        """

        ordering = ("title",)
        verbose_name = "Pill"
        verbose_name_plural = "Pills"


class TakingPill(models.Model):
    """
    Taking pills
    """

    pill = models.ForeignKey(
        Pill, null=False, blank=False, on_delete=models.RESTRICT, verbose_name="Pill"
    )
    day = models.ForeignKey(
        Day, null=False, blank=False, on_delete=models.RESTRICT, verbose_name="Day"
    )
    time = models.TimeField("Time", null=True, blank=True)
    is_taken = models.BooleanField("Is taken", null=False, blank=False, default=False)
    note = models.CharField("Note", max_length=150, null=True, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    def __str__(self) -> str:
        """
        String representation
        """

        return f"{self.pill} {self.day} {self.time}"

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Pill Taking"
        verbose_name_plural = "Pill Taking"


class Note(models.Model):
    """
    Notes for the day
    """

    day = models.ForeignKey(
        Day, null=False, blank=False, on_delete=models.RESTRICT, verbose_name="Day"
    )
    time = models.TimeField("Time", null=True, blank=True)
    note = models.TextField("Note", null=False, blank=False)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    def __str__(self) -> str:
        """
        String representation
        """

        return f"{self.day} {self.time} {self.note[:50]}"

    class Meta:
        """
        Model configuration
        """

        verbose_name = "Note"
        verbose_name_plural = "Notes"
