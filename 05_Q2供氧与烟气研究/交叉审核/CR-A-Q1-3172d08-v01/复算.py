"""只读复算固定 Q1 快照和本地官方附件。仅写审核输出目录。"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from pyxlsb import open_workbook

parser = argparse.ArgumentParser()
parser.add_argument("snapshot", type=Path)
parser.add_argument("repo", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--sim", type=Path, required=True)
args = parser.parse_args()
q = args.snapshot / "04_Q1光谱研究"
v = q / "实验验证"
pre = v / "正式清洗前置审核"
s = q / "专项分析"

def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def components(mask, diagonal):
    offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if diagonal:
        offsets += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    unseen = set(zip(*np.where(mask)))
    sizes = []
    while unseen:
        todo = [unseen.pop()]
        count = 0
        while todo:
            i, j = todo.pop()
            count += 1
            neighbors = [(i + di, j + dj) for di, dj in offsets]
            for neighbor in neighbors:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    todo.append(neighbor)
        sizes.append(count)
    assert sum(sizes) == mask.sum()
    return len(sizes), max(sizes, default=0)

def data(path, sheet, expected_headers):
    with open_workbook(str(path)) as book, book.get_sheet(sheet) as table:
        rows = iter(table.rows())
        header = next(rows)
        assert header[0].r == 0 and [cell.v for cell in header] == expected_headers
        values = []
        for excel_row, row in enumerate(rows, 2):
            assert row[0].r == excel_row - 1 and len(row) == len(header)
            values.append([cell.v for cell in row[:-3]])
    matrix = np.array(values, dtype=float)
    return matrix[:, 0], np.array(expected_headers[1:-3], dtype=float), matrix[:, 1:]

def saturation_neighbors(mask, i, j, radius):
    n, p = mask.shape
    return bool(mask[max(i-radius, 0):i, j].any() or mask[i+1:i+radius+1, j].any()
                or mask[i, max(j-radius, 0):j].any() or mask[i, j+1:j+radius+1].any())

def compare(record, expected):
    for key, actual in expected.items():
        before = record[key]
        ok = str(actual) == before if isinstance(actual, bool) else math.isclose(
            float(actual), float(before), rel_tol=1e-11, abs_tol=1e-9)
        if not ok:
            yield f"{key}: {before}→{actual}"

files = read(q / "交叉审核文件清单.csv")
file_diffs = []
for row in files:
    relative = row["Repository_Relative_Path"]
    path = args.snapshot / relative
    if not path.is_file():
        file_diffs.append((relative, "missing"))
        continue
    raw = path.read_bytes()
    if len(raw) != int(row["Bytes_Git_LF"]) or sha(path) != row["SHA256_Git_LF"]:
        file_diffs.append((relative, "size/hash"))
ref_path = pre / "Q1参考区域审核表.csv"
refs = read(ref_path)
v02 = {row["Reference_ID"]: row for row in read(v / "V02_可信参考区/V02_候选参考区域登记表.csv")}
assert len(refs) == len(v02) == 70 and {r["Reference_ID"] for r in refs} == set(v02)
assert len({r["Reference_ID"] for r in refs}) == 70
assert all(r["Joint_Approval"] == "Pending" and r["Normal_Truth_Certified"] == "False" for r in refs)
assert len(read(s / "前置审核_v1/Q1参考区域审核表.csv")) == 0

s04 = s / "S04_65535候选饱和调查"
s01 = {r["Heat_ID"]: r for r in read(s / "S01_光谱基线核验/S01_光谱基线核验.csv")}
s03 = {r["Heat_ID"]: r for r in read(s / "S03_光谱结构调查/S03_逐炉光谱统计.csv")}
s05 = s / "S05_其他候选异常调查"
s06 = s / "S06_谱峰与异常反例研究"
upper_old = {row["Heat_ID"]: row for row in read(s04 / "S04_逐炉65535统计.csv")}
scores_old = read(s05 / "S05_候选异常登记表.csv")
repeats_old = read(s05 / "S05_重复波长列证据.csv")
cases_old = read(s06 / "S06_代表性案例登记表.csv")
manifest = load(args.snapshot / "01_赛题与原始数据/数据结构清单.json")
assert [item["attachment"] for item in manifest] == list(range(1, 11))
assert "corrected" in Path(manifest[0]["path"]).parts
heat_results, region_results, case_results, grids = [], [], [], {}
for item in manifest:
    heat = item["sheets"][0]
    path = args.repo / item["path"]
    assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
    seq, wave, x = data(path, heat, item["headers"])
    n, p = x.shape
    assert p == 2047 and n > 2 and np.all(np.diff(seq) == 1) and np.all(np.diff(wave) > 0)
    assert np.isfinite(x).all()
    grids[heat] = wave
    t = (seq-seq[0]) * 0.5
    upper = x == 65535
    count = int(upper.sum())
    rows, cols = int(upper.any(axis=1).sum()), int(upper.any(axis=0).sum())
    c4, m4 = components(upper, False)
    c8, m8 = components(upper, True)
    upper_stats = dict(Points=count, Point_Denominator=x.size, Point_Percent=100*count/x.size,
                       Affected_Rows=rows, Row_Denominator=n, Row_Percent=100*rows/n,
                       Affected_Columns=cols, Column_Denominator=p, Column_Percent=100*cols/p,
                       Components_4=c4, Components_8=c8, Largest_4=m4, Largest_8=m8)
    assert not list(compare(upper_old[heat], upper_stats)), heat
    repeated = np.flatnonzero(np.all(x[:, :-1] == x[:, 1:], axis=0))
    repeat_cols = {(int(j)+2, int(j)+3) for j in repeated}
    assert repeat_cols == {(int(r["Left_Excel_Column"]), int(r["Right_Excel_Column"]))
                           for r in repeats_old if r["Heat_ID"] == heat}
    duplicate_columns = {col for pair in repeat_cols for col in pair}
    neighbors = np.stack((x[:-2, 1:-1], x[2:, 1:-1], x[1:-1, :-2], x[1:-1, 2:]))
    med = np.median(neighbors, axis=0)
    mad = np.median(np.abs(neighbors - med), axis=0)
    score = (x[1:-1, 1:-1]-med)/(1.4826*mad+1)
    eligible = ~upper[1:-1, 1:-1]
    flags = {k: eligible & (abs(score) > k) for k in (12,20,30)}
    old_heat_scores = [row for row in scores_old if row["Heat_ID"] == heat]
    old_positions = {(int(row["Excel_Row"])-3, int(row["Excel_Column"])-3) for row in old_heat_scores}
    assert old_positions == set(zip(*np.where(flags[12])))
    for row in old_heat_scores:
        i, j = int(row["Excel_Row"])-3, int(row["Excel_Column"])-3
        assert math.isclose(float(row["Score"]), abs(score[i,j]), rel_tol=1e-11)
        assert row["Candidate_Type"] == ("局部正残差" if score[i,j] > 0 else "局部负残差")
        assert not list(compare(row, dict(Original_Value=x[i+1,j+1],
            Neighbor_Median=med[i,j], Neighbor_MAD=mad[i,j],
            Sequence=seq[i+1], Time_s=t[i+1], Wavelength_nm=wave[j+1])))
    baseline = dict(Rows=n, Spectral_Columns=p, Time_Last_s=t[-1],
        Wavelength_Min_nm=wave[0], Wavelength_Max_nm=wave[-1],
        Maximum=x.max(), Duplicate_Spectral_Rows=n-len({row.tobytes() for row in x}))
    assert not list(compare(s01[heat],baseline)), heat
    median = np.median(x)
    q25, q75, q99 = np.quantile(x,[.25,.75,.99])
    distribution = dict(Min=x.min(), Max=x.max(), Mean=x.mean(), Median=median,
        Std=x.std(), MAD_raw=np.median(abs(x-median)), IQR=q75-q25, Q99=q99)
    assert not list(compare(s03[heat],distribution)), heat
    heat_results.append(dict(Heat_ID=heat, Attachment=item["attachment"], File=path.name,
        SHA256=item["sha256"], **baseline, S03_Distribution=distribution,
        **upper_stats, Repeated_Adjacent_Pairs=sorted(repeat_cols),
        S05_Eligible=int(eligible.sum()), S05_Counts={str(k):int(mask.sum()) for k,mask in flags.items()}))
    for row in refs:
        if row["Heat_ID"] != heat:
            continue
        old = v02[row["Reference_ID"]]
        a,b,c,d = [int(row[k])-2 for k in ("Start_Excel_Row", "End_Excel_Row", "Start_Excel_Column", "End_Excel_Column")]
        assert 0 <= a <= b < n and 0 <= c <= d < p
        block = x[a:b+1,c:d+1]
        halo = upper[max(0,a-1):b+2,max(0,c-1):d+2]
        valid = [(i,j) for i in range(max(1,a),min(n-1,b+1)) for j in range(max(1,c),min(p-1,d+1))]
        expanded = [(i,j) for i in range(a,b+1) for j in range(c,d+1)]
        u2,u4 = (sum(saturation_neighbors(upper,i,j,radius) for i,j in expanded) for radius in (2,4))
        profile = np.median(block,axis=0)
        peak = bool(((profile[1:-1]>profile[:-2]) & (profile[1:-1]>profile[2:])).any())
        prior = sum(flags[12][i-1,j-1] for i,j in valid)
        duplicate = bool(duplicate_columns.intersection(range(c+2,d+3)))
        actual = dict(Start_Sequence=seq[a], End_Sequence=seq[b], Start_s=t[a], End_s=t[b],
            Min_nm=wave[c], Max_nm=wave[d], Points=block.size, Min=block.min(), Max=block.max(),
            Mean=block.mean(), Std=block.std(), Within_65535=int(upper[a:b+1,c:d+1].sum()),
            Halo_65535=int(halo.sum()), Halo_Points=halo.size, Neighbor_Evaluable_Centers=len(valid),
            Centers_With_Saturated_Neighbor=sum(saturation_neighbors(upper,i,j,1) for i,j in valid),
            Four_Neighbor_MAD_Zero=sum(mad[i-1,j-1]==0 for i,j in valid), Prior_S05_Count=prior,
            Repeated_Channel_Overlap=duplicate, Local_Median_Profile_Peak=peak,
            Max_Adjacent_Frame_Mean_Change=np.max(np.abs(np.diff(block,axis=0)).mean(axis=1)))
        diffs = list(compare(row,actual))
        location_fields = ("Heat_ID","Grid","Class","Start_Excel_Row","End_Excel_Row","Start_Excel_Column","End_Excel_Column")
        diffs += [f"V02 {key}" for key in location_fields if row[key] != old[key]]
        diffs += list(compare(old, {key:actual[key] for key in
            ("Points","Start_Sequence","End_Sequence","Start_s","End_s","Min_nm","Max_nm","Min","Max","Mean")}))
        diffs += list(compare(old, dict(Saturation_Count=actual["Within_65535"],
            Saturation_In_Halo=actual["Halo_65535"], Prior_Score_Candidates=prior,
            Repeated_Channel_Overlap=duplicate)))
        cls = row["Class"][0]
        notes = []
        if diffs:
            opinion = "暂缓采纳并对账"
        elif actual["Halo_65535"] or duplicate:
            opinion = "拒作普通参考，保留为困难案例"
        elif u4:
            opinion = "补证，半径4存在上限邻居"
        elif cls in "AF" and not prior and not actual["Four_Neighbor_MAD_Zero"] and not peak:
            opinion = "可列入普通参考待审名单"
        else:
            opinion = "补证，保留对应难例层"
        if actual["Within_65535"]:
            notes.append("框内上限值，仅作为疑似删失观测")
        elif actual["Halo_65535"]:
            notes.append("扩窗含上限，普通局部估计可能受污染")
        if duplicate:
            notes.append("重复边缘通道，保留坐标和值，核对采集机制")
        if u4:
            notes.append(f"按半径2/4的方向邻居，各有{u2}/{u4}个中心触及上限")
        if prior:
            notes.append(f"{prior}个S05候选，核对局部形态与同期工况")
        if actual["Four_Neighbor_MAD_Zero"]:
            notes.append("四邻域MAD为零，需冻结方向有效样本数与尺度底")
        if peak:
            notes.append("严格中位剖面峰存在，先核对峰两肩与逐帧持续性")
        if cls in "BCDE":
            notes.append({"B":"纳入峰保护层，复核逐帧峰位和宽度","C":"纳入高强度难例层，复核背景及峰宽",
                          "D":"纳入变化难例层，核对与Q2事件的时间依据","E":"核对两侧肩部和整段形态后确定用途"}[cls])
        if not notes:
            notes.append("请两位队员核验局部上下文与测量机制后决定是否纳入")
        region_results.append(dict(Reference_ID=row["Reference_ID"], Heat_ID=heat, Sheet=heat,
            Source_SHA256=item["sha256"], Grid=row["Grid"], Class=row["Class"], Excel_Rows=f"{a+2}–{b+2}",
            Excel_Columns=f"{c+2}–{d+2}", **actual, Radius2_Upper_Neighbor_Centers=u2,
            Radius4_Upper_Neighbor_Centers=u4, Q1_Recommendation=row["Recommendation"],
            Q2_Opinion=opinion, Q2_Evidence_Request="。".join(notes), Field_Comparison="；".join(diffs) or "全部核对一致",
            Evidence_Source="本次独立只读XLSB复算；V02/权威70区表对照", Joint_Approval="Pending", Normal_Truth_Certified=False))
    for row in cases_old:
        if row["Heat_ID"] != heat:
            continue
        i,j = int(row["Excel_Row"])-2,int(row["Excel_Column"])-2
        a=b=j
        if upper[i,j]:
            while a>0 and upper[i,a-1]:
                a-=1
            while b+1<p and upper[i,b+1]:
                b+=1
        frac = np.mean((x[:,j]>x[:,max(0,j-1)]) & (x[:,j]>x[:,min(p-1,j+1)]))
        result = dict(Sequence=seq[i],Time_s=t[i],Wavelength_nm=wave[j],Original_Value=x[i,j],
                      Plateau_Points=b-a+1 if upper[i,j] else 0,Repeated_Local_Peak_Fraction=frac)
        diffs = list(compare(row,result))
        for key, edge in (("Left_Shoulder",a-1),("Right_Shoulder",b+1)):
            if row[key]:
                diffs += list(compare(row,{key:x[i,edge]}))
        local = [float(value) for value in row["Temporal_Neighbors"].split(";")]
        if not np.array_equal(local,x[max(0,i-2):i+3,j]):
            diffs.append("Temporal_Neighbors")
        case_results.append(dict(Case_ID=row["Case_ID"],Excel_Row=i+2,Excel_Column=j+2,**result,
            Left_Shoulder=float(x[i,a-1]) if upper[i,j] and a>0 else None,
            Right_Shoulder=float(x[i,b+1]) if upper[i,j] and b+1<p else None, Differences=diffs))
    assert sha(path) == item["sha256"]
    print(f"{heat}: XLSB/hash/7 boxes",flush=True)

wa,wb=grids[manifest[0]["sheets"][0]],grids[manifest[4]["sheets"][0]]
assert all(np.array_equal(w,wa if i<4 else wb) for i,w in enumerate(grids.values()))
delta=wa-wb
frel=Path("V04_实验程序准备/V04_模拟功能测试结果.json")
rrel=Path("正式清洗前置审核/独立模拟风险测试.json")
functional_base,functional_new=load(v/frel),load(args.sim/"实验验证"/frel)
risk_base,risk_new=load(v/rrel),load(args.sim/"实验验证"/rrel)
compared_fields=("checks","synthetic_metrics","folds","injection_records","mask_records")
summary=dict(Commit="3172d088feb9da0fed3a784e5071fcb9905b6a9e", Hash_Manifest_Entries=len(files),
    Hash_Manifest_Differences=file_diffs, Reference_SHA256=sha(ref_path),
    Reference_Config_Hash_Match=sha(ref_path)==load(pre/"Q1正式验证配置草案.json")["reference_sha256"],
    Original_Recommendations=Counter(r["Recommendation"] for r in refs),
    Independent_Opinions=Counter(r["Q2_Opinion"] for r in region_results),
    Cases=case_results, Functional_Count=len(functional_new["checks"]),
    Functional_Passed=sum(x["Passed"] for x in functional_new["checks"]),
    Functional_Reproduction_Exact={key:functional_base[key]==functional_new[key] for key in compared_fields},
    Risk_Count=len(risk_new["checks"]),
    Risk_Passed=sum(x["Check_Passed"] for x in risk_new["checks"]), Risk_Exact=risk_base==risk_new,
    Risk_Reproduction=risk_new, Grid=dict(Delta_Min_nm=delta.min(),Delta_Max_nm=delta.max(),
        MAE_nm=abs(delta).mean(),RMSE_nm=np.sqrt((delta**2).mean()),Overlap_nm=[max(wa[0],wb[0]),min(wa[-1],wb[-1])]),
    Heats=heat_results)
args.output.mkdir(parents=True, exist_ok=True)
write(args.output/"70区独立意见.csv",region_results)
(args.output/"关键复算结果.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
