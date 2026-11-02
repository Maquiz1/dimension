from datetime import date
from io import StringIO
from unittest import skipUnless

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .design import CONTROL, INTERVENTION, allocation_errors, exposure, first_intervention_period
from .models import Facility, StudyPeriod, exposure_for

# Protocol Table 1, copied as printed: C = control, I = intervention.
PROTOCOL_TABLE_1 = {
    1: 'CCIIIIII',
    2: 'CCCIIIII',
    3: 'CCCCIIII',
    4: 'CCCCCIII',
    5: 'CCCCCCII',
}


class ExposureTests(TestCase):
    def test_matches_protocol_table_1(self):
        for sequence, row in PROTOCOL_TABLE_1.items():
            for period, cell in enumerate(row, 1):
                expected = INTERVENTION if cell == 'I' else CONTROL
                self.assertEqual(exposure(sequence, period), expected, (sequence, period))

    def test_unknown_inputs_give_no_status(self):
        self.assertIsNone(exposure(None, 3))
        self.assertIsNone(exposure(2, None))

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            first_intervention_period(6)
        with self.assertRaises(ValueError):
            exposure(1, 9)


class AllocationTests(TestCase):
    def allocation(self):
        return {f'C{i:02d}': i % 5 + 1 for i in range(20)}

    def test_valid_allocation(self):
        self.assertEqual(allocation_errors(self.allocation()), [])

    def test_unbalanced_allocation(self):
        allocation = self.allocation()
        allocation['C00'] = 2 if allocation['C00'] != 2 else 3
        self.assertTrue(allocation_errors(allocation))

    def test_wrong_clinic_count(self):
        allocation = self.allocation()
        del allocation['C00']
        self.assertTrue(allocation_errors(allocation))


@skipUnless(settings.DATA_DICTIONARY_PATH.exists(), 'Data dictionary is not in git.')
class LoadSitesTests(TestCase):
    def test_loads_confirmed_list_without_allocation(self):
        call_command('load_sites', stdout=StringIO())
        self.assertEqual(Facility.objects.count(), 20)
        self.assertEqual(Facility.objects.filter(region='Dar es Salaam').count(), 14)
        self.assertEqual(Facility.objects.filter(region='Mwanza').count(), 6)
        self.assertEqual(Facility.objects.filter(has_mental_health_unit=True).count(), 4)
        self.assertFalse(Facility.objects.exclude(sequence=None).exists())
        self.assertEqual(Facility.objects.get(name='Amana').district, 'Ilala')

    def test_repeat_load_is_safe(self):
        call_command('load_sites', stdout=StringIO())
        call_command('load_sites', stdout=StringIO())
        self.assertEqual(Facility.objects.count(), 20)

    def test_loaded_allocation_cannot_change(self):
        call_command('load_sites', stdout=StringIO())
        Facility.objects.filter(pk='DSM01').update(sequence=1)
        with self.assertRaises(CommandError):
            call_command('load_sites', stdout=StringIO())


class ExposureForTests(TestCase):
    def setUp(self):
        self.facility = Facility.objects.create(
            code='T01', name='Test', facility_type='Dispensary', ward='W', clients=1,
            region='R', district='D', selection_method='M', has_mental_health_unit=False,
        )
        StudyPeriod.objects.create(number=2, start_date=date(2027, 4, 1), end_date=date(2027, 6, 30))
        StudyPeriod.objects.create(number=3, start_date=date(2027, 7, 1), end_date=date(2027, 9, 30))

    def test_no_allocation_gives_period_only(self):
        self.assertEqual(exposure_for(self.facility, date(2027, 7, 1)), (3, None))

    def test_period_boundaries(self):
        self.facility.sequence = 1
        self.assertEqual(exposure_for(self.facility, date(2027, 6, 30)), (2, CONTROL))
        self.assertEqual(exposure_for(self.facility, date(2027, 7, 1)), (3, INTERVENTION))

    def test_date_outside_periods(self):
        self.facility.sequence = 1
        self.assertEqual(exposure_for(self.facility, date(2030, 1, 1)), (None, None))
