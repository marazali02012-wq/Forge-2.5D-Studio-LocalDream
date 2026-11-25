import unittest
import numpy as np
from joint_quality import edge_metrics, refine_joint_weights

def tube(radius=.13, step=.025):
    y=np.arange(-.6,.601,step); a=np.arange(24)*2*np.pi/24
    v=np.array([[radius*np.cos(t),s,radius*np.sin(t)] for s in y for t in a]); f=[]
    for i in range(len(y)-1):
        for k in range(24):
            a=i*24+k;b=i*24+(k+1)%24;c=a+24;d=b+24
            f.extend([[a,b,c],[b,d,c]])
    return v,np.array(f)

class TestJoint(unittest.TestCase):
    def test_bend_and_seam(self):
        v,f=tube(); pts=np.array([[0,-.6,0],[0,0,0],[0,.6,0]])
        w=np.clip((v[:,1]+.035)/.07,0,1); js=np.tile([0,1,2,0],(len(v),1));ws=np.c_[1-w,w,np.zeros((len(v),2))].astype('float32')
        # Duplicate a UV seam vertex, attach duplicate to one triangle.
        v=np.vstack([v,v[576]]);js=np.vstack([js,js[576]]);ws=np.vstack([ws,ws[576]]);f[f==576]=len(v)-1
        outj,outw,report=refine_joint_weights(v,f,pts,['Root','L Elbow','L Wrist'],[-1,0,1],js,ws)
        self.assertTrue(report[0]['accepted']);self.assertLess(report[0]['after']['p95'],report[0]['before']['p95'])
        self.assertTrue(np.array_equal(outw[-1],outw[576]));self.assertTrue(np.array_equal(outj[-1],outj[576]))
        far=abs(v[:,1])>.35;self.assertTrue(np.array_equal(outw[far],ws[far]));self.assertTrue(np.array_equal(outj[far],js[far]))
        self.assertTrue(np.allclose(outw.sum(axis=1),1));self.assertTrue((outw>=0).all())
    def test_metrics(self):
        v,f=tube();m=edge_metrics(v,v,f);self.assertEqual(m['p95'],0);self.assertEqual(m['area_loss'],0)

if __name__=='__main__':unittest.main()
