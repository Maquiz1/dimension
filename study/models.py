from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from . import design


class Facility(models.Model):
    code = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    facility_type = models.CharField(max_length=50)
    ward = models.CharField(max_length=50)
    clients = models.PositiveIntegerField()
    region = models.CharField(max_length=50)
    district = models.CharField(max_length=50)
    selection_method = models.CharField(max_length=50)
    has_mental_health_unit = models.BooleanField()
    sequence = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Set only from the statistician allocation by the load_sites command.',
    )

    class Meta:
        ordering = ['code']
        verbose_name_plural = 'facilities'

    def __str__(self):
        return f'{self.code} {self.name}'


class StudyPeriod(models.Model):
    number = models.PositiveSmallIntegerField(
        primary_key=True, validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'Period {self.number}'

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError('Start date must not be after end date.')
        overlapping = StudyPeriod.objects.exclude(pk=self.pk).filter(
            start_date__lte=self.end_date, end_date__gte=self.start_date
        )
        if overlapping.exists():
            raise ValidationError('Study periods must not overlap.')

    @classmethod
    def number_for(cls, visit_date):
        """Return the period containing a date, or None if none is defined."""
        period = cls.objects.filter(start_date__lte=visit_date, end_date__gte=visit_date).first()
        return period.number if period else None


def exposure_for(facility, visit_date):
    """Return (period, exposure). Either is None until the statistician's inputs are loaded."""
    period = StudyPeriod.number_for(visit_date)
    return period, design.exposure(facility.sequence, period)
