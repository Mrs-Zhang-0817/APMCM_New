"""Independent small analytic probes against frozen Q2 Git objects. No workbook IO."""
import argparse
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path
import numpy as np

REF='61dc006987a7c7260998aabb8bcd13c826c4cd97'
BASE='05_Q2供氧与烟气研究/'
SIM=BASE+'研究成果/B-Q2-SIM-001_v01/'


def blob(path):return subprocess.check_output(['git','show',REF+':'+path])


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    source_hash={}
    def read(path):
        data=blob(path);source_hash[path]=hashlib.sha256(data).hexdigest();return data
    def load(name):
        module=types.ModuleType(name);sys.modules[name]=module
        exec(compile(read(BASE+'代码/'+name+'.py'),name+'.py','exec'),module.__dict__)
        return module
    continuous=load('q2_continuous');delay=load('q2_delay')
    configs={name:json.loads(read(SIM+name)) for name in ['连续重构_冻结审批配置.json','延迟识别_冻结审批配置.json']}
    sim=json.loads(read(SIM+'模拟结果.json'))
    read(BASE+'代码/q2_synthetic.py');read(SIM+'实现与模拟报告.md')
    checks=[]
    def record(name,passed,**evidence):
        checks.append(dict(name=name,passed=bool(passed),**evidence))
    t=np.array([0.,.7,2.3,5.]);query=np.linspace(0,5,1001)
    oxygen=continuous.Oxygen(t,7+2*t);gas=continuous.Gas(t,1+3*t)
    for name,actual,expected in [('oxygen_linear_cumulative',oxygen.cumulative(query),7+2*query),
                                  ('oxygen_linear_derivative',oxygen.rate(query),np.full(query.shape,2.)),
                                  ('gas_linear_rate',gas.rate(query),1+3*query),
                                  ('gas_exact_cumulative',gas.cumulative(query),query+1.5*query**2)]:
        err=float(np.max(abs(actual-expected)));record(name,err<1e-10,max_abs_error=err,n=len(query))
    a,b,c=.13,1.71,4.83
    for name,model in [('oxygen',oxygen),('gas',gas)]:
        add=float(abs(model.integral(a,c)-model.integral(a,b)-model.integral(b,c)))
        derivative=(model.cumulative(query[1:-1]+1e-5)-model.cumulative(query[1:-1]-1e-5))/2e-5
        err=float(np.max(abs(derivative-model.rate(query[1:-1]))))
        record(name+'_additivity_and_finite_difference',add<1e-10 and err<1e-7,
               additivity_abs_error=add,derivative_max_abs_error=err,n=999)
    # New nonlinear, nonuniform monotone case: test properties, not exact recovery of a cubic.
    o2=continuous.Oxygen(t,[1.,1.1,8.,8.])
    knots=t[1:-1]; eps=1e-7
    continuity=float(np.max(abs(o2.rate(knots-eps)-o2.rate(knots+eps))))
    min_rate=float(o2.rate(query).min())
    record('nonlinear_monotone_support',min_rate>=-1e-12 and continuity<1e-4,
           min_rate=min_rate,knot_one_sided_difference=continuity)
    held=continuous.Oxygen([0,.5,1,1.5,2],[0,0,2,2,4]);hq=np.linspace(0,2,2001)
    qerr=float(np.mean(abs(held.rate(hq)-2)))
    balance=float(held.integral(0,2))
    record('holding_conserves_but_rate_is_biased',abs(balance-4)<1e-12 and qerr>1,
           integral=balance,true_integral=4.,rate_mae=qerr,min_rate=float(held.rate(hq).min()),
           max_rate=float(held.rate(hq).max()))
    def rejects(call):
        try:call()
        except ValueError:return True
        return False
    invalid={'outside':lambda:gas.rate(-.1),'reverse_integral':lambda:gas.integral(2,1),
             'duplicate_time':lambda:continuous.Oxygen([0,0],[0,1]),
             'negative_gas':lambda:continuous.Gas([0,1],[0,-1]),
             'decreasing_oxygen':lambda:continuous.Oxygen([0,1],[2,1]),
             'gap_limit':lambda:continuous.Gas([0,1.1],[0,1],max_gap_s=1),
             'nonfinite':lambda:continuous.Gas([0,1],[0,np.nan])}
    record('invalid_inputs_and_domain',all(rejects(f) for f in invalid.values()),cases=list(invalid))
    # Continuous API accepts nonuniform time by design; source grid checking must be in runner.
    record('off_grid_is_not_rejected_by_array_api',not rejects(lambda:continuous.Gas([0,.7,1],[1,2,3])),
           interpretation='configuration promises source-grid rejection; needs runner check, not changing continuous math API')
    rng=np.random.default_rng(72819);n=400;dt=.5;times=np.arange(n)*dt
    x=4+rng.uniform(-1,1,n)
    lag_results={}
    for label,k in [('positive',12),('negative',-8),('boundary',40)]:
        y=np.full(n,4.)
        if k>0:y[k:]=x[:-k]
        else:y[:k]=x[-k:]
        result=delay.estimate_delay(times,x,y)
        lag_results[label]=result
        expected=k*dt
        passed=result['status']=='identified' and result['lag_s']==expected if label!='boundary' else result['status']=='unidentifiable' and result['reason']=='search_boundary_peak'
        record('delay_'+label,passed,expected_lag_s=expected,status=result['status'],reason=result['reason'],lag_s=result['lag_s'],common_pairs=result['common_pairs'])
    result=delay.estimate_delay(times,np.ones(n),np.ones(n))
    record('delay_unexcited_rejection',result['status']=='unidentifiable',reason=result['reason'],lag_s=result['lag_s'])
    confounded=delay.estimate_delay(times,x,x)
    record('common_driver_is_statistical_not_transport',confounded['status']=='identified' and confounded['lag_s']==0,
           lag_s=confounded['lag_s'],interpretation='same latent signal, no independently specified transport')
    # Verify configuration code/evidence hashes against frozen Git bytes; no historical results rerun.
    config_integrity={}
    for name,cfg in configs.items():
        items={}
        for code,expected in cfg['code_sha256'].items():
            path=BASE+'代码/'+code;actual=hashlib.sha256(read(path)).hexdigest()
            items[code]=dict(expected=expected,actual=actual,match=expected==actual)
        items['simulation_result']=dict(expected=cfg['simulation_result_sha256'],actual=source_hash[SIM+'模拟结果.json'],match=cfg['simulation_result_sha256']==source_hash[SIM+'模拟结果.json'])
        for file,expected in cfg['evidence']['sha256'].items():
            actual=hashlib.sha256(read(cfg['evidence']['path']+'/'+file)).hexdigest()
            items[file]=dict(expected=expected,actual=actual,match=expected==actual)
        config_integrity[name]=items
    report=dict(task='A-Q1-CR-Q2-003',q2_fixed_commit=REF,source_sha256=source_hash,
                checks=checks,passed=sum(c['passed'] for c in checks),total=len(checks),
                config_integrity=config_integrity,simulation_keys=list(sim),lag_probes=lag_results,
                raw_workbooks_read=False,real_validation_executed=False,old_66_checks_rerun=False,
                published_simulation_excerpt=sim)
    # Published evidence retained as an excerpt, explicitly distinct from our new probe results.
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k in ('checks','passed','total','config_integrity','simulation_keys')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
