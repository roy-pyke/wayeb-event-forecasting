"""Standard Euclidean coherence repair for a finite feasible-label polytope."""
import numpy as np
from scipy.spatial import ConvexHull


class FeasiblePolytope:
    def __init__(self,vertices):
        self.vertices=np.asarray(vertices,dtype=float)
        # Every present task admits all-zero labels (future silence); affine hull
        # is therefore a linear subspace. Assert this rather than assume it.
        assert np.any((self.vertices==0).all(1))
        _,s,v=np.linalg.svd(self.vertices,full_matrices=False)
        rank=int(np.sum(s>1e-10));self.basis=v[:rank].T
        if rank==0: self.A=np.zeros((0,0));self.b=np.zeros(0)
        elif rank==1:
            z=self.vertices@self.basis
            self.A=np.array([[1.],[-1.]]);self.b=np.array([-z.max(),z.min()])
        else:
            eq=ConvexHull(self.vertices@self.basis).equations
            # Qhull triangulates facets; de-duplicate coplanar constraints.
            eq=np.unique(np.round(eq,11),axis=0)
            self.A=eq[:,:-1];self.b=eq[:,-1]
        self.norm=(self.A*self.A).sum(1)

    def contains(self,points,tolerance=1e-7):
        points=np.asarray(points,dtype=float).reshape(-1,self.vertices.shape[1])
        z=points@self.basis
        residual=np.max(np.abs(points-z@self.basis.T),axis=1)
        if not len(self.A): return residual<=tolerance
        return (residual<=tolerance)&((z@self.A.T+self.b)<=tolerance).all(1)

    def project(self,points):
        shape=np.shape(points);x=np.asarray(points,dtype=float).reshape(-1,self.vertices.shape[1])
        z=x@self.basis
        if not len(self.A): return np.zeros_like(x).reshape(shape)
        active=((z@self.A.T+self.b)>1e-10).any(1)
        if active.any():
            v=z[active].copy();correction=np.zeros((len(v),len(self.A)))
            for _ in range(500):
                before=v.copy()
                for j,(a,b,norm) in enumerate(zip(self.A,self.b,self.norm)):
                    v+=correction[:,j,None]*a
                    update=np.maximum((v@a+b)/norm,0)
                    v-=update[:,None]*a;correction[:,j]=update
                if np.max(np.abs(v-before))<1e-10 and ((v@self.A.T+self.b)<=1e-9).all():break
            if not ((v@self.A.T+self.b)<=1e-8).all(): raise ArithmeticError('polytope projection failed')
            z[active]=v
        return np.clip(z@self.basis.T,0,1).reshape(shape)
