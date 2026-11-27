"""Independent synthetic stress tests only; no real-data loading."""
from pathlib import Path
import json
import numpy as np
from validation_modules import detect,synthetic_spectrum,reconstruct_r0,censored_c2,GridSurface
P=Path(__file__).resolve().parents[1];O=P/'实验验证/正式清洗前置审核';O.mkdir(exist_ok=True);results=[]
def record(name,fact,values):results.append(dict(Test=name,Check_Passed=bool(fact),Values=values,Scope='独立模拟，非真实数据性能'));assert fact,name
x=np.full((15,25),100.);x[7,12]=101
for mode in ['D0','D1','D2']:
    a,_=detect(x,mode,floor=1);b,_=detect(100*x,mode,floor=1);c,_=detect(100*x,mode,floor=100)
    record('MAD0_scale_'+mode,not a[7,12] and b[7,12] and np.array_equal(a,c),dict(original_flags=int(a.sum()),fixed_floor_rescaled_flags=int(b.sum()),co_scaled_floor_flags=int(c.sum())))
def score(v,c):
    m=np.median(v);mad=np.median(abs(np.array(v)-m));return (c-m)/(1.4826*mad+1)
clean=score([100,100,102,104],140);contaminated=score([100,102,65535,65535],140)
record('upper_neighbors_can_hide_positive_residual',abs(clean)>6 and abs(contaminated)<6,dict(clean=clean,contaminated=contaminated))
peak=np.full((15,25),100.);peak[:,12]=1000
p1,_=detect(peak,'D1');p2,_=detect(peak,'D2');record('persistent_narrow_peak_OR_AND',p1[:,12].all() and not p2[:,12].any(),dict(D1_flags=int(p1[:,12].sum()),D2_flags=int(p2[:,12].sum()),peak_points=15))
peak=np.full((15,25),100.);peak[7,12]=1000;p,_=detect(peak,'D2');record('transient_real_peak_still_triggers_consensus',p[7,12],dict(triggered=True,meaning='真实瞬时峰与异常尖点可能观测相同，不能仅算法辨别'))
block=np.full((41,61),100.);block[10:31,15:46]=300
for mode in ['D1','D2']:
    p,_=detect(block,mode);record('block_interior_miss_'+mode,not p[20,30],dict(interior_flag=bool(p[20,30]),flagged_block_points=int(p[10:31,15:46].sum()),block_points=21*31))
t,w,x=synthetic_spectrum();hidden=x.copy();hidden[10:15,30:40]=np.nan;estimate=reconstruct_r0(hidden,t,w)
record('R0_convex_bounds',np.nanmin(estimate)>=np.nanmin(hidden) and np.nanmax(estimate)<=np.nanmax(hidden),dict(min=float(np.nanmin(estimate)),max=float(np.nanmax(estimate))))
edge=x.copy();edge[:3,:]=np.nan;restored=reconstruct_r0(edge,t,w);record('R0_unsupported_boundary_not_fabricated',np.isnan(restored[:3]).all(),dict(unsupported_points=int(np.isnan(restored).sum())))
C=30.;y=np.minimum(x,C);sat=y>=C;fit=censored_c2(y,t,w,C);record('C2_lower_bound_not_identifiability',np.all(fit[sat]>=C),dict(violation_count=int(np.sum(fit[sat]<C)),true_peak=float(x.max()),estimated_peak=float(fit.max()),iterations=200))
# Distinct latent peaks yield identical clipped observations: constructive non-identifiability.
x1=np.array([1.,3.,5.,3.,1.]);x2=np.array([1.,3.,9.,3.,1.]);record('same_observation_different_peak',np.array_equal(np.minimum(x1,3),np.minimum(x2,3)),dict(first_peak=5,second_peak=9,upper=3))
path=O/'独立模拟风险测试.json';path.write_text(json.dumps(dict(checks=results,all_pass=True,real_data_used=False),ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False,indent=2))
