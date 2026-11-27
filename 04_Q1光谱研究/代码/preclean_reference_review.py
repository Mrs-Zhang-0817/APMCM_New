"""Audit existing 70 rectangles only; no generic EDA or real-data reconstruction."""
from pathlib import Path
import argparse,csv,json,hashlib
import numpy as np
from pyxlsb import open_workbook
P=Path(__file__).resolve().parents[1];R=P.parent;O=P/'实验验证/正式清洗前置审核';O.mkdir(exist_ok=True)
def read(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,rr):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr)
a=argparse.ArgumentParser();a.add_argument('--source-root',type=Path,required=True);args=a.parse_args()
refs=read(P/'实验验证/V02_可信参考区/V02_候选参考区域登记表.csv');manifest=json.loads((R/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'));rows=[];sources=[]
for m in manifest:
    num=m['attachment'];heat=m['sheets'][0];path=args.source_root/('附件1.炉号-6B03205.xlsb' if num==1 else 'Data/Data/'+Path(m['path']).name)
    if not path.exists():path=args.source_root/('corrected/附件1.炉号-6B03205.xlsb' if num==1 else 'original/'+Path(m['path']).name)
    before=hashlib.sha256(path.read_bytes()).hexdigest();assert before==m['sha256']
    subset=[r for r in refs if r['Heat_ID']==heat];needed=set()
    for r in subset:needed.update(range(max(0,int(r['Start_Excel_Row'])-3),int(r['End_Excel_Row'])))
    cache={}
    with open_workbook(str(path)) as book:
        with book.get_sheet(1) as sh:
            it=sh.rows();head=[c.v for c in next(it)];wave=np.array(head[1:-3],float)
            for i,rr in enumerate(it):
                if i in needed:cache[i]=np.array([c.v for c in rr],float)
    for r in subset:
        lo=int(r['Start_Excel_Row'])-2;hi=int(r['End_Excel_Row'])-1;jl=int(r['Start_Excel_Column'])-2;jr=int(r['End_Excel_Column'])-1
        block=np.vstack([cache[i][1:-3][jl:jr] for i in range(lo,hi)]);halo=np.vstack([cache[i][1:-3][max(0,jl-1):min(2047,jr+1)] for i in range(max(0,lo-1),hi+1) if i in cache]);sat=int(np.sum(block==65535));hs=int(np.sum(halo==65535));assert sat==int(r['Saturation_Count']) and hs==int(r['Saturation_In_Halo'])
        zero_mad=0;contaminated=0;centers=0
        for i in range(lo,hi):
            for j in range(jl,jr):
                if i-1 not in cache or i+1 not in cache or j==0 or j==2046:continue
                vv=np.array([cache[i-1][j+1],cache[i+1][j+1],cache[i][j],cache[i][j+2]]);med=np.median(vv);mad=np.median(abs(vv-med));centers+=1;zero_mad+=int(mad==0);contaminated+=int(np.any(vv==65535))
        profile=np.median(block,axis=0);localpeak=bool(np.any((profile[1:-1]>profile[:-2])&(profile[1:-1]>profile[2:]))) if len(profile)>2 else False
        timechange=float(np.max(np.mean(abs(np.diff(block,axis=0)),axis=1))) if len(block)>1 else 0
        support=['精确坐标和原值与V02一致；无填补或处理']
        if not hs:support.append('本框及一节点环邻域未见65535（不保证远邻无污染）')
        if not int(r['Prior_Score_Candidates']):support.append('未与旧S05候选重合，此项仅辅助非正常认证')
        if r['Class'][0]=='B':support.append('来自重复出现的尖锐结构候选，适合峰保护审核')
        oppose=[]
        if sat:oppose.append(f'框内{sat}上限点，未知真实峰顶，不能作未截断真值')
        elif hs:oppose.append(f'环邻域含{hs}上限点，局部基线/尺度可能污染')
        if r['Repeated_Channel_Overlap']=='True':oppose.append('与整列重复边缘通道重合，缺独立测量机制证据')
        if int(r['Prior_Score_Candidates']):oppose.append('与旧候选重合，需要原值审核，不能以分数自动否决')
        if r['Class'][0] in 'BCDE':oppose.append('峰形/高值/快速变化真值未知，需两人检查局部时间和波长支持')
        if zero_mad:oppose.append('存在四邻域MAD=0，固定floor影响评分')
        if hs or r['Repeated_Channel_Overlap']=='True':status='Reject Candidate';use='拒绝作为普通无截断、独立参考真值；仍保留为削顶/边缘困难案例'
        elif r['Class'][0] in 'AF' and not int(r['Prior_Score_Candidates']):status='Accept Candidate';use='仅建议进入人工确认名单；不授权真实验证、不认证正常'
        else:status='Needs More Evidence';use='补充峰形、工艺或异常候选上下文后再讨论'
        row=dict(Reference_ID=r['Reference_ID'],Heat_ID=heat,Grid=r['Grid'],Class=r['Class'],Start_Sequence=r['Start_Sequence'],End_Sequence=r['End_Sequence'],Start_Excel_Row=r['Start_Excel_Row'],End_Excel_Row=r['End_Excel_Row'],Start_Excel_Column=r['Start_Excel_Column'],End_Excel_Column=r['End_Excel_Column'],Start_s=r['Start_s'],End_s=r['End_s'],Min_nm=wave[jl],Max_nm=wave[jr-1],Points=block.size,Min=block.min(),Max=block.max(),Mean=block.mean(),Std=block.std(),Within_65535=sat,Halo_65535=hs,Halo_Points=halo.size,Centers_With_Saturated_Neighbor=contaminated,Neighbor_Evaluable_Centers=centers,Four_Neighbor_MAD_Zero=zero_mad,Prior_S05_Count=r['Prior_Score_Candidates'],Repeated_Channel_Overlap=r['Repeated_Channel_Overlap'],Local_Median_Profile_Peak=localpeak,Max_Adjacent_Frame_Mean_Change=timechange,Sharp_or_Process_Change='尖锐候选峰' if r['Class'][0]=='B' else '快速变化候选，未确认工艺事件' if r['Class'][0]=='D' else '局部峰存在但未认证' if localpeak else '未在本框中位剖面见严格局部峰',Support='；'.join(support),Opposition='；'.join(oppose) or '未发现上述风险不等于正常真值',Recommendation=status,Recommendation_Scope=use,Joint_Approval='Pending',Normal_Truth_Certified=False)
        rows.append(row)
    assert before==hashlib.sha256(path.read_bytes()).hexdigest();sources.append(dict(Heat_ID=heat,SHA256=before,Unchanged=True));print(f'Review {num}/10: 7 existing rectangles only',flush=True)
write(O/'Q1参考区域审核表.csv',rows)
(O/'前置审核来源核验.json').write_text(json.dumps(dict(sources=sources,scope='仅70框及一节点环邻域；全文件流式解码定位，不重做泛化EDA',real_preprocessing=False,real_formal_validation=False),ensure_ascii=False,indent=2),encoding='utf-8')
