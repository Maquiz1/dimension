from django.db import models


class FormSubmission(models.Model):
    """One ODK submission. Raw answers are kept unchanged; everything else is derived."""
    instance_id = models.CharField(max_length=100, unique=True)
    xml_form_id = models.CharField(max_length=50, db_index=True)
    form_version = models.CharField(max_length=30, blank=True)
    answers = models.JSONField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now=True)

    study_id = models.CharField(max_length=30, db_index=True, blank=True)
    facility = models.ForeignKey('study.Facility', null=True, blank=True, on_delete=models.PROTECT)
    visit_date = models.DateField(null=True, blank=True)
    study_period = models.PositiveSmallIntegerField(null=True, blank=True)
    exposure = models.PositiveSmallIntegerField(null=True, blank=True)

    needs_review = models.BooleanField(default=False, db_index=True)
    review_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.xml_form_id} {self.study_id} {self.visit_date}'


class DerivedScore(models.Model):
    submission = models.ForeignKey(FormSubmission, related_name='scores', on_delete=models.CASCADE)
    variable = models.CharField(max_length=40, db_index=True)
    number_value = models.IntegerField(null=True, blank=True)
    text_value = models.CharField(max_length=40, blank=True)
    rule_version = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['submission', 'variable'], name='unique_score_per_submission'),
        ]

    def __str__(self):
        return f'{self.variable}={self.number_value if self.number_value is not None else self.text_value}'
