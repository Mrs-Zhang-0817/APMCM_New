"""Synthetic-only R0 span and binding checks, without workbook reads."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from r0_preparation import reconstruct_r0_limited as r0, verify_binding, digest, sha256, window_digest


class R0PreparationTests(unittest.TestCase):
    def test_physical_spans_and_no_extrapolation(self):
        t=np.array([0., .5, 1.]); w=np.array([400.,400.4,401.])
        x=2*t[:,None]+3*w[None,:]; x[1,1]=np.nan
        good,info=r0(x,t,w,max_time_span_s=1,max_wave_span_nm=1,order='time-wave')
        self.assertAlmostEqual(good[1,1],1202.2)
        self.assertEqual(info['support_span'][1,1],1)
        bad,info=r0(x,t,w,max_time_span_s=.9,max_wave_span_nm=.9)
        self.assertTrue(np.isnan(bad[1,1]))
        edge=x.copy(); edge[0]=np.nan
        fitted,info=r0(edge,t,w,max_time_span_s=1,max_wave_span_nm=1)
        self.assertTrue(np.isnan(fitted[0]).all())

    def test_second_axis_limit(self):
        t=np.array([0.,.5,1.]); w=np.array([400.,400.3,400.8])
        x=2*t[:,None]+w[None,:]; x[:,1]=np.nan
        restored,info=r0(x,t,w,max_time_span_s=1,max_wave_span_nm=.8)
        np.testing.assert_allclose(restored,2*t[:,None]+w[None,:])
        rejected,info=r0(x,t,w,max_time_span_s=1,max_wave_span_nm=.79)
        self.assertTrue(np.isnan(rejected[:,1]).all())

    def test_order_and_estimated_support(self):
        x=np.array([[1.,np.nan,3.],[np.nan,np.nan,6.],[7.,8.,9.]])
        t=w=np.array([0.,1.,2.])
        for order in ('time-wave','wave-time'):
            restored,info=r0(x,t,w,max_time_span_s=2,max_wave_span_nm=2,order=order)
            self.assertTrue(info['used_estimated_support'].any())
            self.assertTrue(np.isfinite(restored).all())
            np.testing.assert_equal(restored[np.isfinite(x)],x[np.isfinite(x)])

    def test_invalid_parameters(self):
        for limit in (0,-1,np.nan,np.inf):
            with self.assertRaises(ValueError):r0(np.ones((2,2)),[0,1],[0,1],max_time_span_s=limit,max_wave_span_nm=1)
        with self.assertRaises(ValueError):r0(np.ones((2,2)),[0,0],[0,1],max_time_span_s=1,max_wave_span_nm=1)

    def test_binding_and_each_tamper(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source';source.write_bytes(b'synthetic source fixture')
            code=Path(root)/'code.py';code.write_bytes(b'# fixture')
            x=np.array([[1.,2.],[3.,4.]]);t=np.array([0.,.5]);w=np.array([400.,400.4])
            config={'status':'Pending','limit':1};manifest=[{'reference_id':'synthetic'}]
            b=dict(source_sha256=sha256(source),window_sha256=window_digest(x,t,w),
                   config_sha256=digest(config),reference_manifest_sha256=digest(manifest),
                   code_sha256={'code.py':sha256(code)})
            def check(a=x,tt=t,ww=w,c=config,m=manifest):
                return verify_binding(a,tt,ww,b,c,m,{'code.py':code},source)
            self.assertTrue(check())  # integrity only, never execution authorization
            for changes in ({'a':x+1},{'tt':t+1},{'ww':w+1},{'c':{'status':'Approved'}},{'m':[]}):
                with self.assertRaises(ValueError):check(**changes)
            code.write_bytes(b'# changed')
            with self.assertRaises(ValueError):check()
            code.write_bytes(b'# fixture');source.write_bytes(b'changed')
            with self.assertRaises(ValueError):check()


if __name__=='__main__':unittest.main()
