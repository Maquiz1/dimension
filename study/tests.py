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
    def test_loads_confirmed_list_with_agreed_allocation(self):
        call_command('load_sites', stdout=StringIO())
        self.assertEqual(Facility.objects.count(), 20)
        self.assertEqual(Facility.objects.filter(region='Dar es Salaam').count(), 14)
        self.assertEqual(Facility.objects.filter(region='Mwanza').count(), 6)
        self.assertEqual(Facility.objects.filter(has_mental_health_unit=True).count(), 4)
        self.assertEqual(Facility.objects.get(name='Amana').district, 'Ilala')
        # Stratified allocation agreed by the study team on 26 November 2026 (dictionary v0.4, D07)
        for sequence in range(1, 6):
            clinics = Facility.objects.filter(sequence=sequence)
            self.assertEqual(clinics.count(), 4, sequence)
            self.assertTrue(clinics.filter(region='Mwanza').exists(), sequence)
        self.assertEqual(Facility.objects.get(name='Sekou-Toure RRH').sequence, 1)
        self.assertEqual(Facility.objects.get(name='Buzuruga').sequence, 5)

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


class DashboardTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from capture.ingest import ingest_record

        self.facility = Facility.objects.create(
            code='T01', name='Test Clinic', facility_type='Dispensary', ward='W', clients=1,
            region='Dar es Salaam', district='D', selection_method='M', has_mental_health_unit=True,
        )
        record = {f'phq_{i:02d}': '1' for i in range(1, 10)}
        record.update({'__id': 'uuid:1', 'study_id': 'SECRET-ID-001', 'facility_code': 'T01',
                       'visit_date': '2027-07-01', 'phq_09': '2'})
        ingest_record('dim_5p_phq9', record)
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)

    def test_requires_staff_login(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_shows_counts_but_no_participant_ids(self):
        self.client.force_login(self.staff)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context['submission_count'], 1)
        self.assertEqual(context['item9_alerts'], 1)
        self.assertEqual({b['label']: b['count'] for b in context['phq_bands']}['Moderate'], 1)
        self.assertContains(response, 'Test Clinic')
        self.assertNotContains(response, 'SECRET-ID-001')

    def test_wedge_matches_protocol_table_1(self):
        self.client.force_login(self.staff)
        wedge = self.client.get('/').context['wedge']
        for row in wedge:
            printed = ''.join('I' if c['intervention'] else 'C' for c in row['cells'])
            self.assertEqual(printed, PROTOCOL_TABLE_1[row['sequence']])
