"""Q2 review of the fixed Q1 R0 package. Real windows are bound, never masked."""
import argparse
import copy
import csv
import io
import json
import platform
import subprocess
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pyxlsb

COMMIT = "025b3307f4fa6f98412ae2080a0c3bc883bc3900"
ZIP_SHA = "ca851d06cc6cac9931a3661dcd2fff2592172ad1c848685de7b8e0f9617ab9fb"
PACKAGE = "04_Q1光谱研究/实验验证/R0点遮蔽审批准备_v1"
CODE = "04_Q1光谱研究/代码"
MANIFEST = "01_赛题与原始数据/数据结构清单.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rejected(call, expected):
    try:
        call()
    except ValueError as exc:
        assert str(exc) == expected, str(exc)
        return str(exc)
    raise AssertionError(f"expected rejection: {expected}")


def finite_or_none(value):
    return float(value) if np.isfinite(value) else None


def r0_probes(r0, config):
    thresholds = {key:config[key] for key in ("max_time_span_s", "max_wave_span_nm")}
    result = {}
    for axis, points, too_wide in ((0,[0,.5,1.],[0,.5,1.5]),
                                  (1,[700,700.4,701.6],[700,700.4,701.601])):
        x = np.array([[0.],[np.nan],[4.]])
        if axis == 1:
            x = x.T
        center = (1,0) if axis == 0 else (0,1)
        args = (points,[700]) if axis == 0 else ([0],points)
        exact, proof = r0.reconstruct_r0_limited(x, *args, **thresholds)
        assert np.isfinite(exact[center]) and len(proof["supports"]) == 1
        assert abs(proof["supports"][0]["span"]-list(thresholds.values())[axis]) < 1e-10
        args = (too_wide,[700]) if axis == 0 else ([0],too_wide)
        rejected_output, rejected_proof = r0.reconstruct_r0_limited(x, *args, **thresholds)
        assert rejected_proof["unresolved"][center] and np.isnan(rejected_output[center])
        edge = np.full_like(x,np.nan)
        edge.flat[1:] = [2,4]
        y, proof_edge = r0.reconstruct_r0_limited(edge, *args, **thresholds)
        assert np.isnan(y.flat[0]) and proof_edge["unresolved"].flat[0]
        result[f"axis_{axis}"] = dict(allowed_points=points, too_wide_points=too_wide,
            allowed_result=float(exact[center]), allowed_trace=proof["supports"][0],
            over_span=finite_or_none(rejected_output[center]), missing_side=finite_or_none(y.flat[0]))
    x = np.array([[0.,0.,0.],[np.nan,np.nan,4.],[4.,np.nan,12.]])
    mask = np.isnan(x)
    pair = {}
    for order in config["orders"]:
        y, info = r0.reconstruct_r0_limited(x, [0,.5,1], [700,700.4,700.8], order=order, **thresholds)
        target = next(s for s in info["supports"] if s["target"]==[1,1])
        assert info["provenance"][1,1]==2 and info["used_estimated_support"][1,1]
        assert target["used_estimated_support"] and np.array_equal(x[~mask],y[~mask])
        pair[order] = dict(center=float(y[1,1]), trace=target, supports=info["supports"])
    assert np.allclose([p["center"] for p in pair.values()],[3,4],rtol=0,atol=1e-10)
    result["same_input_two_orders"] = dict(mask=np.argwhere(mask).tolist(), outcomes=pair)
    x = np.array([[np.nan],[1.],[np.nan],[3.]])
    pred, info = r0.reconstruct_r0_limited(x,[0,.5,1,1.5],[700],**thresholds)
    targets = [(0,0),(2,0)]
    truth = [7.,2.5]
    evaluated = [(abs(pred[i,j]-reference)) for (i,j),reference in zip(targets,truth)
                 if not info["unresolved"][i,j]]
    assert len(evaluated)==1 and evaluated[0]==.5
    result["coverage_oracle_q2_only"] = dict(
        requested=len(targets), resolved=len(evaluated), unresolved=len(targets)-len(evaluated),
        coverage=len(evaluated)/len(targets), mae_resolved_only=evaluated[0],
        raw_kernel_outputs=[finite_or_none(pred[i,j]) for i,j in targets],
        nominal_gate_pass=len(evaluated)==len(targets))
    return result


def tamper(r0, config):
    with tempfile.TemporaryDirectory(prefix="r0-bind-fixture-") as wd:
        path = Path(wd)
        source, code = path/"source.bin", path/"fixture.py"
        source.write_bytes(b"original fixture")
        code.write_bytes(b"# original fixture")
        x,t,w = np.array([[3.,5.],[7.,9.]]), np.array([0.,.5]),np.array([400.,400.4])
        refs = [{"reference_id":"fixture","approved":False}]
        cp = {"fixture.py":code}
        b = dict(source_sha256=r0.sha256(source),window_sha256=r0.window_digest(x,t,w),
                 config_sha256=r0.digest(config), reference_manifest_sha256=r0.digest(refs),
                 code_sha256={"fixture.py":r0.sha256(code)})
        def check(xx=x, tt=t, ww=w, cfg=config, ref=refs):
            return r0.verify_binding(xx,tt,ww,b,cfg,ref,cp,source)
        assert check() is True
        cfg = copy.deepcopy(config)
        cfg["max_time_span_s"] += .5
        outcomes = {
            "value":rejected(lambda: check(xx=x+[[1,0],[0,0]]),"actual values/coordinates binding"),
            "time":rejected(lambda: check(tt=t+[0,.1]),"actual values/coordinates binding"),
            "wavelength":rejected(lambda: check(ww=w+[0,.1]),"actual values/coordinates binding"),
            "config":rejected(lambda: check(cfg=cfg),"configuration binding"),
            "reference_manifest":rejected(lambda: check(ref=[dict(refs[0],approved=True)]),"reference manifest binding"),
        }
        code.write_bytes(b"# changed fixture")
        outcomes["code"] = rejected(check,"code binding")
        code.write_bytes(b"# original fixture")
        source.write_bytes(b"modified fixture")
        outcomes["source"] = rejected(check,"source binding")
        return outcomes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--zip",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args = p.parse_args()
    # The fixed Git bytes are authoritative even if the optional transport ZIP is inaccessible.
    def git(*words):
        return subprocess.check_output(["git","-C",str(args.repo),*words])
    assert git("rev-parse",COMMIT+"^{commit}").decode().strip()==COMMIT
    with tempfile.TemporaryDirectory(prefix="q1-r0-audit-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(io.BytesIO(git("archive","--format=zip",COMMIT,PACKAGE,CODE,MANIFEST))) as z:
            z.extractall(root)
        # No Q1 file is edited. Avoid writing Python caches beside imported snapshot code.
        import sys
        sys.dont_write_bytecode = True
        sys.path.insert(0,str(root/CODE))
        import r0_preparation as r0
        from detection_metrics_v3 import detection_metrics_v3
        package = root/PACKAGE
        checks = read_json(package/"checks_and_hashes.json")
        config = read_json(package/"config_pending.json")
        refs = read_json(package/"reference_manifest_pending.json")
        bindings = {row["reference_id"]:row for row in read_json(package/"input_bindings.json")}
        sources = {row["sheets"][0]:row for row in read_json(root/MANIFEST)}
        code_paths = {name:root/CODE/name for name in checks["code_sha256"]}
        assert not config["real_data_execution_allowed"] and config["status"]=="Pending"
        assert config["max_time_span_s"]==1.0 and config["max_wave_span_nm"]==1.6
        assert r0.digest(config)==checks["config_sha256"] and r0.digest(refs)==checks["reference_manifest_sha256"]
        assert {name:r0.sha256(path) for name,path in code_paths.items()}==checks["code_sha256"]
        files = {}
        for f in sorted([*package.iterdir(),*code_paths.values()]):
            key = f.relative_to(root).as_posix()
            assert git("show",COMMIT+":"+key)==f.read_bytes()
            files[key] = dict(sha256=r0.sha256(f), bytes=f.stat().st_size)
        assert len(files)==24
        transport = dict(found=args.zip.is_file(),expected_sha256=ZIP_SHA,actual_sha256=None,
                         matching_git_files=None, content_matches_fixed_commit=None)
        if transport["found"]:
            import hashlib
            transport["actual_sha256"] = r0.sha256(args.zip)
            with zipfile.ZipFile(args.zip) as z:
                verified = [key for key in files if key in z.namelist() and
                            hashlib.sha256(z.read(key)).hexdigest()==files[key]["sha256"]]
            transport["matching_git_files"] = len(verified)
            transport["content_matches_fixed_commit"] = (transport["actual_sha256"]==ZIP_SHA and len(verified)==24)
        frames = {(r["reference_id"],int(r["sequence"])):r for r in read_csv(package/"frame_evidence.csv")}
        stats = {r["reference_id"]:r for r in read_csv(package/"candidate_summary.csv")}
        assert len(frames)==35 and len(stats)==len(bindings)==len(refs)==5
        assert [r["reference_id"] for r in refs]==config["reference_ids"]
        assert sorted(config["reference_strata"]["background_candidate"]+
                      config["reference_strata"]["dynamic_challenge"])==sorted(bindings)
        assert sorted(map(len,config["reference_strata"].values()))==[1,4]
        evidence = []
        for ref in refs:
            rid,h = ref["reference_id"],ref["heat"]
            src = sources[h]
            path = args.repo/src["path"]
            assert ref["approved"] is False and src["sha256"]==ref["source_sha256"]==bindings[rid]["source_sha256"]
            assert path.name==ref["source_file"] and path.stat().st_size==src["bytes"]
            if src["attachment"]==1:
                assert "corrected" in path.parts
            x,t,w = r0.load_window(path,src["sha256"],h,*ref["loaded_sequence"],*ref["loaded_excel_columns"])
            print(rid, x.shape, flush=True)
            assert r0.verify_binding(x,t,w,bindings[rid],config,refs,code_paths,path) is True
            assert r0.window_digest(x,t,w)==ref["window_sha256"]
            rows = read_csv(package/(rid+"_raw_support.csv"))
            assert len(rows)==x.size==375 and len(t)==15 and len(w)==25 and not np.any(x>=65535)
            sc,ec = ref["loaded_sequence"]
            sw,ew = ref["loaded_excel_columns"]
            assert [int(row["sequence"]) for row in rows]==[i for i in range(sc,ec+1) for _ in w]
            assert [int(row["excel_column"]) for row in rows]==list(range(sw,ew+1))*len(t)
            assert np.array_equal([float(row["raw_intensity"]) for row in rows],x.ravel())
            assert np.array_equal([float(row["time_s"]) for row in rows],np.repeat(t,len(w)))
            assert np.array_equal([float(row["wavelength_nm"]) for row in rows],np.tile(w,len(t)))
            core = x[4:-4,4:-4]
            assert core.shape==(7,17) and t[[4,-5]].tolist()==ref["core_time_s"] and w[[4,-5]].tolist()==ref["core_nm"]
            maxchange = float(np.max(np.mean(abs(np.diff(core,axis=0)),axis=1)))
            assert np.isclose(maxchange,float(stats[rid]["max_frame_mean_absolute_change"]))
            for seq,tm,vals in zip(range(ref["core_sequence"][0],ref["core_sequence"][1]+1),t[4:-4],core):
                a = frames[rid,seq]
                j = int(np.argmax(vals))
                actual = dict(time_s=tm,local_max_nm=w[4+j],local_max=vals[j],local_max_index=j,
                              left_edge=vals[0],right_edge=vals[-1],left_drop=vals[j]-vals[0],
                              right_drop=vals[j]-vals[-1],median=np.median(vals),mean=np.mean(vals))
                assert all(np.isclose(float(a[k]),v,rtol=1e-12) for k,v in actual.items())
                assert (a["maximum_interior"]=="True")== (0<j<len(vals)-1)
            # Compare all loaded wavelengths to the source manifest's actual full-axis coordinates.
            full_wave = np.asarray(src["headers"][1:2048],dtype=float)
            assert np.array_equal(w,full_wave[sw-2:ew-1])
            lo,hi = (col-2 for col in ref["core_excel_columns"])
            five_step = min(min(full_wave[j+5]-full_wave[j],full_wave[j]-full_wave[j-5])
                            for j in range(lo,hi+1))
            assert five_step>config["max_wave_span_nm"] and 2.5>config["max_time_span_s"]
            evidence.append(dict(id=rid,attachment=src["attachment"],grid=ref["grid"],use=ref["proposed_use"],
                source_sha256=src["sha256"],window_sha256=ref["window_sha256"],core_points=core.size,
                loaded_points=x.size,loaded_at_or_above_cap=int(np.sum(x>=65535)),
                frame_records_verified=len(core),max_adjacent_frame_mean_abs=maxchange,
                min_five_wavelength_steps_nm=float(five_step),five_time_steps_s=2.5,
                actual_load_and_binding=True))
        good_path = args.repo/sources[refs[0]["heat"]]["path"]
        load_rejected = rejected(lambda:r0.load_window(good_path,"0"*64,refs[0]["heat"],
                                  *refs[0]["loaded_sequence"],*refs[0]["loaded_excel_columns"]),
                                 "source SHA256 mismatch")
        pred = np.array([1.,0.,np.nan,0.])
        truth = np.array([True,True,True,False])
        three = detection_metrics_v3(pred,truth,np.array([True,True,False,True]))
        assert three["unknown_positive"]==1 and three["Recall_conditional"]==.5 and three["positive_recovery_all"]==1/3
        empty = detection_metrics_v3([],np.array([],bool))
        assert empty["Recall_conditional"] is empty["positive_recovery_all"] is empty["coverage"] is None
        all_unknown = detection_metrics_v3([np.nan],np.array([True]),np.array([True]))
        assert all_unknown["Recall_conditional"] is None and all_unknown["positive_recovery_all"]==0
        bad_eligible = rejected(lambda:detection_metrics_v3(pred,truth,np.zeros(4,bool)),
                                "finite prediction outside eligible mask")
        seeds, ks, orders = config["seeds"],config["masked_points_per_region"],config["orders"]
        assert seeds==[20261127,20261128,20261129] and ks==[1,2] and config["same_masks_for_both_orders"]
        counts = dict(points_per_core=119, fractions={k:k/119 for k in ks}, sequences=len(seeds),
                      planned_runs=len(refs)*len(seeds)*len(ks)*len(orders),
                      planned_requests_per_order=len(refs)*len(seeds)*sum(ks),
                      planned_requests_all=len(refs)*len(seeds)*sum(ks)*len(orders),
                      real_mask_positions_generated=False)
        result = dict(task="J-Q1-R0-GATE-002",commit=COMMIT,transport_zip=transport,
                      python=platform.python_version(),numpy=np.__version__,pyxlsb=pyxlsb.__version__,
                      fixed_git_files=files, config_digest=r0.digest(config), reference_digest=r0.digest(refs),
                      actual_windows=evidence, wrong_source_digest_at_load=load_rejected,
                      tamper_rejections=tamper(r0,config), r0_synthetic=r0_probes(r0,config),
                      three_state=dict(example=three,empty=empty,valid_but_unknown=all_unknown,rejected=bad_eligible),
                      planned_protocol=counts, real_masking_executed=False,real_reconstruction_executed=False)
    with args.out.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write("\n")


if __name__ == "__main__":
    main()
