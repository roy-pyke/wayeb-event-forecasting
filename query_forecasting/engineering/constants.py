"""Remove only exact constant controls, whose moments follow from total mass."""
import numpy as np
from recombine import recombine


def without_constants(weights,features,target,rng):
    features=np.asarray(features,float)
    variable=np.any(features!=features[0],axis=0)
    result,meta=recombine(weights,features[:,variable],target,rng)
    error=float(np.max(np.abs((result-np.asarray(weights))@features),initial=0.))
    if error>2e-9:raise AssertionError('original constraint drift after constant elimination')
    meta['moment_error']=max(meta['moment_error'],error)
    meta['removed_constant_columns']=int((~variable).sum())
    return result,meta
