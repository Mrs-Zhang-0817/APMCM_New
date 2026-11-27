"""Three-state detection evaluation; no data loading or processing authorization."""
import numpy as np


def _boolean_mask(value, shape, name):
    result = np.asarray(value)
    if result.shape != shape or result.dtype != np.bool_:
        raise ValueError(f'{name} must be a boolean array of matching shape')
    return result


def detection_metrics_v3(predicted, truth, eligible=None, protected_peaks=None):
    """Evaluate 0/1/NaN predictions against explicitly supplied binary labels.

    eligible is the detector's qualification mask, not an evaluation subset:
    a finite prediction outside it is rejected as inconsistent. All supplied
    observations remain in the coverage and positive-recovery denominators.
    Callers must slice the declared evaluation population before calling.
    Unknown labels are unsupported: truth must come from a separate reference.
    """
    p = np.asarray(predicted, dtype=float)
    y = _boolean_mask(truth, p.shape, 'truth')
    if np.isinf(p).any() or np.any(np.isfinite(p) & (p != 0) & (p != 1)):
        raise ValueError('predicted values must be 0, 1, or NaN')
    assessed = np.isfinite(p)
    if eligible is not None:
        qualification = _boolean_mask(eligible, p.shape, 'eligible')
        if np.any(assessed & ~qualification):
            raise ValueError('finite prediction outside eligible mask')
    unknown = ~assessed
    positive = assessed & (p == 1)
    negative = assessed & (p == 0)
    tp = int(np.sum(positive & y))
    fp = int(np.sum(positive & ~y))
    fn = int(np.sum(negative & y))
    tn = int(np.sum(negative & ~y))
    up = int(np.sum(unknown & y))
    un = int(np.sum(unknown & ~y))
    ratio = lambda a, b: float(a / b) if b else None
    n = p.size
    out = dict(total=n, evaluated=int(assessed.sum()), unknown=int(unknown.sum()),
               positives=int(y.sum()), negatives=int((~y).sum()),
               TP=tp, FP=fp, FN=fn, TN=tn,
               unknown_positive=up, unknown_negative=un,
               coverage=ratio(int(assessed.sum()), n),
               positive_coverage=ratio(tp + fn, int(y.sum())),
               negative_coverage=ratio(fp + tn, int((~y).sum())),
               Precision=ratio(tp, tp + fp), Recall_conditional=ratio(tp, tp + fn),
               F1_conditional=ratio(2 * tp, 2 * tp + fp + fn),
               FPR_conditional=ratio(fp, fp + tn),
               positive_recovery_all=ratio(tp, int(y.sum())),
               unknown_positive_fraction=ratio(up, int(y.sum())))
    if protected_peaks is not None:
        peak = _boolean_mask(protected_peaks, p.shape, 'protected_peaks')
        count = int(peak.sum())
        evaluated = int(np.sum(peak & assessed))
        flagged = int(np.sum(peak & positive))
        out.update(protected_peak_total=count, protected_peak_evaluated=evaluated,
                   protected_peak_flagged=flagged,
                   protected_peak_unknown=int(np.sum(peak & unknown)),
                   protected_peak_coverage=ratio(evaluated, count),
                   protected_peak_flag_rate_conditional=ratio(flagged, evaluated),
                   protected_peak_flag_rate_all=ratio(flagged, count))
    assert tp + fp + fn + tn + up + un == n
    assert tp + fn + up == int(y.sum())
    return out
