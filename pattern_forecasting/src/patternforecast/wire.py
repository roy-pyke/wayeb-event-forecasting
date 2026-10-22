"""Versioned sparse forecast frames with the payload sizes used in experiments."""
import struct
import numpy as np

HEADER=struct.Struct('!QIQI')  # timestamp ns, entity uint32, sequence uint64, model version
MASK=struct.Struct('!H')


def encode(timestamp_ns,entity,sequence,version,values,mask):
    mask=np.asarray(mask,dtype=bool).ravel();values=np.asarray(values,dtype=float).ravel()
    if len(mask)!=9 or len(values)!=9: raise ValueError('expected 9 forecast coordinates')
    if not np.isfinite(values).all() or ((values<0)|(values>1)).any(): raise ValueError('invalid probability')
    code=int(mask.astype(int)@(2**np.arange(9)))
    body=np.asarray(values[mask],dtype='>f4').tobytes()
    return HEADER.pack(int(timestamp_ns),int(entity),int(sequence),int(version))+MASK.pack(code)+body


def decode(packet,expected_version):
    if len(packet)<26: raise ValueError('truncated frame')
    timestamp,entity,seq,version=HEADER.unpack_from(packet)
    if version!=expected_version: raise ValueError('model version mismatch: certificate invalid')
    code=MASK.unpack_from(packet,24)[0]
    if code>=512: raise ValueError('unknown coordinate mask')
    mask=((code>>np.arange(9))&1).astype(bool)
    if len(packet)!=26+4*int(mask.sum()): raise ValueError('payload length mismatch')
    values=np.frombuffer(packet[26:],dtype='>f4').astype(np.float64)
    if not np.isfinite(values).all() or ((values<0)|(values>1)).any(): raise ValueError('invalid probability')
    return timestamp,entity,seq,mask,values


class Receiver:
    def __init__(self,version):
        self.version=version;self.cache={};self.sequence={}

    def accept(self,packet):
        timestamp,entity,seq,mask,values=decode(packet,self.version)
        if seq<=self.sequence.get(entity,-1): raise ValueError('out-of-order or duplicate frame')
        if entity not in self.cache and not mask.all(): raise ValueError('initial frame must refresh all coordinates')
        forecast=self.cache.get(entity,np.zeros(9)).copy();forecast[mask]=values
        self.cache[entity]=forecast;self.sequence[entity]=seq
        return timestamp,forecast.copy()

    def apply_possible(self,entity,possible):
        if entity not in self.cache: raise ValueError('uninitialized receiver')
        self.cache[entity]*=np.asarray(possible).ravel()
        return self.cache[entity].copy()
