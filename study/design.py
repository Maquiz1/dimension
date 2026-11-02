"""Stepped-wedge design rules from protocol Table 1."""
from collections import Counter

SEQUENCES = range(1, 6)
PERIODS = range(1, 9)
CLINICS_PER_SEQUENCE = 4
CONTROL = 0
INTERVENTION = 1


def first_intervention_period(sequence):
    """Sequence 1 starts in period 3 and sequence 5 in period 7."""
    if sequence not in SEQUENCES:
        raise ValueError(f'Sequence must be 1-5, got {sequence!r}')
    return sequence + 2


def exposure(sequence, period):
    """Return CONTROL or INTERVENTION, or None until both inputs are known."""
    if sequence is None or period is None:
        return None
    if period not in PERIODS:
        raise ValueError(f'Period must be 1-8, got {period!r}')
    return INTERVENTION if period >= first_intervention_period(sequence) else CONTROL


def allocation_errors(allocation):
    """Check a {facility_code: sequence} mapping against the protocol's 5 x 4 design."""
    errors = []
    if len(allocation) != len(SEQUENCES) * CLINICS_PER_SEQUENCE:
        errors.append(f'Expected 20 clinics, got {len(allocation)}.')
    counts = Counter(allocation.values())
    for sequence in SEQUENCES:
        if counts[sequence] != CLINICS_PER_SEQUENCE:
            errors.append(f'Sequence {sequence} has {counts[sequence]} clinics, expected 4.')
    invalid = sorted(set(allocation.values()) - set(SEQUENCES), key=str)
    if invalid:
        errors.append(f'Invalid sequence values: {invalid}.')
    return errors
