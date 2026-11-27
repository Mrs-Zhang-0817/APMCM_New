"""Independent synthetic functional checks; no original workbook is read."""
from pathlib import Path
import json,time,hashlib,csv
import numpy as np
from validation_modules import *
P=Path(__file__).resolve().parents[1];O=P/'实验验证/V04_实验程序准备';O.mkdir(parents=True,exist_ok=True)
checks=[];metrics=[];timings=[];injection_records=[];mask_records=[]
def check(name,condition):
    assert condition,name;checks.append(dict(Check=name,Passed=True))
t,w,reference=synthetic_spectrum();original=reference.copy();seed=20261127
for kind in ['high','low','time','wavelength','block']:
    observed,truth,records=inject_anomalies(reference,kind,seed);injection_records.extend(records)
    check('injection_'+kind,np.array_equal(observed!=reference,truth) and len(records)==truth.sum())
    check('seed_'+kind,np.array_equal(observed,inject_anomalies(reference,kind,seed)[0]))
    input_hash=hashlib.sha256(observed.tobytes()).hexdigest()
    for model in ['D0','D1','D2']:
        start=time.perf_counter();pred,_=detect(observed,model);timings.append(dict(Operation=model,Shape=str(reference.shape),Seconds=time.perf_counter()-start));check('dimension_'+kind+'_'+model,pred.shape==reference.shape)
        metrics.append(dict(Synthetic_Only=True,Task='detection',Scenario=kind,Model=model,Input_SHA256=input_hash,Metrics=detection_metrics(pred,truth)))
    check('immutable_'+kind,np.array_equal(reference,original))
truth=np.array([[1,1,0,0]],bool);pred=np.array([[1,0,1,0]],bool);m=detection_metrics(pred,truth)
check('known_confusion',all(m[k]==v for k,v in dict(TP=1,FP=1,FN=1,TN=1,Precision=.5,Recall=.5,F1=.5,FPR=.5).items()))
check('undefined_precision',detection_metrics(np.zeros_like(truth),truth)['Precision'] is None)
check('protected_peak_denominator',detection_metrics(pred,truth,protected_peaks=np.array([[0,0,1,1]],bool))['Protected_Peak_Flag_Rate']==.5)
for kind in ['points','time','wavelength','block','peak']:
    kwargs={'peak_index':int(np.argmin(abs(w-504)))} if kind=='peak' else {}
    observed,mask=mask_observations(reference,kind,seed,**kwargs);check('hidden_'+kind,np.isnan(observed[mask]).all() and np.array_equal(observed[~mask],reference[~mask]))
    mask_records.append(dict(Kind=kind,Seed=seed,Positions=np.argwhere(mask).tolist(),Reference_Only_For_Evaluation=reference[mask].tolist(),Model_Input_Hidden=True))
    start=time.perf_counter();estimate=reconstruct_r0(observed,t,w);timings.append(dict(Operation='R0_'+kind,Shape=str(reference.shape),Seconds=time.perf_counter()-start));check('preserved_'+kind,np.array_equal(estimate[~mask],reference[~mask]));metrics.append(dict(Synthetic_Only=True,Task='reconstruction',Scenario=kind,Model='R0',Metrics=reconstruction_metrics(estimate,reference,mask,t,w)))
# An analytic plane must be exactly recovered at non-grid coordinates by a bilinear function.
plane=2*t[:,None]+3*w[None,:]+1;surface=GridSurface(t,w,plane);tq=(t[:-1]+t[1:])/2;wq=(w[:-1]+w[1:])/2
check('off_grid_plane_exact',np.allclose(surface.evaluate(tq,wq),2*tq[:,None]+3*wq[None,:]+1))
check('nodes_exact',np.allclose(surface.evaluate(t,w),plane))
try:surface.evaluate([t[0]-1],[w[0]]);check('no_extrapolation',False)
except ValueError:check('no_extrapolation',True)
testmask=np.ones((2,2),bool);m=reconstruction_metrics(np.array([[0.,2.],[4.,6.]]),np.ones((2,2)),testmask,np.array([0.,1.]),np.array([0.,1.]))
check('known_reconstruction_metric',np.isclose(m['MAE'],2.5) and np.isclose(m['RMSE'],3))
all_missing=reconstruct_r0(np.full(reference.shape,np.nan),t,w)
check('unsupported_gap_reported',reconstruction_metrics(all_missing,reference,np.ones(reference.shape,bool),t,w)['Evaluated_Points']==0)
clip_counts=[]
for q in [.6,.8,.95]:
    upper=float(np.quantile(reference,q));observed,mask=clip_observations(reference,upper);check('clipping_'+str(q),np.array_equal(mask,reference>upper) and np.all(observed<=upper));clip_counts.append(int(mask.sum()))
    start=time.perf_counter();estimate=censored_c2(observed,t,w,upper);timings.append(dict(Operation='C2_200_iterations',Shape=str(reference.shape),Seconds=time.perf_counter()-start));check('lower_bound_'+str(q),np.all(estimate[mask]>=upper));metrics.append(dict(Synthetic_Only=True,Task='clipping',Scenario=str(q),Model='C2',Metrics=reconstruction_metrics(estimate,reference,mask,t,w),Shoulder_MAE=float(np.mean(abs(estimate[~mask]-reference[~mask]))),Lower_Bound_Violations=int(np.sum(estimate[mask]<upper))))
check('clipping_severity',clip_counts[0]>=clip_counts[1]>=clip_counts[2])
for q in [.6,.8,.95]:
    upper=float(np.quantile(reference,q));observed,mask=clip_observations(reference,upper);observed[observed>=upper]=np.nan;estimate=reconstruct_r0(observed,t,w)
    metrics.append(dict(Synthetic_Only=True,Task='clipping',Scenario=str(q),Model='C1_interpolation_control',Metrics=reconstruction_metrics(estimate,reference,mask,t,w),Lower_Bound_Violations=int(np.sum((estimate<upper)&mask&np.isfinite(estimate)))))
for shape_kind in ['narrow','wide']:
    peak=20/(1+((w-504)/.3)**2) if shape_kind=='narrow' else 20*np.maximum(0,1-abs(w-516)/6)
    ref=10+np.ones((len(t),1))*peak;clipped,mask=clip_observations(ref,20)
    check('clip_shape_'+shape_kind,mask.any() and np.all(clipped[mask]==20))
single=reference.copy();upper=(np.sort(single.ravel())[-1]+np.sort(single.ravel())[-2])/2;_,mask=clip_observations(single,upper);check('single_point_clipping',mask.sum()==1)
for shape in [(48,96),(96,192)]:
    tt,ww,xx=synthetic_spectrum(*shape);observed,mask=mask_observations(xx,'block',seed)
    for name,fn in [('D2',lambda:detect(xx,'D2')),('R0',lambda:reconstruct_r0(observed,tt,ww)),('C2',lambda:censored_c2(np.minimum(xx,25),tt,ww,25))]:
        st=time.perf_counter();fn();timings.append(dict(Operation=name+'_benchmark',Shape=str(shape),Seconds=time.perf_counter()-st))
heats=['sim'+str(i) for i in range(10)];folds=loho_plan(heats,{h:'A' if i<4 else 'B' for i,h in enumerate(heats)})
check('loho_isolation',all(not(set(f['train'])&set(f['test']+f['validation'])) and not(set(f['test'])&set(f['validation'])) for f in folds))
check('reference_never_changed',np.array_equal(reference,original))
try:validate_experiment_config({'status':'Pending','frozen':False},[],real_data=True);check('pending_real_data_blocked',False)
except PermissionError:check('pending_real_data_blocked',True)
(O/'V04_模拟功能测试结果.json').write_text(json.dumps(dict(seed=seed,shape=list(reference.shape),scope='独立人工二维谱；功能验证，非真实数据性能',checks=checks,synthetic_metrics=metrics,timings=timings,folds=folds,injection_records=injection_records,mask_records=mask_records,real_workbooks_read=False),ensure_ascii=False,indent=2),encoding='utf-8')
with (O/'V04_模拟计算成本.csv').open('w',encoding='utf-8-sig',newline='') as f:
    out=csv.DictWriter(f,fieldnames=list(timings[0]),lineterminator='\n');out.writeheader();out.writerows(timings)
print(json.dumps(dict(functional_checks=len(checks),passed=all(c['Passed'] for c in checks),real_data_validation=False,timings=timings[-6:]),ensure_ascii=False,indent=2))
if not all(c['Passed'] for c in checks):raise SystemExit(1)
