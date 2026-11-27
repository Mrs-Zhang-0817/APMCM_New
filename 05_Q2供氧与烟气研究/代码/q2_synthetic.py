"""Run Q2 experiments using constructed arrays only. Writes one new JSON file."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np

from q2_continuous import Gas, Oxygen
from q2_delay import estimate_delay

SEED = 20261127
TOL = 1e-9


def error(observed, expected):
    residual = np.asarray(observed) - np.asarray(expected)
    return dict(n=residual.size, mae=float(np.mean(np.abs(residual))),
                rmse=float(np.sqrt(np.mean(residual**2))), max_abs=float(np.max(np.abs(residual))))


def hold(y, every, phase=0):
    index = np.arange(y.size)
    return y[np.maximum(0, index - (index - phase) % every)]


def integrate_model_rate(model, t):
    # Two-point Gauss quadrature integrates degree 2 on each node interval.
    mid = (t[1:] + t[:-1]) / 2
    scale = np.diff(t) / (2 * np.sqrt(3))
    return np.diff(t) * (model.rate(mid-scale) + model.rate(mid+scale)) / 2


def continuous_experiment(check):
    t = np.array([0., .4, 1.05, 1.7, 2.4, 3., 4.4, 5., 6., 7.6, 9., 12.])
    dense = np.linspace(0, 12, 1201)

    def oxygen_truth(x):
        return 4 + 2*x + .05*x**2

    def co2_truth(x):
        return 1 + .6*np.maximum(x-5, 0)

    def co_truth(x):
        return .8 + .2*x

    oxygen = Oxygen(t, oxygen_truth(t))
    co2 = Gas(t, co2_truth(t))
    co = Gas(t, co_truth(t))
    definitions = [
        ("oxygen", oxygen, 2+.1*dense, oxygen_truth(dense)),
        ("co2", co2, co2_truth(dense), dense+.3*np.maximum(dense-5, 0)**2),
        ("co", co, co_truth(dense), .8*dense+.1*dense**2),
    ]
    clean = {}
    for name, model, truth_rate, truth_cum in definitions:
        nodes = model.cumulative(t)
        interval_balance = error(integrate_model_rate(model, t), np.diff(nodes))
        query = dense[1:-1]
        derivative = (model.cumulative(query+1e-5)-model.cumulative(query-1e-5))/2e-5
        away = np.min(abs(query[:, None]-t),axis=1) > 1e-5
        independent_derivative = error(derivative[away], model.rate(query[away]))
        knot_derivative = error(derivative[~away], model.rate(query[~away]))
        additivity = float(abs(model.integral(.17, 11.37) -
                               (model.integral(.17, 4.29)+model.integral(4.29, 11.37))))
        clean[name] = dict(rate=error(model.rate(dense), truth_rate),
                           cumulative=error(model.cumulative(dense), truth_cum),
                           integral_vs_node_increment=interval_balance,
                           derivative_vs_rate=independent_derivative,
                           derivative_at_knots_finite_difference=knot_derivative,
                           min_rate=float(model.rate(dense).min()), additivity_abs=additivity)
        check(name+"_analytic_rate_and_volume", clean[name]["rate"]["max_abs"] < TOL
              and clean[name]["cumulative"]["max_abs"] < TOL)
        check(name+"_calculus", interval_balance["max_abs"] < TOL and additivity < TOL
              and independent_derivative["max_abs"] < 1e-7
              and knot_derivative["max_abs"] < 2e-6 and clean[name]["min_rate"] >= 0)
        check(name+"_closed_domain", model.domain == (0.,12.) and model.integral(12.,12.) == 0)
        for bad_time in (-.01, 12.01, np.nan):
            reject(check, name+"_reject_query_"+str(bad_time), lambda: model.rate(bad_time))
        reject(check, name+"_reverse_integral", lambda: model.integral(2, 1))
    dt = np.arange(0, 12.5, .5)
    true_o = oxygen_truth(dt)
    true_co2 = co2_truth(dt)
    distortions = {
        "hold_every_3_nodes": (hold(true_o, 3), hold(true_co2, 3)),
        "quantize_0.5_m3_0.2_m3_s": (np.round(true_o/.5)*.5, np.round(true_co2/.2)*.2),
        "hold_and_quantize": (hold(np.round(true_o/.5)*.5, 3), hold(np.round(true_co2/.2)*.2, 3)),
    }
    stress = {}
    for name, (o, g) in distortions.items():
        om, gm = Oxygen(dt, o), Gas(dt, g)
        stress[name] = dict(oxygen_rate=error(om.rate(dense), 2+.1*dense),
                            oxygen_volume=error(om.cumulative(dense), oxygen_truth(dense)),
                            co2_rate=error(gm.rate(dense), co2_truth(dense)),
                            co2_volume=error(gm.cumulative(dense), dense+.3*np.maximum(dense-5,0)**2),
                            oxygen_repeated_transitions=int(np.sum(np.diff(o)==0)),
                            gas_repeated_transitions=int(np.sum(np.diff(g)==0)),
                            transition_denominator=dt.size-1,
                            observed_oxygen_increment=float(o[-1]-o[0]),
                            true_oxygen_increment=float(true_o[-1]-true_o[0]),
                            observed_last_gas=float(g[-1]))
        q_error = error(integrate_model_rate(om, dt), np.diff(o))["max_abs"]
        check(name+"_conservation_and_nonnegativity", q_error < TOL
              and om.rate(dense).min() >= 0 and gm.rate(dense).min() >= 0
              and np.allclose(om.cumulative(dt), o, rtol=0, atol=TOL))
    zero = lambda x: .5*np.maximum(3-x,0)+.75*np.maximum(x-6,0)
    real_zero = Gas(dt, zero(dt))
    injected_zero = true_co2.copy()
    zero_nodes = (dt>=3) & (dt<=6)
    injected_zero[zero_nodes] = 0
    zero_as_observed = Gas(dt, injected_zero)
    in_zero = (dense>=3) & (dense<=6)
    stress["true_zero_vs_observation_zero"] = dict(
        zero_nodes=int(zero_nodes.sum()), observed_node_denominator=dt.size,
        true_zero_rate_error=error(real_zero.rate(dense), zero(dense)),
        zero_coded_full_rate_error=error(zero_as_observed.rate(dense), co2_truth(dense)),
        zero_coded_during_zero_rate_error=error(zero_as_observed.rate(dense[in_zero]), co2_truth(dense[in_zero])),
        zero_coded_final_volume_error=float(zero_as_observed.cumulative(12)-co2.cumulative(12)))
    check("true_zero_preserved", np.all(real_zero.rate(dense[in_zero]) == 0))
    check("observation_zero_not_corrected", np.all(zero_as_observed.rate(dt[zero_nodes]) == 0))
    turn = Oxygen(dt, 4+2*dt+3*np.maximum(dt-6, 0))
    turn_q = 2+3*(dense>=6)
    near = (dense>=5.5) & (dense<=6.5)
    stress["true_rate_step_at_6s"] = dict(near=error(turn.rate(dense[near]), turn_q[near]),
        outside=error(turn.rate(dense[~near]), turn_q[~near]),
        left_q=float(turn.rate(5.99999)), right_q=float(turn.rate(6.00001)))
    check("true_step_volume_conserved", abs(turn.integral(0,12)-42) < TOL)
    flat = Oxygen([0, .7], [4, 4])
    check("flat_oxygen_zero_rate", flat.rate(.2)==0 and flat.integral(0,.7)==0)
    two = Oxygen([1, 2.5], [3, 6])
    check("two_node_boundary_derivative", np.all(two.rate([1,2.5])==2))
    reject(check, "decreasing_oxygen", lambda: Oxygen([0,1], [2,1]))
    reject(check, "negative_gas", lambda: Gas([0,1], [1,-1]))
    reject(check, "duplicate_time", lambda: Gas([0,0], [1,1]))
    reject(check, "gap_limit", lambda: Oxygen([0,2], [0,1], max_gap_s=1))
    return dict(nodes=t.tolist(), dense_points=dense.size, stress_dt_s=.5,
                stress_nodes=dt.size, clean=clean, stress=stress)


def reject(check, name, call):
    try:
        call()
    except ValueError:
        check(name, True)
    else:
        check(name, False)


def delay_experiment(check):
    rng = np.random.default_rng(SEED)
    t = np.arange(0, 120, .5)
    index = np.arange(t.size)+50
    latent = np.convolve(rng.normal(size=t.size+100), [.12,.23,.3,.23,.12], mode="same")
    x = latent[index]

    def shifted(lag):
        return np.interp(index-lag/.5, np.arange(latent.size), latent)

    scenarios = [
        ("low_flow_CO2", 5+x, 15+1.2*shifted(8), 8., "difference"),
        ("low_flow_CO", 5+x, 30+1.6*shifted(6), 6., "difference"),
        ("high_flow_CO2", 9+x, 15+1.2*shifted(5), 5., "difference"),
        ("high_flow_CO", 9+x, 30+1.6*shifted(4), 4., "difference"),
        ("negative_sign_control", 5+x, 15+shifted(-4), -4., "difference"),
        ("off_grid", 5+x, 15+shifted(4.25), 4.25, "difference"),
        ("asynchronous_hold_raw", hold(5+x,3), hold(15+shifted(8),4,2), 8., "raw"),
        ("asynchronous_hold_difference", hold(5+x,3), hold(15+shifted(8),4,2), 8., "difference"),
        ("common_linear_trend_raw", 5+x+.3*t, 15+shifted(8)+.6*t, 8., "raw"),
        ("common_linear_trend_difference", 5+x+.3*t, 15+shifted(8)+.6*t, 8., "difference"),
        ("common_linear_trend_detrended", 5+x+.3*t, 15+shifted(8)+.6*t, 8., "linear_detrend"),
        ("common_step_only", 5+5*(t>=50), 15+8*(t>=50), None, "difference"),
        ("common_driver_no_transport", 5+x, 15+1.2*x, None, "difference"),
        ("low_excitation", 5+1e-4*x, 15+1e-4*shifted(8), 8., "difference"),
        ("low_gas_excitation", 5+x, np.full_like(t,15), 8., "difference"),
        ("periodic_alias", 5+np.sin(np.pi*t/2), 15+np.sin(np.pi*(t-1.5)/2), 1.5, "difference"),
        ("boundary", 5+x, 15+shifted(20), 20., "difference"),
    ]
    params = dict(lag_min_s=-20., lag_max_s=20., min_pairs=40, min_std_oxygen=.08,
                  min_std_gas=.08, min_correlation=.45, min_peak_margin=.06, peak_exclusion_s=1.,
                  min_effective_excitation=6.)
    results = {}
    for name, o, gas, truth, mode in scenarios:
        result = estimate_delay(t, o, gas, mode=mode, **params)
        lag = result["lag_s"]
        result.update(true_transport_lag_s=truth, input_nodes=t.size,
                      signed_error_s=lag-truth if lag is not None and truth is not None else None)
        results[name] = result
        check(name+"_common_pairs", all(row["pairs"]==result["common_pairs"] for row in result["profile"]))
    for name in ("low_flow_CO2", "low_flow_CO", "high_flow_CO2", "high_flow_CO", "negative_sign_control",
                 "common_linear_trend_difference", "common_linear_trend_detrended"):
        check(name+"_known_lag", results[name]["signed_error_s"] is not None
              and abs(results[name]["signed_error_s"]) < TOL)
    check("off_grid_half_step_error", results["off_grid"]["signed_error_s"] is not None
          and abs(results["off_grid"]["signed_error_s"]) <= .25+TOL)
    for name in ("low_excitation", "low_gas_excitation"):
        check(name+"_reject", results[name]["status"]=="unidentifiable"
              and results[name]["reason"]=="low_excitation" and results[name]["lag_s"] is None)
    check("periodic_alias_reject", results["periodic_alias"]["status"]=="unidentifiable")
    check("boundary_reject", results["boundary"]["reason"]=="search_boundary_peak")
    check("single_step_reject", results["common_step_only"]["reason"]=="concentrated_excitation")
    check("common_driver_noncausal_counterexample", results["common_driver_no_transport"]["lag_s"]==0)
    short = estimate_delay(t[:60], x[:60], shifted(8)[:60], **params)
    check("short_support_reject", short["reason"]=="insufficient_common_support")
    reject(check, "nonuniform_lag_grid", lambda: estimate_delay([0,1,3], [2,3,4], [5,6,7]))
    return dict(seed=SEED, dt_s=.5, settings=params, scenarios=results, short_support=short)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="path to a new JSON result")
    args = parser.parse_args()
    checks = {}

    def check(name, passed):
        checks[name] = bool(passed)

    result = dict(task="B-Q2-SIM-001", seed=SEED, real_workbooks_read=False,
                  python=platform.python_version(), numpy=np.__version__)
    result["continuous"] = continuous_experiment(check)
    result["delay"] = delay_experiment(check)
    result["checks"] = checks
    code = Path(__file__).resolve().parent
    result["code_sha256"] = {name: hashlib.sha256((code/name).read_bytes()).hexdigest()
                             for name in ("q2_continuous.py","q2_delay.py","q2_synthetic.py")}
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    failed = [name for name, passed in checks.items() if not passed]
    print(f"{len(checks)-len(failed)}/{len(checks)} checks passed. Output: {args.out}")
    if failed:
        raise SystemExit(f"Failed: {failed}")


if __name__ == "__main__":
    main()
