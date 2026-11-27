"""Re-read three low-point contexts for readable autoscaled raw-evidence plots."""
from pathlib import Path
import argparse,csv,json,hashlib
import numpy as np
from pyxlsb import open_workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1];R=P.parent
a=argparse.ArgumentParser();a.add_argument('--source-root',type=Path,required=True);args=a.parse_args()
with (P/'专项分析/S06_谱峰与异常反例研究/S06_低点补充案例.csv').open(encoding='utf-8-sig') as f:cases=[c for c in csv.DictReader(f) if c['Heat_ID'] in ['6B03205','6C02057','6C02058']]
manifest=json.loads((R/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'));records=[]
for c in cases:
    m=next(m for m in manifest if m['sheets'][0]==c['Heat_ID']);num=m['attachment'];path=args.source_root/('附件1.炉号-6B03205.xlsb' if num==1 else 'Data/Data/'+Path(m['path']).name)
    if not path.exists():path=args.source_root/('corrected/附件1.炉号-6B03205.xlsb' if num==1 else 'original/'+Path(m['path']).name)
    before=hashlib.sha256(path.read_bytes()).hexdigest();assert before==m['sha256'];i=int(c['Excel_Row'])-2;j=int(c['Excel_Column'])-2;rows=[]
    with open_workbook(str(path)) as b:
        with b.get_sheet(1) as sh:
            it=sh.rows();header=[v.v for v in next(it)]
            for ii,row in enumerate(it):
                if max(0,i-5)<=ii<=i+5:rows.append([v.v for v in row])
                if ii>i+5:break
    a=np.array(rows,float);s=a[:,1:-3];t=(a[:,0]-1)*.5;w=np.array(header[1:-3],float);l=max(0,j-20);r=min(len(w),j+21)
    fig,ax=plt.subplots(1,3,figsize=(14,4),layout='constrained');lo=s[:,l:r].min();hi=s[:,l:r].max();im=ax[0].pcolormesh(w[l:r],t,s[:,l:r],shading='auto',vmin=lo,vmax=hi);fig.colorbar(im,ax=ax[0],label=f'Raw intensity [{lo:g}, {hi:g}]');ax[0].set(xlabel='Wavelength (nm)',ylabel='Time (s)')
    ii=int(np.where(a[:,0]==float(c['Sequence']))[0][0]);ax[1].plot(w[l:r],s[ii,l:r],'.-');ax[1].axvline(w[j],c='r');ax[1].set(xlabel='Wavelength (nm)',ylabel='Raw intensity (local scale)');ax[2].plot(t,s[:,j],'.-');ax[2].axvline(float(c['Time_s']),c='r');ax[2].set(xlabel='Time (s)',ylabel='Raw intensity (local scale)');fig.suptitle(c['Case_ID']+' | local zoom; all raw nodes; linear autoscale, no sampling/transform');out=P/'专项分析/S06_谱峰与异常反例研究'/(c['Case_ID']+'_低点局部放大.png');fig.savefig(out,dpi=135);plt.close(fig)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before;records.append(dict(Case_ID=c['Case_ID'],SHA256=before,Unchanged=True,Color_Min=lo,Color_Max=hi,Plot=out.relative_to(P).as_posix()))
(P/'研究成果/低点图核验.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('Three readable low-point zoom figures created; all source hashes unchanged.')
