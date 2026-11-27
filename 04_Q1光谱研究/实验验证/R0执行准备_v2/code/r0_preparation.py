"""Bound raw-window loader and span-limited R0. No real-experiment CLI."""
import hashlib
import json
from pathlib import Path
import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def window_digest(values, t, w):
    return digest(dict(values=np.asarray(values).tolist(), time=np.asarray(t).tolist(),
                       wavelength=np.asarray(w).tolist()))


def load_window(path, source_sha, heat, seq_start, seq_end, col_start, col_end):
    """Excel columns inclusive, 1-based; sequence range includes halo. Raw only."""
    from pyxlsb import open_workbook
    if sha256(path) != source_sha:
        raise ValueError('source SHA256 mismatch')
    if not (1 <= seq_start <= seq_end and 2 <= col_start <= col_end <= 2048):
        raise ValueError('window coordinates')
    values = []
    with open_workbook(str(path)) as book:
        if book.sheets != [heat]:
            raise ValueError('sheet mismatch')
        with book.get_sheet(1) as sheet:
            rows = sheet.rows()
            header = [c.v for c in next(rows)]
            if len(header) != 2051:
                raise ValueError('expected 2051 columns')
            all_w = np.array(header[1:2048], float)
            if not np.isfinite(all_w).all() or not (np.diff(all_w) > 0).all():
                raise ValueError('wavelength grid')
            for index, row in enumerate(rows, 1):
                cells = {c.c: c.v for c in row}
                if cells.get(0) != index:
                    raise ValueError('sequence mismatch')
                if seq_start <= index <= seq_end:
                    values.append([cells.get(j) for j in range(col_start-1, col_end)])
                if index >= seq_end:
                    break
    x = np.asarray(values, float)
    if x.shape != (seq_end-seq_start+1, col_end-col_start+1) or not np.isfinite(x).all():
        raise ValueError('incomplete/nonfinite window')
    t = (np.arange(seq_start, seq_end+1)-1)*.5
    w = all_w[col_start-2:col_end-1]
    if sha256(path) != source_sha:
        raise ValueError('source changed while reading')
    return x, t, w


def verify_binding(values, t, w, binding, config, reference_manifest, code_paths, source_path):
    """Verify raw loaded values BEFORE masking. This does not grant approval."""
    if sha256(source_path) != binding['source_sha256']:
        raise ValueError('source binding')
    if window_digest(values, t, w) != binding['window_sha256']:
        raise ValueError('actual values/coordinates binding')
    if digest(config) != binding['config_sha256']:
        raise ValueError('configuration binding')
    if digest(reference_manifest) != binding['reference_manifest_sha256']:
        raise ValueError('reference manifest binding')
    actual = {name: sha256(path) for name, path in code_paths.items()}
    if actual != binding['code_sha256']:
        raise ValueError('code binding')
    return True


def reconstruct_r0_limited(observed, t, w, *, max_time_span_s, max_wave_span_nm,
                           order='time-wave'):
    """Interior two-pass linear fill; bracket span limits are in physical units.

    Each pass freezes its support before filling the line. Estimated support from
    the previous axis is tracked, never silently presented as raw observation.
    """
    x = np.array(observed, dtype=float, copy=True)
    t, w = np.asarray(t, float), np.asarray(w, float)
    if t.ndim != 1 or w.ndim != 1 or len(t) < 1 or len(w) < 1 or x.shape != (len(t), len(w)):
        raise ValueError('shape')
    if not np.isfinite(t).all() or not np.isfinite(w).all() or not (np.diff(t)>0).all() or not (np.diff(w)>0).all() or np.isinf(x).any():
        raise ValueError('coordinates/values')
    limits = (max_time_span_s, max_wave_span_nm)
    if not np.isfinite(limits).all() or min(limits) <= 0 or order not in ('time-wave','wave-time'):
        raise ValueError('support limits/order')
    provenance = np.where(np.isfinite(x), 0, -1)
    used_estimated = np.zeros(x.shape, bool)
    spans = np.full(x.shape, np.nan)
    sources = []
    for step, axis in enumerate((0,1) if order=='time-wave' else (1,0), 1):
        coord = t if axis == 0 else w
        for k in range(x.shape[1-axis]):
            line = x[:,k] if axis == 0 else x[k,:]
            tags = provenance[:,k] if axis == 0 else provenance[k,:]
            support = np.flatnonzero(np.isfinite(line))
            for q in np.flatnonzero(~np.isfinite(line)):
                left, right = support[support<q], support[support>q]
                if not len(left) or not len(right):
                    continue
                l, r = int(left[-1]), int(right[0])
                span = float(coord[r]-coord[l])
                # Coordinate subtraction near 400 nm can round 0.8 upward.
                # Tolerance is floating-point roundoff only, not a physical allowance.
                roundoff = 8*np.finfo(float).eps*max(1.,abs(coord[l]),abs(coord[r]))
                if span > limits[axis] + roundoff:
                    continue
                ij = (int(q),k) if axis == 0 else (k,int(q))
                estimated = bool(tags[l]>0 or tags[r]>0)
                line[q] = line[l]+(line[r]-line[l])*(coord[q]-coord[l])/span
                tags[q] = step
                used_estimated[ij] = estimated
                spans[ij] = span
                sources.append(dict(target=list(ij), axis=axis, left=l, right=r,
                                    span=span, used_estimated_support=estimated))
    return x, dict(provenance=provenance, used_estimated_support=used_estimated,
                   support_span=spans, supports=sources, unresolved=~np.isfinite(x), order=order)
