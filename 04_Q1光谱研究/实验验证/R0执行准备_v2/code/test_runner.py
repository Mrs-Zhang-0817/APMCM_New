"""New delta tests only. All arrays/identities here are SYNTHETIC FIXTURES."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import r0_runner as runner
import r0_preparation as r0


def fixture():
    cfg=dict(reference_strata={'background_candidate':['FIXTURE-A'],'dynamic_challenge':['FIXTURE-B']},
             seeds=[20261127,20261128,20261129],masked_points_per_region=[1,2],
             orders=['time-wave','wave-time'],core_slice=[4,11,4,21],
             max_time_span_s=1.,max_wave_span_nm=1.6)
    refs=[{'reference_id':'FIXTURE-A'},{'reference_id':'FIXTURE-B'}]
    codes={'files':{'r0_runner.py':'fixture-code','r0_preparation.py':'fixture-dependency'}}
    approval=dict(status='Approved',domain='synthetic_fixture',approval_id='SYNTHETIC-ONLY-NOT-HUMAN-APPROVAL',
                  approvers=[{'name':'SYNTHETIC-FIXTURE-A','confirmed_at':'fixture'},
                             {'name':'SYNTHETIC-FIXTURE-B','confirmed_at':'fixture'}],
                  permitted_action=runner.ACTION,reference_ids=['FIXTURE-A','FIXTURE-B'],
                  permitted_uses=cfg['reference_strata'],contract=runner.contract(cfg,refs,codes))
    return cfg,refs,codes,approval


class DeltaTests(unittest.TestCase):
    def test_sampling_is_reproducible_nested_and_without_replacement(self):
        ok=np.ones((7,17),bool);ok[0,0]=False
        for ordinal in (0,1):
            for seed in (20261127,20261128,20261129):
                a=runner.sample_two(ok,seed,ordinal);b=runner.sample_two(ok,seed,ordinal)
                self.assertEqual(a,b);self.assertNotEqual(a[0],a[1]);self.assertNotIn([0,0],a)
                self.assertEqual(a[:1],a[:2][:1])

    def test_kernel_shares_masks_across_orders_and_retains_inputs(self):
        cfg,refs,_,_=fixture();t=np.arange(15)*.5;w=400+np.arange(25)*.3
        x=10+2*t[:,None]+w[None,:];before=x.copy()
        records=runner.run_arrays(x,t,w,refs[0],cfg,0)
        self.assertEqual(len(records),12);np.testing.assert_equal(x,before)
        for i in range(0,len(records),2):
            a,b=records[i:i+2];self.assertEqual(a['requested_positions'],b['requested_positions'])
            self.assertEqual(a['requested'],a['k']);self.assertEqual(a['unresolved'],0)
            self.assertLess(a['MAE'],1e-10)
        for start in (0,4,8):self.assertEqual(records[start]['requested_positions'],records[start+2]['requested_positions'][:1])

    def test_partial_and_all_unresolved_denominators(self):
        truth=np.ones((1,3));mask=np.ones((1,3),bool)
        info={'supports':[],'used_estimated_support':np.zeros((1,3),bool)}
        out=runner.evaluate(np.array([[2,np.nan,np.nan]]),truth,mask,[0],[1,2,3],info)
        self.assertEqual((out['requested'],out['resolved'],out['unresolved']),(3,1,2))
        self.assertEqual(out['coverage'],1/3);self.assertEqual(out['MAE'],1)
        self.assertFalse(out['coverage_gate_passed'])
        out=runner.evaluate(np.full((1,3),np.nan),truth,mask,[0],[1,2,3],info)
        self.assertEqual(out['coverage'],0);self.assertIsNone(out['MAE']);self.assertIsNone(out['RMSE'])
        self.assertIsNone(out['p95']);self.assertIsNone(out['max'])
        self.assertTrue(all(p['reason'] for p in out['points']))

    def test_weighted_summary_uses_requests(self):
        rows=[dict(requested=1,resolved=1,reference_id='A',stratum='background',order='time-wave'),
              dict(requested=3,resolved=0,reference_id='B',stratum='dynamic',order='time-wave')]
        result=runner.summarize(rows)
        self.assertEqual(result['all_requests']['coverage'],.25)
        self.assertEqual(result['groups']['reference_id']['B']['unresolved'],3)

    def test_approval_invalidated_by_every_changed_contract_component(self):
        cfg,refs,codes,approval=fixture()
        self.assertTrue(runner.authorize(approval,cfg,refs,codes,domain='synthetic_fixture'))
        for index in range(3):
            changed=copy.deepcopy([cfg,refs,codes]);
            if index==0:changed[0]['max_time_span_s']=2
            elif index==1:changed[1][0]['reference_id']='CHANGED'
            else:changed[2]['files']['r0_runner.py']='CHANGED'
            with self.assertRaises(PermissionError):runner.authorize(approval,*changed,domain='synthetic_fixture')

    def test_missing_approval_scope_domain_and_uses_rejected(self):
        cfg,refs,codes,a=fixture()
        for key,value in [('status','Pending'),('approvers',[]),('approval_id',None),
                          ('permitted_action','full_cleaning'),('reference_ids',[]),('permitted_uses',{})]:
            b=copy.deepcopy(a);b[key]=value
            with self.assertRaises(PermissionError):runner.authorize(b,cfg,refs,codes,domain='synthetic_fixture')
        with self.assertRaises(PermissionError):runner.authorize(None,cfg,refs,codes)
        with self.assertRaises(PermissionError):runner.authorize(a,cfg,refs,codes,domain='real')

    def test_pending_real_cli_never_loads_or_samples(self):
        cfg,refs,codes,a=fixture();a['status']='Pending'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,obj in [('parameters.json',cfg),('references.json',refs),('code_manifest.json',codes),('approval.json',a)]:
                (root/name).write_text(json.dumps(obj),encoding='utf-8')
            with patch.object(r0,'load_window') as loader,patch.object(runner,'sample_two') as sampler:
                with self.assertRaises(PermissionError):runner.run_real(root,root/'approval.json',root/'MISSING-SOURCES',root/'out.json')
                loader.assert_not_called();sampler.assert_not_called();self.assertFalse((root/'out.json').exists())

    def test_modified_code_rejected_against_manifest(self):
        import platform
        folder=Path(runner.__file__).parent
        codes=dict(files={n:r0.sha256(folder/n) for n in ('r0_runner.py','r0_preparation.py')},
                   runtime=dict(python=platform.python_version(),numpy=np.__version__))
        runner.checked_code_manifest(codes)
        codes['files']['r0_preparation.py']='CHANGED-FIXTURE-HASH'
        with self.assertRaises(PermissionError):runner.checked_code_manifest(codes)


if __name__=='__main__':unittest.main()
