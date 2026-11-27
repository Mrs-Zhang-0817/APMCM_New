"""Finalize local draft integrity records, run targeted tests; no real masks."""
import csv
import io
import json
import platform
import unittest
from pathlib import Path
import numpy as np
from r0_preparation import sha256, digest, verify_binding


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--source-root',type=Path,required=True)
    args=p.parse_args();out=args.package;code=Path(__file__).parent
    config=json.loads((out/'config_pending.json').read_text(encoding='utf-8'))
    manifest=json.loads((out/'reference_manifest_pending.json').read_text(encoding='utf-8'))
    if config['status']!='Pending' or config['real_data_execution_allowed'] is not False:
        raise ValueError('This finalizer is for unapproved preparation only')
    files=['r0_preparation.py','prepare_r0_evidence.py','test_r0_preparation.py',
           'detection_metrics_v3.py','test_detection_metrics_v3.py','finalize_r0_preparation.py']
    paths={name:code/name for name in files}
    hashes={name:sha256(path) for name,path in paths.items()}
    bindings=[]
    for item in manifest:
        with (out/(item['reference_id']+'_raw_support.csv')).open(encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        t=np.unique([float(r['time_s']) for r in rows]);w=np.unique([float(r['wavelength_nm']) for r in rows])
        x=np.array([float(r['raw_intensity']) for r in rows]).reshape(len(t),len(w))
        b=dict(reference_id=item['reference_id'],source_sha256=item['source_sha256'],
               window_sha256=item['window_sha256'],config_sha256=digest(config),
               reference_manifest_sha256=digest(manifest),code_sha256=hashes)
        source=args.source_root/item['source_file'] if item['heat']=='6B03205' else args.source_root/'Data'/'Data'/item['source_file']
        verify_binding(x,t,w,b,config,manifest,paths,source)
        bindings.append(b)
    suite=unittest.TestSuite()
    for name in ('test_r0_preparation','test_detection_metrics_v3'):
        suite.addTests(unittest.TestLoader().loadTestsFromName(name))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'synthetic_checks.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():raise RuntimeError(stream.getvalue())
    record=dict(task='A-Q1-MVM-001b',python=platform.python_version(),numpy=np.__version__,
                checks_run=result.testsRun,failures=0,errors=0,actual_window_bindings_verified=len(bindings),
                real_masking_executed=False,formal_cleaning=False,training=False,
                config_sha256=digest(config),reference_manifest_sha256=digest(manifest),code_sha256=hashes)
    for name,obj in [('input_bindings.json',bindings),('checks_and_hashes.json',record)]:
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
