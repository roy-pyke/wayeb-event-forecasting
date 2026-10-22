"""State-conditioned probability coordinate codecs; classical linear algebra.

All policies share quantization, projection, and the exact outcome loss oracle.
Only their representation differs. Unquantized reconstruction is structurally
exact; finite-precision messages are checked after actual serialization.
"""
import struct
import numpy as np
from scipy.linalg import qr
from .wire import HEADER

META=struct.Struct('!HB')
MASK=struct.Struct('!H')
PRECISIONS=(8,16,32,64)


class CoordinateMap:
    def __init__(self,indices,reconstruct):
        self.indices=np.asarray(indices,dtype=int)
        self.reconstruct=np.asarray(reconstruct,dtype=float)
        self.dimension=len(self.indices)

    @classmethod
    def compile(cls,profiles,mode='basis'):
        y=np.asarray(profiles,dtype=float);d=y.shape[1]
        assert np.any((y==0).all(1)), 'This implementation requires future silence.'
        if mode=='all': indices=np.arange(d)
        elif mode=='zero': indices=np.flatnonzero(y.max(0))
        elif mode=='basis':
            rank=np.linalg.matrix_rank(y,tol=1e-10)
            indices=qr(y,pivoting=True,mode='economic')[2][:rank]
            indices=np.sort(indices)  # canonical coordinate order on the wire
        else: raise ValueError('unknown representation')
        if len(indices): matrix=np.linalg.lstsq(y[:,indices],y,rcond=1e-10)[0]
        else: matrix=np.zeros((0,d))
        if mode in ('all','zero'):
            matrix=np.eye(d)[indices]
        matrix=np.round(matrix,12)
        assert np.max(np.abs(y[:,indices]@matrix-y))<1e-9
        return cls(indices,matrix)

    def expand(self,coordinates):
        return np.asarray(coordinates)@self.reconstruct


def pack_values(values,bits):
    values=np.asarray(values,dtype=float)
    if not np.isfinite(values).all() or ((values < -1e-7)|(values > 1+1e-7)).any():
        raise ValueError('invalid probability coordinates')
    values=np.clip(values,0,1)
    if bits in (8,16):
        return np.rint(values*((1<<bits)-1)).astype('u1' if bits==8 else '>u2').tobytes()
    return values.astype('>f4' if bits==32 else '>f8').tobytes()


def unpack_values(body,bits):
    dtype={8:'u1',16:'>u2',32:'>f4',64:'>f8'}[bits]
    values=np.frombuffer(body,dtype=dtype).astype(float)
    if bits in (8,16): values/=((1<<bits)-1)
    if not np.isfinite(values).all() or ((values<0)|(values>1)).any():
        raise ValueError('invalid probability payload')
    return values


def encode_frame(timestamp,entity,sequence,version,state,coordinates,bits,mask=None):
    coordinates=np.asarray(coordinates)
    sparse=mask is not None
    flag=PRECISIONS.index(bits)+(4 if sparse else 0)
    result=HEADER.pack(int(timestamp),int(entity),int(sequence),int(version))+META.pack(int(state),flag)
    if sparse:
        mask=np.asarray(mask,dtype=bool)
        if len(mask)!=len(coordinates) or len(mask)>16: raise ValueError('invalid mask dimension')
        result+=MASK.pack(int(mask.astype(int)@(2**np.arange(len(mask)))))
        coordinates=coordinates[mask]
    return result+pack_values(coordinates,bits)


def decode_frame(packet,version,state,mapping,cached,polytope):
    if len(packet)<27: raise ValueError('truncated frame')
    timestamp,entity,sequence,received_version=HEADER.unpack_from(packet)
    q,flag=META.unpack_from(packet,24)
    if received_version!=version: raise ValueError('model version mismatch')
    if q!=state: raise ValueError('business state mismatch')
    if flag>=8: raise ValueError('unknown encoding')
    bits=PRECISIONS[flag%4];offset=27;sparse=bool(flag&4)
    mask=np.ones(mapping.dimension,dtype=bool)
    if sparse:
        if len(packet)<29: raise ValueError('truncated mask')
        code=MASK.unpack_from(packet,27)[0];offset=29
        if code>=2**mapping.dimension: raise ValueError('unknown coordinate mask')
        mask=((code>>np.arange(mapping.dimension))&1).astype(bool)
    if len(packet)!=offset+int(mask.sum())*(bits//8): raise ValueError('payload length mismatch')
    coordinates=np.asarray(cached)[mapping.indices].copy()
    coordinates[mask]=unpack_values(packet[offset:],bits)
    forecast=polytope.project(mapping.expand(coordinates))
    return timestamp,entity,sequence,forecast


def loss_bound(candidate,full,profiles):
    p=np.asarray(candidate);f=np.asarray(full)
    return float(np.mean(p*p-f*f)-2*np.min(profiles@(p-f))/len(f))


def select_message(cached,full,profiles,mapping,polytope,epsilon,metadata,partial=True):
    """Choose the cheapest certified serialized full or greedy sparse message.

    No future labels or future queries are used. Quantization and projection
    are explicitly included in each candidate's loss certificate.
    """
    timestamp,entity,sequence,version,state=metadata
    b=loss_bound(cached,full,profiles)
    if b<=epsilon+1e-12:return cached.copy(),b,b'',0
    if not mapping.dimension:raise ArithmeticError('zero-rank state cannot require a message')
    values=full[mapping.indices];old=cached[mapping.indices]
    order=np.argsort(-np.abs(values-old),kind='stable')
    candidates=[]
    for bits in PRECISIONS:
        frame=encode_frame(*metadata,values,bits)
        p=decode_frame(frame,version,state,mapping,cached,polytope)[-1]
        b=loss_bound(p,full,profiles)
        if b<=epsilon+1e-12:candidates.append((len(frame),b,frame,p,bits))
        if partial:
            mask=np.zeros(mapping.dimension,dtype=bool)
            for j in order[:-1]:
                mask[j]=True
                # Larger masks at this precision cannot improve payload size.
                size=29+int(mask.sum())*(bits//8)
                if candidates and size>min(c[0] for c in candidates):break
                frame=encode_frame(*metadata,values,bits,mask)
                p=decode_frame(frame,version,state,mapping,cached,polytope)[-1]
                b=loss_bound(p,full,profiles)
                if b<=epsilon+1e-12:
                    candidates.append((len(frame),b,frame,p,bits));break
    if not candidates:raise ArithmeticError('float64 full refresh failed certificate')
    _,b,frame,p,bits=min(candidates,key=lambda v:(v[0],v[1],v[4]))
    return p,b,frame,bits


def replay(data,full,family,horizons,representation,epsilon,partial=True):
    from .polytope import FeasiblePolytope
    sets=[family.feasible(q,tuple(horizons)).astype(float) for q in range(len(family.states))]
    polytopes=[FeasiblePolytope(y) for y in sets]
    if representation=='static':
        common=CoordinateMap.compile(family.static_profiles(len(horizons)))
        maps=[common]*len(sets)
    else: maps=[CoordinateMap.compile(y,representation) for y in sets]
    ref=np.asarray(full).reshape(-1,9).copy()
    for q in np.unique(data['q']):
        ix=data['q']==q;ref[ix]=polytopes[q].project(ref[ix])
    pred=np.zeros_like(ref);bounds=np.zeros(len(ref));sizes=np.zeros(len(ref),dtype=int)
    precisions=np.zeros(len(ref),dtype=int);cached=np.zeros(9)
    for i in range(len(ref)):
        q=int(data['q'][i]);poly=polytopes[q]
        if i==0 or data['segment'][i]!=data['segment'][i-1]:cached=np.zeros(9)
        cached=poly.project(cached)
        # Sequence covers every query, not only packets, so a receiver can
        # refuse stale packets. State ID guards against business desynchrony.
        meta=(int(data['t'][i])*10**9,int(data['entity'][i]),i,1,q)
        cached,b,frame,bits=select_message(cached,ref[i],sets[q],maps[q],poly,epsilon,meta,partial)
        pred[i]=cached;bounds[i]=b;sizes[i]=len(frame);precisions[i]=bits
    return dict(pred=pred.reshape(-1,3,3),full=ref.reshape(-1,3,3),certificate=bounds,
                bytes=sizes,sends=sizes>0,precision=precisions,
                maps=[dict(indices=m.indices,reconstruct=m.reconstruct) for m in maps])
