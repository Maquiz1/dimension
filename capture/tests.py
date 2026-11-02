from datetime import date
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from openpyxl import load_workbook

from study.models import Facility, StudyPeriod

from .ingest import ingest_record
from .models import FormSubmission
from .odk import CentralClient
from .scoring import score_gad7, score_phq9


def phq(values):
    return {f'phq_{i:02d}': str(v) for i, v in enumerate(values, 1)}


def gad(values):
    return {f'gad_{i:02d}': str(v) for i, v in enumerate(values, 1)}


class ScoringTests(SimpleTestCase):
    def test_phq_bands_at_every_boundary(self):
        for total, band in [(0, 'minimal'), (4, 'minimal'), (5, 'mild'), (9, 'mild'), (10, 'moderate'),
                            (14, 'moderate'), (15, 'moderately_severe'), (19, 'moderately_severe'),
                            (20, 'severe'), (27, 'severe')]:
            values = [3] * (total // 3) + [total % 3] + [0] * 9
            scores = score_phq9(phq(values[:9]))
            self.assertEqual(scores['phq_total'], total)
            self.assertEqual(scores['phq_band'], band)

    def test_gad_bands_at_every_boundary(self):
        for total, band in [(0, 'minimal'), (4, 'minimal'), (5, 'mild'), (9, 'mild'), (10, 'moderate'),
                            (14, 'moderate'), (15, 'severe'), (21, 'severe')]:
            values = [3] * (total // 3) + [total % 3] + [0] * 7
            scores = score_gad7(gad(values[:7]))
            self.assertEqual(scores['gad_total'], total)
            self.assertEqual(scores['gad_band'], band)

    def test_referral_threshold(self):
        self.assertEqual(score_phq9(phq([3, 3, 3, 0, 0, 0, 0, 0, 0]))['phq_refer'], 0)
        self.assertEqual(score_phq9(phq([3, 3, 3, 1, 0, 0, 0, 0, 0]))['phq_refer'], 1)
        self.assertEqual(score_gad7(gad([3, 3, 3, 0, 0, 0, 0]))['gad_refer'], 0)
        self.assertEqual(score_gad7(gad([3, 3, 3, 1, 0, 0, 0]))['gad_refer'], 1)

    def test_item9_alert_with_low_total(self):
        scores = score_phq9(phq([0, 0, 0, 0, 0, 0, 0, 0, 1]))
        self.assertEqual(scores['phq_total'], 1)
        self.assertEqual(scores['phq_refer'], 0)
        self.assertEqual(scores['phq_item9_alert'], 1)

    def test_item9_alert_on_incomplete_form(self):
        answers = phq([0, 0, 0, 0, 0, 0, 0, 0, 2])
        del answers['phq_01']
        scores = score_phq9(answers)
        self.assertIsNone(scores['phq_total'])
        self.assertEqual(scores['phq_item9_alert'], 1)

    def test_out_of_range_answer_gives_no_total(self):
        self.assertIsNone(score_phq9(phq([4, 0, 0, 0, 0, 0, 0, 0, 0]))['phq_total'])


class IngestTests(TestCase):
    def setUp(self):
        self.facility = Facility.objects.create(
            code='T01', name='Test', facility_type='Dispensary', ward='W', clients=1,
            region='R', district='D', selection_method='M', has_mental_health_unit=False, sequence=1,
        )
        StudyPeriod.objects.create(number=3, start_date=date(2027, 7, 1), end_date=date(2027, 9, 30))

    def record(self, **changes):
        record = {
            '__id': 'uuid:test-1',
            '__system': {'submissionDate': '2027-07-02T08:00:00.000Z', 'formVersion': '1'},
            'study_id': 'TEST-001', 'facility_code': 'T01', 'visit_date': '2027-07-02',
            **phq([1, 1, 1, 1, 1, 1, 1, 1, 1]),
        }
        record.update(changes)
        return record

    def score(self, submission, variable):
        return submission.scores.get(variable=variable)

    def test_scores_and_exposure(self):
        submission = ingest_record('dim_5p_phq9', self.record())
        self.assertFalse(submission.needs_review)
        self.assertEqual((submission.study_period, submission.exposure), (3, 1))
        self.assertEqual(self.score(submission, 'phq_total').number_value, 9)
        self.assertEqual(self.score(submission, 'phq_band').text_value, 'mild')
        self.assertEqual(self.score(submission, 'phq_item9_alert').number_value, 1)

    def test_repeat_ingest_updates_without_duplicating(self):
        ingest_record('dim_5p_phq9', self.record())
        submission = ingest_record('dim_5p_phq9', self.record(phq_01='3'))
        self.assertEqual(FormSubmission.objects.count(), 1)
        self.assertEqual(submission.scores.filter(variable='phq_total').count(), 1)
        self.assertEqual(self.score(submission, 'phq_total').number_value, 11)

    def test_problem_records_are_kept_and_flagged(self):
        submission = ingest_record('dim_5p_phq9', self.record(facility_code='NOPE', study_id=None, visit_date=None))
        self.assertTrue(submission.needs_review)
        self.assertIn('facility', submission.review_reason)
        self.assertIn('study_id', submission.review_reason)
        self.assertIn('visit_date', submission.review_reason)

    def test_incomplete_scale_is_flagged(self):
        submission = ingest_record('dim_5p_phq9', self.record(phq_01=None))
        self.assertTrue(submission.needs_review)
        self.assertIsNone(self.score(submission, 'phq_total').number_value)


class CentralClientTests(SimpleTestCase):
    def response(self, payload):
        response = mock.Mock()
        response.json.return_value = payload
        return response

    def test_reads_every_page(self):
        with mock.patch('capture.odk.requests.Session') as session:
            session.return_value.headers = {}
            session.return_value.post.return_value = self.response({'token': 't'})
            session.return_value.get.side_effect = [
                self.response({'value': [{'__id': 'a'}, {'__id': 'b'}]}),
                self.response({'value': [{'__id': 'c'}]}),
            ]
            client = CentralClient('https://x/', 'e', 'p', 1)
            client.PAGE_SIZE = 2
            self.assertEqual([r['__id'] for r in client.submissions('f')], ['a', 'b', 'c'])
            self.assertEqual(session.return_value.headers['Authorization'], 'Bearer t')


class PullCommandTests(SimpleTestCase):
    @mock.patch.object(settings, 'ODK_URL', '')
    def test_requires_configuration(self):
        with self.assertRaises(CommandError):
            call_command('pull_odk')


class GeneratedFormTests(SimpleTestCase):
    XF = '{http://www.w3.org/2002/xforms}'
    GENERATED = Path(settings.BASE_DIR) / 'odk_forms' / 'generated'

    def survey(self, name):
        sheet = load_workbook(self.GENERATED / f'{name}.xlsx')['survey']
        rows = sheet.iter_rows(values_only=True)
        headers = next(rows)
        return {row[1]: dict(zip(headers, row)) for row in rows}

    def bindings(self, name):
        root = ElementTree.parse(self.GENERATED / f'{name}.xml').getroot()
        return {b.get('nodeset').split('/')[-1]: b for b in root.iter(self.XF + 'bind')}

    def test_phq_items_are_required_and_alert_follows_item9(self):
        survey = self.survey('dim_5p_phq9')
        names = list(survey)
        for i in range(1, 10):
            self.assertEqual(survey[f'phq_{i:02d}']['type'], 'select_one phq4')
            self.assertEqual(survey[f'phq_{i:02d}']['required'], 'yes')
        self.assertEqual(names.index('phq_alert_ack'), names.index('phq_09') + 1)
        self.assertEqual(survey['phq_alert_ack']['type'], 'acknowledge')
        self.assertEqual(survey['phq_alert_ack']['relevant'], '${phq_09} > 0')

    def test_answer_scores_match_server(self):
        for name, variable in [('dim_5p_phq9', 'phq4'), ('dim_6p_gad7', 'gad4')]:
            sheet = load_workbook(self.GENERATED / f'{name}.xlsx')['choices']
            codes = [row[1] for row in sheet.iter_rows(values_only=True) if row[0] == variable]
            self.assertEqual(codes, ['0', '1', '2', '3'])

    def test_all_twenty_clinics_are_choices(self):
        sheet = load_workbook(self.GENERATED / 'dim_6p_gad7.xlsx')['choices']
        self.assertEqual(sum(1 for row in sheet.iter_rows(values_only=True) if row[0] == 'facility'), 20)

    def test_swahili_item_labels_come_from_crf(self):
        survey = self.survey('dim_6p_gad7')
        for i in range(1, 8):
            self.assertFalse(survey[f'gad_{i:02d}']['label::Kiswahili (sw)'].startswith('[EN]'))

    def test_exposure_is_not_on_the_form(self):
        for name in ['dim_5p_phq9', 'dim_6p_gad7']:
            self.assertNotIn('exposure', self.survey(name))
            self.assertNotIn('sequence', self.survey(name))
