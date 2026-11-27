"""Signed lag scan for paired, uniformly sampled observations (offline only)."""

import numpy as np

from q2_continuous import samples


def _feature(y, mode):
    if mode == "difference":
        return np.diff(y)
    if mode == "linear_detrend":
        index = np.arange(y.size) - (y.size - 1) / 2
        return y - y.mean() - index * (index @ (y - y.mean())) / (index @ index)
    if mode == "raw":
        return y
    raise ValueError("mode must be raw, difference or linear_detrend")


def _center(a):
    scale = float(np.max(np.abs(a)))
    if scale == 0:
        return a, 0., 0.
    da = a / scale
    da -= da.mean()
    energy = da**2
    total = float(energy.sum())
    if total == 0:
        return da, 0., 0.
    weights = energy / total
    return da / np.sqrt(total), scale * np.sqrt(total / a.size), float(1 / (weights @ weights))


def estimate_delay(time, oxygen, gas, *, lag_min_s=-20., lag_max_s=20.,
                   mode="difference", min_pairs=40, min_std_oxygen=.08, min_std_gas=.08,
                   min_correlation=.45, min_peak_margin=.06, peak_exclusion_s=1.,
                   min_effective_excitation=6.):
    """Scan Corr(x[i], g[i+k]); positive lag means oxygen leads gas.

    All lags use the same oxygen indices and number of pairs. Return only a
    reportable lag after support, excitation, peak and ambiguity checks.
    """
    t, x, y = samples(time, oxygen, gas)
    dt = float((t[-1] - t[0]) / (t.size - 1))
    if not np.allclose(np.diff(t), dt, rtol=1e-9, atol=1e-12):
        raise ValueError("delay scan requires an unchanged uniform time grid")
    limits = [lag_min_s, lag_max_s, min_std_oxygen, min_std_gas, min_effective_excitation,
              min_correlation, min_peak_margin, peak_exclusion_s]
    if not np.isfinite(limits).all() or lag_min_s >= lag_max_s:
        raise ValueError("invalid scan range or threshold")
    if (type(min_pairs) is not int or min_pairs < 3 or min(min_std_oxygen, min_std_gas) <= 0
            or not 0 <= min_correlation <= 1 or not 0 < min_peak_margin <= 2 or peak_exclusion_s < 0
            or min_effective_excitation < 1):
        raise ValueError("invalid scan threshold")
    x, y = _feature(x, mode), _feature(y, mode)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("nonfinite feature after preprocessing")
    k0 = int(np.ceil(lag_min_s / dt - 1e-9))
    k1 = int(np.floor(lag_max_s / dt + 1e-9))
    if k1 - k0 < 2:
        raise ValueError("at least three trial lags are required")
    start = max(0, -k0)
    stop = min(x.size, y.size - k1)
    n = max(0, stop - start)
    result = dict(status="unidentifiable", reason=None, lag_s=None, best_lag_s=None,
                  peak_correlation=None, competing_correlation=None, peak_margin=None,
                  nominal_pairs=x.size, common_pairs=n, evaluated_lags=0, trial_lags=k1-k0+1,
                  mode=mode, dt_s=dt, oxygen_std=None, oxygen_effective_excitation=None, profile=[])
    if n < min_pairs:
        result["reason"] = "insufficient_common_support"
        return result
    center, std_x, eff_x = _center(x[start:stop])
    result.update(oxygen_std=std_x, oxygen_effective_excitation=eff_x)
    for k in range(k0, k1 + 1):
        tail, std_y, eff_y = _center(y[start+k:stop+k])
        why = None
        if std_x < min_std_oxygen or std_y < min_std_gas:
            why = "low_excitation"
        elif min(eff_x, eff_y) < min_effective_excitation:
            why = "concentrated_excitation"
        r = None if why else float(np.clip(center @ tail, -1, 1))
        result["profile"].append(dict(lag_s=k*dt, pairs=n, gas_std=std_y,
                                      gas_effective_excitation=eff_y, correlation=r, excluded=why))
    assessed = [row for row in result["profile"] if row["correlation"] is not None]
    result["evaluated_lags"] = len(assessed)
    if not assessed:
        result["reason"] = ("concentrated_excitation"
                            if any(row["excluded"] == "concentrated_excitation" for row in result["profile"])
                            else "low_excitation")
        return result
    best = max(assessed, key=lambda row: row["correlation"])
    lag = best["lag_s"]
    result.update(best_lag_s=lag, peak_correlation=best["correlation"])
    competitors = [row["correlation"] for row in assessed
                   if abs(row["lag_s"] - lag) > peak_exclusion_s + 1e-9 * dt]
    if competitors:
        result["competing_correlation"] = max(competitors)
        result["peak_margin"] = best["correlation"] - max(competitors)
    if best["correlation"] < min_correlation:
        result["reason"] = "weak_peak"
    elif lag in (k0 * dt, k1 * dt):
        result["reason"] = "search_boundary_peak"
    elif not competitors:
        result["reason"] = "no_separated_competitor"
    elif result["peak_margin"] < min_peak_margin:
        result["reason"] = "ambiguous_peak"
    else:
        result.update(status="identified", lag_s=lag)
    return result
