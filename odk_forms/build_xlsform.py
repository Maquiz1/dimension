#!/usr/bin/env python
"""Generate XLSForms from the data dictionary, so labels and codes have one source.

Usage: python odk_forms/build_xlsform.py 5P 6P
Fields that only drive the tablet display are defined in FORMS below; server scores in
capture/scoring.py are the record.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parent.parent
DICTIONARY = ROOT / 'data_dictionary' / 'DIMENSION_Data_Dictionary_v0.1.xlsx'
OUTPUT = ROOT / 'odk_forms' / 'generated'
UNTRANSLATED = '[EN] '  # Makes a missing Swahili label obvious to anyone testing the form.
ALERT_EN = (
    'SAFETY ALERT (draft wording, decision D04): the patient endorsed this item. '
    'Tell the clinician on duty now, before continuing.'
)

COMMON_START = ['study_id', 'facility_code', 'visit_date', 'visit_type', 'form_language', 'sex']
COMMON_END = ['form_comments', 'staff_initials']
COMMON_CONSTRAINTS = {
    'visit_date': ('. <= today()', 'Date cannot be in the future.', 'Tarehe haiwezi kuwa ya baadaye.'),
}


def sum_of(prefix, count):
    return ' + '.join(f'${{{prefix}_{i:02d}}}' for i in range(1, count + 1))


FORMS = {
    '5P': {
        'form_id': 'dim_5p_phq9',
        'title': 'DIMENSION 5P PHQ-9 (DRAFT)',
        'intro': (
            'Over the last 2 weeks, how often have you been bothered by any of the following problems?',
            'Katika kipindi cha wiki mbili zilizopita ni mara ngapi umesumbuliwa na matatizo haya yafuatayo?',
        ),
        'after': {
            'phq_09': [
                {'type': 'acknowledge', 'name': 'phq_alert_ack', 'relevant': '${phq_09} > 0',
                 'en': ALERT_EN, 'required': 'yes'},
            ],
        },
        'end': [
            {'type': 'calculate', 'name': 'phq_total_display', 'calculation': sum_of('phq', 9)},
            {'type': 'note', 'name': 'phq_result', 'en': 'PHQ-9 total: ${phq_total_display}',
             'sw': 'Jumla ya PHQ-9: ${phq_total_display}'},
            {'type': 'note', 'name': 'phq_referral', 'relevant': '${phq_total_display} >= 10',
             'en': 'Score is 10 or more: refer to the clinician for further diagnosis (protocol; trigger under decision D03).'},
        ],
    },
    '6P': {
        'form_id': 'dim_6p_gad7',
        'title': 'DIMENSION 6P GAD-7 (DRAFT)',
        'intro': (
            'Over the last 2 weeks, how often have you been bothered by any of the following problems?',
            'Katika majuma mawili yaliyopita, ni mara ngapi umejihisi kupatwa na matatizo yafuatayo?',
        ),
        'after': {},
        'end': [
            {'type': 'calculate', 'name': 'gad_total_display', 'calculation': sum_of('gad', 7)},
            {'type': 'note', 'name': 'gad_result', 'en': 'GAD-7 total: ${gad_total_display}',
             'sw': 'Jumla ya GAD-7: ${gad_total_display}'},
            {'type': 'note', 'name': 'gad_referral', 'relevant': '${gad_total_display} >= 10',
             'en': 'Score is 10 or more: refer to the clinician for further diagnosis (protocol; trigger under decision D03).'},
        ],
    },
}

SURVEY_COLUMNS = [
    'type', 'name', 'label::English (en)', 'label::Kiswahili (sw)', 'required', 'relevant',
    'constraint', 'constraint_message::English (en)', 'constraint_message::Kiswahili (sw)', 'calculation',
]
CHOICE_COLUMNS = ['list_name', 'name', 'label::English (en)', 'label::Kiswahili (sw)']


def rows_as_dicts(sheet):
    rows = sheet.iter_rows(values_only=True)
    headers = next(rows)
    return [dict(zip(headers, row)) for row in rows if row[0] is not None]


def swahili(english, sw):
    return sw if sw else f'{UNTRANSLATED}{english}'


def survey_row(variable):
    """Convert one data dictionary row to an XLSForm survey row."""
    field_type = variable['Type']
    if variable['Choice list']:
        field_type = f"{field_type} {variable['Choice list']}"
    row = {
        'type': field_type,
        'name': variable['Variable'],
        'label::English (en)': variable['Label (English)'],
        'label::Kiswahili (sw)': swahili(variable['Label (English)'], variable['Label (Swahili)']),
        'required': 'yes' if variable['Required'] == 'Yes' else '',
        'relevant': variable['Relevance (ODK, proposed)'] or '',
    }
    if variable['Variable'] in COMMON_CONSTRAINTS:
        constraint, en, sw = COMMON_CONSTRAINTS[variable['Variable']]
        row.update({'constraint': constraint, 'constraint_message::English (en)': en,
                    'constraint_message::Kiswahili (sw)': sw})
    return row


def extra_row(extra):
    row = {'type': extra['type'], 'name': extra['name'], 'relevant': extra.get('relevant', ''),
           'required': extra.get('required', ''), 'calculation': extra.get('calculation', '')}
    if 'en' in extra:
        row['label::English (en)'] = extra['en']
        row['label::Kiswahili (sw)'] = swahili(extra['en'], extra.get('sw'))
    return row


def build_form(form, variables, choices):
    spec = FORMS[form]
    by_name = {v['Variable']: v for v in variables}
    survey = [{'type': t, 'name': t} for t in ('start', 'end')]
    survey.append({'type': 'deviceid', 'name': 'deviceid'})
    survey += [survey_row(by_name[name]) for name in COMMON_START]
    survey.append({'type': 'note', 'name': 'intro', 'label::English (en)': spec['intro'][0],
                   'label::Kiswahili (sw)': spec['intro'][1]})
    for variable in (v for v in variables if v['Form'] == form):
        survey.append(survey_row(variable))
        survey += [extra_row(e) for e in spec['after'].get(variable['Variable'], [])]
    survey += [extra_row(e) for e in spec['end']]
    survey += [survey_row(by_name[name]) for name in COMMON_END]

    used = {row['type'].split()[1] for row in survey if row['type'].startswith('select_')}
    missing = used - {c['List'] for c in choices}
    if missing:
        raise SystemExit(f'Choice lists missing from the dictionary: {sorted(missing)}')

    book = Workbook()
    sheet = book.active
    sheet.title = 'survey'
    sheet.append(SURVEY_COLUMNS)
    for row in survey:
        sheet.append([row.get(column, '') for column in SURVEY_COLUMNS])
    sheet = book.create_sheet('choices')
    sheet.append(CHOICE_COLUMNS)
    for choice in choices:
        if choice['List'] in used:
            sheet.append([choice['List'], str(choice['Code']), choice['Label (English)'],
                          swahili(choice['Label (English)'], choice['Label (Swahili)'])])
    sheet = book.create_sheet('settings')
    sheet.append(['form_title', 'form_id', 'version', 'default_language', 'instance_name'])
    sheet.append([spec['title'], spec['form_id'], datetime.now().strftime('%Y%m%d%H%M'),
                  'English (en)', "concat(${study_id}, ' ', ${visit_date})"])
    path = OUTPUT / f"{spec['form_id']}.xlsx"
    book.save(path)
    return path


def validate(path):
    """Convert with pyxform and run ODK Validate. Any warning fails the build."""
    xml = path.with_suffix('.xml')
    result = subprocess.run(
        [sys.executable, '-m', 'pyxform.xls2xform', str(path), str(xml), '--json', '--odk_validate'],
        capture_output=True, text=True,
    )
    try:
        # pyxform writes its JSON result to stderr.
        outcome = json.loads(result.stderr)
    except json.JSONDecodeError:
        raise SystemExit(f'Validation failed for {path.name}: {result.stderr or result.stdout}')
    if outcome['code'] != 100 or outcome['warnings']:
        raise SystemExit(f'Validation failed for {path.name}: {outcome}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('forms', nargs='+', choices=sorted(FORMS))
    args = parser.parse_args()
    if not DICTIONARY.exists():
        raise SystemExit(f'Data dictionary not found at {DICTIONARY}. It is not in git; see README.')
    book = load_workbook(DICTIONARY, data_only=True)
    variables = rows_as_dicts(book['Data Dictionary'])
    choices = rows_as_dicts(book['Choices'])
    OUTPUT.mkdir(exist_ok=True)
    for form in args.forms:
        path = build_form(form, variables, choices)
        validate(path)
        print(f'Built {path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
