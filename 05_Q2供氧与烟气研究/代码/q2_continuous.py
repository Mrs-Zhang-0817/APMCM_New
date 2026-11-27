"""Q2 array-only, offline candidates. Time is in seconds, volumes in m³."""

import numpy as np


def samples(time, *values, max_gap_s=None):
    """Copy and validate paired observations, including the optional gap limit."""
    t = np.array(time, dtype=float, copy=True)
    if t.ndim != 1 or t.size < 2 or not np.isfinite(t).all():
        raise ValueError("at least two finite time nodes are required")
    steps = np.diff(t)
    if not np.isfinite(steps).all() or np.any(steps <= 0):
        raise ValueError("time nodes must be strictly increasing")
    if max_gap_s is not None:
        if not np.isfinite(max_gap_s) or max_gap_s <= 0:
            raise ValueError("max_gap_s must be finite and positive")
        if np.any(steps > max_gap_s):
            raise ValueError("a gap exceeds the supported length")
    ys = tuple(np.array(y, dtype=float, copy=True) for y in values)
    if any(y.shape != t.shape or not np.isfinite(y).all() for y in ys):
        raise ValueError("each series must be finite and aligned with time")
    return (t, *ys)


def _segment(t, query):
    query = np.asarray(query, dtype=float)
    if not np.isfinite(query).all() or np.any((query < t[0]) | (query > t[-1])):
        raise ValueError("queries must be finite and inside the closed observation interval")
    i = np.clip(np.searchsorted(t, query, side="right") - 1, 0, t.size - 2)
    return query, i, query - t[i]


def _interval(cumulative, start, stop):
    a, b = np.broadcast_arrays(np.asarray(start, dtype=float), np.asarray(stop, dtype=float))
    if np.any(b < a):
        raise ValueError("integral endpoints must be ordered")
    return cumulative(b) - cumulative(a)


class Oxygen:
    """Conservative piecewise cubic O (C1) and continuous derivative q (C0)."""

    def __init__(self, time, cumulative, *, max_gap_s=None):
        self._t, self._o = samples(time, cumulative, max_gap_s=max_gap_s)
        increments = np.diff(self._o)
        if np.any(self._o < 0) or np.any(increments < 0):
            raise ValueError("cumulative oxygen must be nonnegative and nondecreasing")
        h = np.diff(self._t)
        d = increments / h
        m = np.empty_like(self._o)
        m[0], m[-1] = d[0], d[-1]
        if d.size > 1:
            candidate = (h[1:] * d[:-1] + h[:-1] * d[1:]) / (h[:-1] + h[1:])
            m[1:-1] = np.minimum(candidate, 1.5 * np.minimum(d[:-1], d[1:]))
            left = d[0] + h[0] / (h[0] + h[1]) * (d[0] - d[1])
            right = d[-1] + h[-1] / (h[-2] + h[-1]) * (d[-1] - d[-2])
            m[0] = np.clip(left, 0, 1.5 * d[0])
            m[-1] = np.clip(right, 0, 1.5 * d[-1])
        middle = 3 * d - (m[:-1] + m[1:])
        if not (np.isfinite(m).all() and np.isfinite(middle).all()):
            raise ValueError("oxygen coefficients exceed numerical range")
        self._h = h
        self._m = m
        # Bound roundoff at the zero coefficient of a mathematically nonnegative rate.
        self._middle = np.maximum(middle, 0)

    @property
    def domain(self):
        return float(self._t[0]), float(self._t[-1])

    def rate(self, time):
        """Return q(time) in m³/s, using one-sided derivatives at the endpoints."""
        _, i, elapsed = _segment(self._t, time)
        u = elapsed / self._h[i]
        return self._m[i] * (1 - u)**2 + 2 * self._middle[i] * u * (1 - u) + self._m[i + 1] * u**2

    def cumulative(self, time):
        """Return O(time) in m³, anchored at the observed first cumulative value."""
        query, i, elapsed = _segment(self._t, time)
        u = elapsed / self._h[i]
        left, mid, right = self._m[i], self._middle[i], self._m[i + 1]
        average = left + u * ((mid - left) + u * ((left - 2 * mid + right) / 3))
        return np.where(query == self._t[-1], self._o[-1], self._o[i] + elapsed * average)

    def integral(self, start, stop):
        """Return oxygen delivered over [start, stop], in m³."""
        return _interval(self.cumulative, start, stop)


class Gas:
    """Nonnegative piecewise-linear rate (C0) and exact integrated volume (C1)."""

    def __init__(self, time, rate, *, max_gap_s=None):
        self._t, self._g = samples(time, rate, max_gap_s=max_gap_s)
        if np.any(self._g < 0):
            raise ValueError("gas rate must be nonnegative")
        self._h = np.diff(self._t)
        self._prefix = np.r_[0., np.cumsum(self._h * (.5 * self._g[:-1] + .5 * self._g[1:]))]
        if not np.isfinite(self._prefix).all():
            raise ValueError("gas volume exceeds numerical range")

    @property
    def domain(self):
        return float(self._t[0]), float(self._t[-1])

    def _rate(self, i, elapsed):
        u = elapsed / self._h[i]
        return (1 - u) * self._g[i] + u * self._g[i + 1]

    def rate(self, time):
        """Return CO₂ or CO flow in m³/s."""
        _, i, elapsed = _segment(self._t, time)
        return self._rate(i, elapsed)

    def cumulative(self, time):
        """Return volume in m³ since the first time node."""
        _, i, elapsed = _segment(self._t, time)
        return self._prefix[i] + elapsed * (.5 * self._g[i] + .5 * self._rate(i, elapsed))

    def integral(self, start, stop):
        return _interval(self.cumulative, start, stop)
