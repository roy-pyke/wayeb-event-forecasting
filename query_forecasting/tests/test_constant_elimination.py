import sys
import numpy as np
from queryforecast.common import PACKAGE
for folder in ['occupancy','engineering']:sys.path.insert(0,str(PACKAGE/folder))
from constants import without_constants


def test_exact_constants_are_implied_by_mass_including_nonbinary_constants():
    rng=np.random.default_rng(13);w=rng.random(80);w/=w.sum()
    x=rng.normal(size=(80,8));f=np.c_[x,np.zeros((80,7)),np.full((80,5),3.14159)]
    for seed in range(8):
        v,meta=without_constants(w,f,20,np.random.default_rng(seed))
        assert meta['removed_constant_columns']==12 and meta['rank']==9
        assert np.count_nonzero(v)<=20 and np.all(v>=0)
        np.testing.assert_allclose(v@f,w@f,atol=2e-10)
        np.testing.assert_allclose(v.sum(),1.,atol=1e-12)
