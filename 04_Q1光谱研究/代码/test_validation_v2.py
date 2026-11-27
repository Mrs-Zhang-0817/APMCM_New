"""Synthetic regression entry; prints JSON, never writes historical results."""
import json,hashlib,warnings
import numpy as np
from validation_modules_v2 import *
checks=[];cases=[]
def check(name,ok,values=None):
    checks.append(dict(test=name,passed=bool(ok),values=values));assert ok,name
def raises(name,fn,exc=ValueError):
    try: fn()
    except exc: check(name,True);return
    check(name,False)
def evaluate(name,x,center=(3,3),**kw):
    result={}
    for mode in ('D1','D2'):
        p,d=detect_v2(x,mode,**kw);i=center
        result[mode]=dict(prediction=None if np.isnan(p[i]) else float(p[i]),state=str(d['state'][i]),time_count=int(d['time_count'][i]),wave_count=int(d['wave_count'][i]),time_fraction=float(d['time_fraction'][i]),wave_fraction=float(d['wave_fraction'][i]),flags=int(np.nansum(p)),evaluated=int(np.isfinite(p).sum()),total=p.size)
    cases.append(dict(scenario=name,results=result));return result
warnings.filterwarnings('ignore',category=RuntimeWarning)
for nt,nw,name in [(1,1,'one_each'),(2,2,'two_each'),(1,4,'time_insufficient'),(4,1,'wave_insufficient'),(0,0,'both_insufficient')]:
    x=np.full((7,7),np.nan);x[3,3]=12
    for q in [2,4,1,5][:nt]:x[q,3]=0
    for q in [2,4,1,5][:nw]:x[3,q]=0
    out=evaluate(name,x)
    for mode in out:
        check(name+'_'+mode,(out[mode]['prediction']==1) if nt==nw==2 else out[mode]['prediction'] is None,out[mode])
x=np.zeros((9,9));x[4,4]=12;x[2,4]=65535
out=evaluate('saturation_neighbor',x,(4,4));check('pollution_is_unknown_not_normal',all(v['prediction'] is None for v in out.values()))
x=np.zeros((15,25));x[:,12]=1000
out=evaluate('persistent_narrow_peak',x,(7,12));check('persistent_peak_risk_visible',out['D1']['prediction']==1 and out['D2']['prediction']==0,out)
x=np.zeros((15,25));x[7,12]=1000
out=evaluate('transient_true_peak',x,(7,12));check('transient_peak_risk_visible',out['D2']['prediction']==1,out)
x=np.zeros((41,61));x[10:31,15:46]=300
out=evaluate('continuous_block_interior',x,(20,30));check('block_miss_still_visible',all(v['prediction']==0 for v in out.values()),out)
x=np.zeros((7,7));x[0,0]=12
out=evaluate('corner_two_inward',x,(0,0));check('boundary_not_blanket_excluded',all(v['prediction']==1 for v in out.values()),out)
_,d=detect_v2(x);check('nominal_fraction_corner',d['time_fraction'][0,0]==.5 and d['wave_fraction'][0,0]==.5)
out=evaluate('corner_strict_fraction',x,(0,0),min_fraction=.75);check('strict_boundary_unknown',all(v['prediction'] is None for v in out.values()))
x=np.zeros((7,7));x[3,3]=12
out=evaluate('MAD_zero',x);p,d=detect_v2(x);check('MAD0_finite',d['time_mad_zero'][3,3] and np.isfinite(d['time_score'][3,3]))
for mode in ('D1','D2'):
    a,_=detect_v2(x,mode);b,_=detect_v2(100*x,mode,floor=100)
    check('coscaled_floor_'+mode,np.array_equal(a,b,equal_nan=True))
for sign in (-1,1):
    y=np.full((9,9),100.);y[4,4]+=sign*20
    for mode in ('D1','D2'):check('signed_spike_'+mode+str(sign),detect_v2(y,mode)[0][4,4]==1)
x=np.zeros((7,7));x[3,3]=65535;check('cap_center_unknown',np.isnan(detect_v2(x)[0][3,3]))
raises('floor_zero_reject',lambda:detect_v2(x,floor=0))
raises('fraction_invalid_reject',lambda:detect_v2(x,min_fraction=1.1))
for name,kw in [('zero',dict(fraction=0)),('one',dict(fraction=1))]:
    mask,rec=select_mask_v2((5,5),'points',3,**kw);check('mask_'+name,int(mask.sum())==(0 if name=='zero' else 25),rec)
raises('unknown_mask_reject',lambda:select_mask_v2((5,5),'typo',3))
raises('negative_fraction_reject',lambda:select_mask_v2((5,5),'points',3,fraction=-.1))
raises('oversized_mask_reject',lambda:select_mask_v2((5,5),'block',3,size=(6,1)))
raises('undeclared_peak_reject',lambda:select_mask_v2((5,5),'peak',3))
for kind in ('time','wavelength','block','peak'):
    kw={'peak_index':2} if kind=='peak' else {};m,a=select_mask_v2((7,9),kind,3,**kw);n,b=select_mask_v2((7,9),kind,3,**kw)
    check('mask_seed_count_'+kind,np.array_equal(m,n) and a['actual_points']==a['requested_points'])
refs=[dict(Reference_ID='SIM',Status='Jointly Approved',Approval_ID='SYNTHETIC_ONLY',Approvers=['simulation_A','simulation_B'],Source_SHA256='0'*64,Approved_Use='Synthetic Fixture')]
payload=json.dumps(refs).encode();cfg=dict(real_data_execution_allowed=True,status='Jointly Approved',frozen=True,approval_id='SYNTHETIC_ONLY',config_version='synthetic',approvers=['simulation_A','simulation_B'],reference_manifest_sha256=hashlib.sha256(payload).hexdigest())
def seal(c):
    c={k:v for k,v in c.items() if k!='config_sha256'};c['config_sha256']=hashlib.sha256(json.dumps(c,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();return c
cfg=seal(cfg);authorize_real_v2(cfg,refs,payload);check('synthetic_gate_fixture_only',True)
for key in cfg:
    c=cfg.copy();c.pop(key);raises('gate_missing_'+key,lambda c=c:authorize_real_v2(c,refs,payload),PermissionError)
c=cfg.copy();c['real_data_execution_allowed']=False;c=seal(c);raises('disabled_even_signed',lambda:authorize_real_v2(c,refs,payload),PermissionError)
raises('manifest_tamper',lambda:authorize_real_v2(cfg,refs,payload+b' '),PermissionError)
raises('reference_tamper',lambda:authorize_real_v2(cfg,[dict(refs[0],Status='Pending')],payload),PermissionError)
raw=np.array([[0.,0,4],[2,np.nan,8],[12,12,8]])
a,da=r0_with_support_v2(raw,[0,1,2],[0,1,2]);b,db=r0_with_support_v2(raw,[0,1,2],[0,1,2],order='wave-time')
check('R0_order_6_vs_5',a[1,1]==6 and b[1,1]==5)
raw=np.array([[0.,0,0],[np.nan,np.nan,4],[4,np.nan,8.]])
a,da=r0_with_support_v2(raw,[0,1,2],[0,1,2]);check('R0_second_step_source_tag',da['used_estimated_support'][1,1])
raw=np.ones((5,5));raw[:2]=np.nan;a,da=r0_with_support_v2(raw,np.arange(5),np.arange(5));check('R0_unsupported_edge',np.isnan(a[:2]).all())
_,tags=clip_v2(np.array([1.,3,5]),3);check('clip_equality_separate',tags['strict_clipped'].tolist()==[False,False,True] and tags['equality'].tolist()==[False,True,False])
for name,args in [('nonfinite',(np.full((3,3),np.nan),[0,1,2],[0,1,2],3)),('repeated_coordinate',(np.ones((3,3)),[0,0,2],[0,1,2],3)),('negative_alpha',(np.ones((3,3)),[0,1,2],[0,1,2],3))]:
    raises('C2_'+name,lambda args=args,name=name:c2_checked_v2(*args,**({'alpha':-1} if name=='negative_alpha' else {})))
fit,info=c2_checked_v2(np.minimum(np.array([[1,3,9,3,1]]*3,float),3),[0,1,2],[0,.5,1,2,4],3)
check('C2_bounds_not_convergence',info['lower_bound_violations']==0 and not info['convergence_certified'])
check('clip_nonidentifiable',np.array_equal(np.minimum([1,3,5,3,1],3),np.minimum([1,3,9,3,1],3)))
w=np.array([0.,1,1.5,2,2.5,3,4,5]);r=np.array([[20,0,2,4,2,0,0,0.]])
e=r.copy();e[0,3]=3;m=np.zeros_like(r,bool);m[0,3]=True
met=reconstruction_metrics_v2(e,r,m,w,peak_window=(1,3),shoulder_windows=[(4,5)],background=0)
check('fixed_peak_ignores_unrelated_max',met['height']['mean']==1 and met['FWHM_nm']['count']==1,met)
exact=reconstruction_metrics_v2(r,r,m,w,peak_window=(1,3),shoulder_windows=[(4,5)],background=0)
check('identity_peak_metrics',all(exact[k]['mean']==0 for k in ('position_nm','height','FWHM_nm','area')))
e[0,2]=np.nan;met=reconstruction_metrics_v2(e,r,m,w,peak_window=(1,3),shoulder_windows=[(4,5)],background=0);check('incomplete_peak_coverage',met['peak_coverage']==0 and met['height']['mean'] is None)
raises('missing_peak_window_reject',lambda:reconstruction_metrics_v2(e,r,m,w,peak_window=(2,2.1),shoulder_windows=[],background=0))
print(json.dumps(dict(task='A-Q1-CR-002',synthetic_only=True,checks=checks,detector_scenarios=cases,all_pass=all(v['passed'] for v in checks)),ensure_ascii=False,indent=2))
