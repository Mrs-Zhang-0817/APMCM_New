"""Candidate validation modules. Array-only API; no original-data loading."""
import numpy as np

def synthetic_spectrum(n=48,p=96):
    t=np.linspace(0,20,n);w=490+40*np.linspace(0,1,p)**1.03
    background=10+.1*(w-490)[None,:]+.2*t[:,None]
    narrow=(20+4*np.sin(t/3))[:,None]/(1+((w-504)[None,:]/.35)**2)
    broad=(12+3*np.cos(t/5))[:,None]*np.maximum(0,1-abs(w-516)[None,:]/6)
    return t,w,background+narrow+broad

def select_mask(shape,kind,seed,fraction=.01,size=(3,5),peak_index=None):
    rng=np.random.default_rng(seed);n,p=shape;mask=np.zeros(shape,bool)
    if kind=='points':
        count=max(1,int(round(n*p*fraction)));mask.flat[rng.choice(n*p,count,replace=False)]=True
    else:
        rows,cols=size
        if kind=='time':cols=1
        if kind=='wavelength':rows=1
        if kind=='peak':
            if peak_index is None:raise ValueError('peak_index must be predeclared, not extracted from hidden truth')
            rows=1;cols=min(cols,p);j=max(0,min(p-cols,peak_index-cols//2));i=int(rng.integers(0,n))
        else:i=int(rng.integers(0,n-rows+1));j=int(rng.integers(0,p-cols+1))
        mask[i:i+rows,j:j+cols]=True
    return mask

def inject_anomalies(reference,kind,seed=20261127,amplitude=20,fraction=.01,size=(3,5)):
    if amplitude<=0:raise ValueError('positive magnitude required')
    shape_kind='points' if kind in ['high','low'] else kind
    mask=select_mask(reference.shape,shape_kind,seed,fraction,size)
    observed=np.array(reference,copy=True);delta=-amplitude if kind=='low' else amplitude;observed[mask]+=delta
    records=[dict(Row=int(i),Column=int(j),Reference=float(reference[i,j]),Observed=float(observed[i,j]),Delta=float(delta),Seed=seed,Kind=kind,Requested_Fraction=fraction,Actual_Fraction=float(mask.mean()),Injected_Count=int(mask.sum()),Denominator=reference.size) for i,j in np.argwhere(mask)]
    return observed,mask,records

def mask_observations(reference,kind,seed=20261127,**kwargs):
    mask=select_mask(reference.shape,kind,seed,**kwargs);observed=np.array(reference,copy=True);observed[mask]=np.nan
    return observed,mask

def clip_observations(reference,upper):
    observed=np.minimum(reference,upper);return observed,reference>upper

def detection_metrics(predicted,truth,eligible=None,protected_peaks=None):
    eligible=np.ones_like(truth,bool) if eligible is None else eligible
    tp=int(np.sum(predicted&truth&eligible));fp=int(np.sum(predicted&~truth&eligible));fn=int(np.sum(~predicted&truth&eligible));tn=int(np.sum(~predicted&~truth&eligible))
    ratio=lambda a,b:a/b if b else None
    return dict(TP=tp,FP=fp,FN=fn,TN=tn,Precision=ratio(tp,tp+fp),Recall=ratio(tp,tp+fn),F1=ratio(2*tp,2*tp+fp+fn),FPR=ratio(fp,fp+tn),Protected_Peak_Flag_Rate=ratio(np.sum(predicted&protected_peaks&eligible),np.sum(protected_peaks&eligible)) if protected_peaks is not None else None)

def detect(observed,kind='D0',threshold=6,floor=1,time_radius=2,wave_radius=2):
    x=np.asarray(observed);n,p=x.shape
    if kind=='D0':
        median=np.nanmedian(x);mad=np.nanmedian(abs(x-median));score=(x-median)/(1.4826*mad+floor);return abs(score)>threshold,dict(global_score=score)
    st=np.full(x.shape,np.nan);sw=st.copy()
    for i in range(n):
        indexes=[q for q in range(max(0,i-time_radius),min(n,i+time_radius+1)) if q!=i]
        if len(indexes)>=2:
            med=np.nanmedian(x[indexes],axis=0);mad=np.nanmedian(abs(x[indexes]-med),axis=0);st[i]=(x[i]-med)/(1.4826*mad+floor)
    for j in range(p):
        indexes=[q for q in range(max(0,j-wave_radius),min(p,j+wave_radius+1)) if q!=j]
        if len(indexes)>=2:
            med=np.nanmedian(x[:,indexes],axis=1);mad=np.nanmedian(abs(x[:,indexes]-med[:,None]),axis=1);sw[:,j]=(x[:,j]-med)/(1.4826*mad+floor)
    if kind=='D1':prediction=(abs(st)>threshold)|(abs(sw)>threshold)
    elif kind=='D2':prediction=(abs(st)>threshold)&(abs(sw)>threshold)&(np.sign(st)==np.sign(sw))
    else:raise ValueError(kind)
    return prediction,dict(time_score=st,wave_score=sw)

class GridSurface:
    """Piecewise bilinear surface on actual nonuniform coordinates; no extrapolation."""
    def __init__(self,t,w,values):
        self.t=np.asarray(t);self.w=np.asarray(w);self.values=np.array(values,copy=True)
        if self.values.shape!=(len(t),len(w)) or not np.isfinite(values).all():raise ValueError('finite complete grid required')
        if not (np.all(np.diff(t)>0) and np.all(np.diff(w)>0)):raise ValueError('strictly increasing actual coordinates required')
    def evaluate(self,tq,wq):
        tq=np.atleast_1d(tq);wq=np.atleast_1d(wq)
        if tq.min()<self.t[0] or tq.max()>self.t[-1] or wq.min()<self.w[0] or wq.max()>self.w[-1]:raise ValueError('outside domain')
        temporal=np.column_stack([np.interp(tq,self.t,self.values[:,j]) for j in range(len(self.w))])
        return np.vstack([np.interp(wq,self.w,row) for row in temporal])

def reconstruct_r0(observed,t,w):
    x=np.array(observed,copy=True);missing=~np.isfinite(x)
    # Interior interpolation only. Unresolved edge gaps remain explicitly unsupported.
    for j in range(len(w)):
        ok=np.isfinite(x[:,j]);ix=np.where(ok)[0]
        if len(ix)>=2:
            todo=missing[:,j]&(t>=t[ix[0]])&(t<=t[ix[-1]]);x[todo,j]=np.interp(t[todo],t[ok],x[ok,j])
    for i in range(len(t)):
        ok=np.isfinite(x[i]);ix=np.where(ok)[0]
        if len(ix)>=2:
            todo=~ok&(w>=w[ix[0]])&(w<=w[ix[-1]]);x[i,todo]=np.interp(w[todo],w[ok],x[i,ok])
    return x

def censored_c2(observed,t,w,upper,alpha=.1,beta=.1,iterations=200):
    """Projected-gradient nonuniform wavelength-curvature candidate; no peak-shape truth assumption."""
    sat=observed>=upper;x=np.array(observed,copy=True);weight=(~sat).astype(float);dt=np.diff(t);dw=np.diff(w)
    c0=2/(dw[:-1]*(dw[:-1]+dw[1:]));c1=-2/(dw[:-1]*dw[1:]);c2=2/(dw[1:]*(dw[:-1]+dw[1:]))
    rownorm=np.max(abs(c0)+abs(c1)+abs(c2));colsum=np.zeros(len(w));colsum[:-2]+=abs(c0);colsum[1:-1]+=abs(c1);colsum[2:]+=abs(c2)
    step=.9/(1+alpha*rownorm*colsum.max()+4*beta/dt.min()**2)
    for _ in range(iterations):
        g=weight*(x-observed);curv=c0*x[:,:-2]+c1*x[:,1:-1]+c2*x[:,2:];g[:,:-2]+=alpha*c0*curv;g[:,1:-1]+=alpha*c1*curv;g[:,2:]+=alpha*c2*curv;b=beta*np.diff(x,axis=0)/dt[:,None]**2;g[:-1]-=b;g[1:]+=b
        x-=step*g;x[sat]=np.maximum(x[sat],upper)
    return x

def reconstruction_metrics(estimate,reference,mask,t,w):
    eligible=mask&np.isfinite(estimate);d=estimate[eligible]-reference[eligible]
    out=dict(Requested_Points=int(mask.sum()),Evaluated_Points=int(eligible.sum()),Coverage=float(eligible.sum()/mask.sum()) if mask.any() else None,MAE=float(np.mean(abs(d))) if len(d) else None,RMSE=float(np.sqrt(np.mean(d*d))) if len(d) else None)
    rows=np.where(eligible.any(axis=1))[0];height=[];position=[];area=[]
    for i in rows:
        if not np.isfinite(estimate[i]).all():continue
        height.append(abs(estimate[i].max()-reference[i].max()));position.append(abs(w[np.argmax(estimate[i])]-w[np.argmax(reference[i])]))
        area.append(abs(np.trapezoid(estimate[i],w)-np.trapezoid(reference[i],w)))
    touched=mask[:,1:]|mask[:,:-1];finite=np.isfinite(estimate[:,1:])&np.isfinite(estimate[:,:-1]);edge=touched&finite;dg=(np.diff(estimate,axis=1)-np.diff(reference,axis=1))/np.diff(w)[None,:]
    out.update(Peak_Height_MAE=float(np.mean(height)) if height else None,Peak_Position_MAE_nm=float(np.mean(position)) if position else None,Peak_Area_MAE=float(np.mean(area)) if area else None,Shape_Gradient_RMSE_lambda=float(np.sqrt(np.mean(dg[edge]**2))) if edge.any() else None)
    return out

def loho_plan(heats,grids):
    if len(set(heats))!=len(heats) or len(heats)<3:raise ValueError('unique >=3 objects required')
    folds=[]
    for test in heats:
        other=[x for x in heats if x!=test];validation=other[-1];train=other[:-1]
        folds.append(dict(test=[test],validation=[validation],train=train,train_grid_groups=sorted(set(grids[h] for h in train)),parameter_fit_allowed=train,parameter_select_allowed=[validation],test_labels_for_selection=False))
    return folds

def validate_experiment_config(config,approved_references,real_data=False):
    if not real_data:return
    if config.get('status')!='Jointly Approved' or config.get('frozen') is not True:raise PermissionError('Real-data validation requires joint approval and frozen settings')
    if not approved_references or any(r.get('Status')!='Jointly Approved' for r in approved_references):raise PermissionError('Reference proposals are not approved truth proxies')
