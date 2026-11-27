"""A-Q1-CR-002: synthetic-only candidates. No workbook reader or real-data runner."""
import hashlib
import json
import numpy as np
from validation_modules import reconstruct_r0, censored_c2

def detect_v2(observed, kind='D2', threshold=6., floor=1., time_radius=2,
              wave_radius=2, min_neighbors=2, min_fraction=.5, upper=65535.):
    """Unknown predictions are NaN. Fraction denominator is full nominal 2*r.
    D1/D2 both require two assessable axes; partial evidence is fallback only.
    A finite upper-valued neighbor invalidates its axis, even after exclusion.
    """
    x=np.asarray(observed,dtype=float)
    if x.ndim!=2 or min(x.shape)<1 or kind not in ('D1','D2'): raise ValueError('shape/kind')
    if not np.isfinite([threshold,floor,min_fraction,upper]).all() or threshold<=0 or floor<=0 or not 0<min_fraction<=1: raise ValueError('parameters')
    if any(not isinstance(v,int) or isinstance(v,bool) or v<1 for v in (time_radius,wave_radius,min_neighbors)): raise ValueError('integer support')
    valid_center=np.isfinite(x)&(x<upper)
    details={}
    for axis,radius,name in [(0,time_radius,'time'),(1,wave_radius,'wave')]:
        score=np.full(x.shape,np.nan);count=np.zeros(x.shape,int)
        geometric=count.copy();polluted=np.zeros(x.shape,bool);zero=polluted.copy()
        for ij in np.ndindex(x.shape):
            idx=ij[axis];ii=[q for q in range(max(0,idx-radius),min(x.shape[axis],idx+radius+1)) if q!=idx]
            vals=np.array([x[q,ij[1]] if axis==0 else x[ij[0],q] for q in ii])
            geometric[ij]=len(vals);polluted[ij]=np.any(np.isfinite(vals)&(vals>=upper))
            good=vals[np.isfinite(vals)&(vals<upper)];count[ij]=len(good)
            if valid_center[ij] and len(good)>=min_neighbors and len(good)/(2*radius)>=min_fraction and not polluted[ij]:
                med=np.median(good);mad=np.median(abs(good-med));zero[ij]=mad==0
                score[ij]=(x[ij]-med)/(1.4826*mad+floor)
        details[name+'_score']=score;details[name+'_count']=count
        details[name+'_fraction']=count/(2*radius);details[name+'_geometric_count']=geometric
        details[name+'_polluted']=polluted;details[name+'_mad_zero']=zero
    st=details['time_score'];sw=details['wave_score']
    et=np.isfinite(st);ew=np.isfinite(sw);eligible=et&ew
    a=abs(st)>threshold;b=abs(sw)>threshold
    flag=(a|b) if kind=='D1' else (a&b&(np.sign(st)==np.sign(sw)))
    prediction=np.full(x.shape,np.nan);prediction[eligible]=flag[eligible].astype(float)
    state=np.full(x.shape,'Unassessable',dtype='<U24')
    state[valid_center&(et^ew)]='Fallback Required'
    state[eligible&~flag]='Evaluable Not Triggered';state[eligible&flag]='Evaluable Triggered'
    details.update(eligible=eligible,state=state,partial_direction_trigger=(a|b)&~eligible,
                   valid_center=valid_center)
    return prediction,details

def select_mask_v2(shape,kind,seed,fraction=.01,size=(3,5),peak_index=None):
    if len(shape)!=2 or any(not isinstance(v,int) or isinstance(v,bool) or v<=0 for v in shape): raise ValueError('shape')
    if kind not in ('points','time','wavelength','block','peak'): raise ValueError('kind')
    if not np.isfinite(fraction) or not 0<=fraction<=1: raise ValueError('fraction')
    n,p=shape;rng=np.random.default_rng(seed);mask=np.zeros(shape,bool)
    if kind=='points':
        count=int(round(n*p*fraction))
        mask.flat[rng.choice(n*p,count,replace=False)]=True
    else:
        if len(size)!=2 or any(not isinstance(v,int) or isinstance(v,bool) or v<=0 for v in size): raise ValueError('size')
        rows,cols=size
        if kind=='time': cols=1
        if kind in ('wavelength','peak'): rows=1
        if rows>n or cols>p: raise ValueError('size exceeds domain')
        if kind=='peak' and (not isinstance(peak_index,int) or not 0<=peak_index<p): raise ValueError('predeclared peak index')
        i=int(rng.integers(0,n-rows+1));j=int(rng.integers(0,p-cols+1))
        if kind=='peak': j=max(0,min(p-cols,peak_index-cols//2))
        mask[i:i+rows,j:j+cols]=True
    return mask,dict(kind=kind,seed=seed,fraction=fraction,size=list(size),
                     requested_points=int(round(n*p*fraction)) if kind=='points' else rows*cols,
                     actual_points=int(mask.sum()),denominator=n*p)

def authorize_real_v2(config,references,manifest_bytes):
    """Configuration check only, never executes. Approval identities require human review."""
    if config.get('real_data_execution_allowed') is not True or config.get('status')!='Jointly Approved' or config.get('frozen') is not True: raise PermissionError('execution disabled')
    if not isinstance(manifest_bytes,bytes): raise PermissionError('manifest bytes required')
    digest=hashlib.sha256(manifest_bytes).hexdigest()
    payload=json.loads(manifest_bytes)
    required=('approval_id','config_version','config_sha256','approvers','reference_manifest_sha256')
    if any(not config.get(k) for k in required): raise PermissionError('approval fields missing')
    if len(set(config['approvers']))!=2 or any(not isinstance(v,str) or not v.strip() for v in config['approvers']): raise PermissionError('two people required')
    core={k:v for k,v in config.items() if k!='config_sha256'}
    if hashlib.sha256(json.dumps(core,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()!=config['config_sha256']: raise PermissionError('config hash')
    if digest!=config['reference_manifest_sha256'] or not references or references!=payload: raise PermissionError('reference manifest mismatch')
    ids=[r.get('Reference_ID') for r in references]
    if len(set(ids))!=len(ids) or not all(ids): raise PermissionError('reference IDs')
    for r in references:
        if r.get('Status')!='Jointly Approved' or r.get('Approval_ID')!=config['approval_id'] or set(r.get('Approvers',[]))!=set(config['approvers']) or len(r.get('Source_SHA256',''))!=64 or not r.get('Approved_Use'): raise PermissionError('reference approval incomplete')

def r0_with_support_v2(observed,t,w,order='time-wave'):
    x=np.array(observed,float,copy=True);t=np.asarray(t);w=np.asarray(w)
    if x.shape!=(len(t),len(w)) or not np.isfinite(t).all() or not np.isfinite(w).all() or not (np.diff(t)>0).all() or not (np.diff(w)>0).all() or np.isinf(x).any(): raise ValueError('coordinates/values')
    if order not in ('time-wave','wave-time'): raise ValueError('order')
    original=np.isfinite(x);provenance=np.where(original,0,-1);used_estimated=np.zeros(x.shape,bool)
    for step,axis in enumerate(([0,1] if order=='time-wave' else [1,0]),1):
        for k in range(x.shape[1-axis]):
            line=x[:,k] if axis==0 else x[k,:];coord=t if axis==0 else w
            tags=provenance[:,k] if axis==0 else provenance[k,:]
            support=np.flatnonzero(np.isfinite(line))
            if len(support)<2: continue
            for q in np.flatnonzero(~np.isfinite(line)):
                left=support[support<q];right=support[support>q]
                if not len(left) or not len(right): continue
                l=left[-1];r=right[0];line[q]=line[l]+(line[r]-line[l])*(coord[q]-coord[l])/(coord[r]-coord[l]);tags[q]=step
                ij=(q,k) if axis==0 else (k,q);used_estimated[ij]=(tags[l]>0 or tags[r]>0)
    return x,dict(provenance=provenance,used_estimated_support=used_estimated,order=order,unresolved=~np.isfinite(x))

def clip_v2(reference,upper):
    x=np.asarray(reference,float)
    if not np.isfinite(x).all() or not np.isfinite(upper): raise ValueError('finite clipping inputs')
    return np.minimum(x,upper),dict(strict_clipped=x>upper,equality=x==upper,below=x<upper,observed_at_cap=x>=upper)

def c2_checked_v2(observed,t,w,upper,alpha=.1,beta=.1,iterations=200):
    y=np.asarray(observed,float);t=np.asarray(t,float);w=np.asarray(w,float)
    if y.shape!=(len(t),len(w)) or len(t)<2 or len(w)<3 or not np.isfinite(y).all() or not np.isfinite(t).all() or not np.isfinite(w).all() or not (np.diff(t)>0).all() or not (np.diff(w)>0).all(): raise ValueError('C2 domain')
    if not np.isfinite([upper,alpha,beta]).all() or alpha<0 or beta<0 or not isinstance(iterations,int) or isinstance(iterations,bool) or iterations<1 or np.any(y>upper): raise ValueError('C2 parameters')
    fit=censored_c2(y,t,w,upper,alpha,beta,iterations)
    return fit,dict(observed_at_cap=int((y>=upper).sum()),lower_bound_violations=int((fit[y>=upper]<upper).sum()),
                    convergence_certified=False,iterations=iterations,real_data_ready=False)

def _summary(values):
    v=np.asarray(values,float)
    return dict(count=len(v),mean=float(v.mean()) if len(v) else None,
                median=float(np.median(v)) if len(v) else None,
                p95=float(np.quantile(v,.95)) if len(v) else None,max=float(v.max()) if len(v) else None)

def _peak(y,w,background):
    if not np.isfinite(y).all(): return None
    z=y-background;j=int(np.argmax(z))
    if j==0 or j==len(y)-1 or z[j]<=0 or np.sum(z==z[j])!=1: return None
    half=z[j]/2;left=np.flatnonzero(z[:j]<=half);right=np.flatnonzero(z[j+1:]<=half)+j+1
    if not len(left) or not len(right): return None
    l=left[-1];r=right[0]
    wl=w[l]+(half-z[l])*(w[l+1]-w[l])/(z[l+1]-z[l])
    wr=w[r-1]+(half-z[r-1])*(w[r]-w[r-1])/(z[r]-z[r-1])
    return np.array([w[j],z[j],wr-wl,np.trapezoid(z,w)])

def reconstruction_metrics_v2(estimate,reference,mask,w,*,peak_window,shoulder_windows,background):
    """Explicit physical windows. No automatic selection from hidden truth.
    FWHM uses connected half-height crossings around unique discrete maximum.
    """
    e=np.asarray(estimate,float);r=np.asarray(reference,float);m=np.asarray(mask,bool);w=np.asarray(w,float)
    if e.shape!=r.shape or e.shape!=m.shape or e.ndim!=2 or e.shape[1]!=len(w) or not np.isfinite(r).all() or not (np.diff(w)>0).all() or not np.isfinite(w).all() or not np.isfinite(background): raise ValueError('metric shape/coordinates')
    if len(peak_window)!=2 or peak_window[0]>=peak_window[1] or peak_window[0]<w[0] or peak_window[1]>w[-1]: raise ValueError('peak window')
    peak=(w>=peak_window[0])&(w<=peak_window[1]);shoulder=np.zeros(len(w),bool)
    if peak.sum()<3: raise ValueError('peak support')
    for lo,hi in shoulder_windows:
        if lo>=hi or lo<w[0] or hi>w[-1] or not (hi<peak_window[0] or lo>peak_window[1]): raise ValueError('shoulder window')
        shoulder|=(w>=lo)&(w<=hi)
    rows=np.flatnonzero(m.any(axis=1));eligible=m&np.isfinite(e);d=e[eligible]-r[eligible]
    out=dict(requested_points=int(m.sum()),evaluated_points=int(eligible.sum()),coverage=float(eligible.sum()/m.sum()) if m.any() else None,MAE=float(np.mean(abs(d))) if len(d) else None,RMSE=float(np.sqrt(np.mean(d*d))) if len(d) else None,absolute_error=_summary(abs(d)),peak_window=list(peak_window),background=background,peak_requested_rows=len(rows),peak_rows=[])
    errs=[]
    for i in rows:
        a=_peak(e[i,peak],w[peak],background);b=_peak(r[i,peak],w[peak],background)
        ok=a is not None and b is not None
        out['peak_rows'].append(dict(row=int(i),assessable=ok,absolute_errors=(abs(a-b).tolist() if ok else None)))
        if ok: errs.append(abs(a-b))
    out['peak_evaluated_rows']=len(errs);out['peak_coverage']=len(errs)/len(rows) if len(rows) else None
    for k,name in enumerate(('position_nm','height','FWHM_nm','area')): out[name]=_summary([a[k] for a in errs])
    requested=np.zeros(e.shape,bool);requested[rows]=shoulder
    ok=requested&np.isfinite(e);out['shoulder_requested_points']=int(requested.sum());out['shoulder_evaluated_points']=int(ok.sum());out['shoulder_absolute_error']=_summary(abs(e[ok]-r[ok]))
    edge=(m[:,1:]|m[:,:-1]);valid=edge&np.isfinite(e[:,1:])&np.isfinite(e[:,:-1]);dg=(np.diff(e,axis=1)-np.diff(r,axis=1))/np.diff(w)
    out['gradient_requested_edges']=int(edge.sum());out['gradient_evaluated_edges']=int(valid.sum());out['gradient_RMSE']=float(np.sqrt(np.mean(dg[valid]**2))) if valid.any() else None
    return out
