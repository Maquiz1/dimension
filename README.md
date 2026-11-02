# DIMENSION data management system

Data system for the DIMENSION stepped-wedge trial of digital mental health training in 20 HIV clinics in Tanzania.

**Status: early draft, not for use with participants.** PHQ-9 and GAD-7 are the only forms so far. Their safety wording, referral trigger and Swahili text are waiting on decisions in the data dictionary.

## Design

- ODK Collect and ODK Central capture data on tablets, offline.
- Django and PostgreSQL hold the record. `pull_odk` stores raw answers, then calculates scores and study period on the server.
- Control or intervention status is calculated from the clinic's sequence and the visit date. It is never entered on a form.

| Path | Purpose |
|---|---|
| `study/` | Clinics, study periods, stepped-wedge rules |
| `capture/` | Submissions, scoring, ODK pull |
| `odk_forms/build_xlsform.py` | Generates forms from the data dictionary |
| `odk_forms/generated/` | Generated XLSForm and XForm files |

## Files not in git

`documentations/` and `data_dictionary/` are kept out of this repository, as is `.env`. Get them from the study team and place them in the project root. Without `data_dictionary/DIMENSION_Data_Dictionary_v0.1.xlsx`, `load_sites` and `build_xlsform.py` stop with an error, and the tests that need it are skipped.

## Setup

Requires Python 3.10+, Docker and Java (Java is for ODK Validate).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env               # then set the secret key and database password
docker compose up -d --wait
.venv/bin/python manage.py migrate
.venv/bin/python manage.py load_sites
.venv/bin/python manage.py test
```

## Commands

```bash
.venv/bin/python odk_forms/build_xlsform.py 5P 6P   # rebuild and validate forms
.venv/bin/python manage.py pull_odk                 # needs the ODK_* settings in .env
```

## Waiting on

- Sequence allocation and period dates from the statistician. Enter the sequence on the workbook's Sites sheet and rerun `load_sites`; it checks for 4 clinics per sequence and will not change a loaded allocation.
- An ODK Central server. `pull_odk` has only been tested against mocked responses so far.
