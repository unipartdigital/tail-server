#!/usr/bin/python3

import math
import numpy as np
import numpy.linalg as lin

from dwarf import *
from numpy import dot


## Functions

def _sqrsum(a):
    return np.sum((a*a).T,0)

def _norm(a):
    return np.sqrt(_sqrsum(a))

def _dist(x,y):
    return _norm(x-y)

def woodoo(T):
    T41 = T[3] - T[0]
    T32 = T[2] - T[1]
    T54 = T[4] - T[3]
    T63 = T[5] - T[2]
    T51 = T[4] - T[0]
    T62 = T[5] - T[1]
    ToF = (T41*T63 - T32*T54) / (T51+T62)
    DoF = (ToF / DW1000_CLOCK_HZ) * Cabs
    return DoF

def hypercone(b0,bi,di):
    dim = len(b0)
    bi0 = bi - b0
    di0 = di.reshape(-1,1)
    Gb = np.block([bi0,di0])
    hb = (_sqrsum(bi)-_sqrsum(b0)-di*di)/2
    Gbb = dot(Gb.T,Gb)
    Gbh = dot(Gb.T,hb)
    X = lin.solve(Gbb,Gbh)
    return X[0:dim]

def hyperjump2D(b0,bs,bi,di,sigma,theta):
    bi0 = bi - b0
    bs0 = bs - b0
    ds0 = _norm(bs0)
    dis = _norm(bi - bs)
    di0 = di.reshape(-1,1)
    Gb = np.block([[bi0,di0],[bs0,-ds0],[bs[1],-bs[0],0]])
    hb = np.block([(_sqrsum(bi)-_sqrsum(b0)-di*di)/2, dot(bs0.T,b0), 0])
    Cv = ds0*theta
    Cc = ds0*theta*theta/2
    Pm = dis*sigma
    Ps = np.block([1/Pm,1/Cc,1/Cv])
    Gs = np.diag(Ps*Ps)
    Gbb = dot(dot(Gb.T,Gs),Gb)
    Gbh = dot(dot(Gb.T,Gs),hb)
    X = lin.solve(Gbb,Gbh)
    C = lin.cond(Gbb)
    return X[0:2],C

def hyperlater2D(ref_coord,coords,ranges,sigmas,delta=None,theta=0.045,maxiter=8):
    if len(ref_coord) != 2:
        raise ValueError('hyperlater2D only accepts 2D coordinsates')
    if len(coords) < 3:
        raise np.linalg.LinAlgError('Not enough inputs: {}'.format(len(coords)))
    B0 = np.array(ref_coord)
    B = np.array(coords)
    R = np.array(ranges)
    S = np.array(sigmas)
    X = hypercone(B0,B,R)
    Y,C = hyperjump2D(B0,X,B,R,S,theta)
    if delta is None:
        delta = np.amin(S) / 2
    N = 1
    while N < maxiter and _dist(X,Y) > delta:
        X = Y
        N = N + 1
        Y,C = hyperjump2D(B0,X,B,R,S,theta)
    X = np.array((Y[0],Y[1],0))
    return X,C


def hyperjump3D(b0,bs,bi,di,sigma,theta):
    bi0 = bi - b0
    bs0 = bs - b0
    ds0 = _norm(bs0)
    dis = _norm(bi - bs)
    di0 = di.reshape(-1,1)
    Gb = np.block([[bi0,di0],[bs0,-ds0],[bs[1],-bs[0],0,0],[bs[2],0,-bs[0],0]])
    hb = np.block([(_sqrsum(bi)-_sqrsum(b0)-di*di)/2, dot(bs0.T,b0), 0, 0])
    Cv = ds0*theta
    Cc = ds0*theta*theta/2
    Pm = dis*sigma
    Ps = np.block([1/Pm,1/Cc,1/Cv,1/Cv])
    Gs = np.diag(Ps*Ps)
    Gbb = dot(dot(Gb.T,Gs),Gb)
    Gbh = dot(dot(Gb.T,Gs),hb)
    X = lin.solve(Gbb,Gbh)
    C = lin.cond(Gbb)
    return X[0:3],C

def hyperlater3D(ref_coord,coords,ranges,sigmas,delta=None,theta=0.045,maxiter=8):
    if len(ref_coord) != 3:
        raise ValueError('hyperlater3D only accepts 3D coordinsates')
    if len(coords) < 4:
        raise np.linalg.LinAlgError('Not enough inputs: {}'.format(len(coords)))
    B0 = np.array(ref_coord)
    B = np.array(coords)
    R = np.array(ranges)
    S = np.array(sigmas)
    X = hypercone(B0,B,R)
    Y,C = hyperjump3D(B0,X,B,R,S,theta)
    if delta is None:
        delta = np.amin(S) / 2
    N = 1
    while N < maxiter and _dist(X,Y) > delta:
        X = Y
        N = N + 1
        Y,C = hyperjump3D(B0,X,B,R,S,theta)
    return Y,C


def hyperjump3Dp(b0,bs,bi,di,sigma,theta):
    bi_xy = bi[:,0:2]
    bi_z = bi[:,2]
    b0_xy = b0[0:2]
    b0_z = b0[2]
    bs_xy = bs[0:2]
    bs_z = bs[2]
    bi0_xy = bi_xy - b0_xy
    bi0_z = bi_z - b0_z 
    bs0 = bs - b0
    bs0_xy = bs_xy - b0_xy
    # ci0_z = bi_z*bi_z - b0_z*b0_z -2*bs_z*bi0_z
    #       = (bi_z - b0_z)(bi_z + b0_z) - 2bs_z*bi0_z
    #       = (bi_z - b0_z)(bi_z + b0_z - 2bs_z)
    #       = (bi_z - b0_z)((bi_z - bs_z) + (b0_z - bs_z))
    ci0_z = bi0_z * ((bi_z - bs_z) + (b0_z - bs_z))
    ds0 = _norm(bs0)
    dis = _norm(bi - bs)
    di0 = di.reshape(-1,1)
    Gb = np.block([[bi0_xy,di0],[bs0_xy,-ds0],[bs[1],-bs[0],0]])
    hb = np.block([(_sqrsum(bi_xy)-_sqrsum(b0_xy)-di*di+ci0_z)/2, dot(bs0_xy.T,b0_xy), 0])
    Cv = ds0*theta
    Cc = ds0*theta*theta/2
    Pm = dis*sigma
    Ps = np.block([1/Pm,1/Cc,1/Cv])
    Gs = np.diag(Ps*Ps)
    Gbb = dot(dot(Gb.T,Gs),Gb)
    Gbh = dot(dot(Gb.T,Gs),hb)
    X = lin.solve(Gbb,Gbh)
    C = lin.cond(Gbb)
    R = np.array((X[0],X[1],bs[2]))
    return R,C


def hyperlater3Dp(ref_coord,coords,ranges,sigmas,delta=None,theta=0.045,maxiter=8,z_est=0.0):
    if len(ref_coord) != 3:
        raise ValueError('hyperlater_pseudo3D only accepts 3D coordinsates')
    if len(coords) < 4:
        raise np.linalg.LinAlgError('Not enough inputs: {}'.format(len(coords)))
    B0 = np.array(ref_coord)
    B = np.array(coords)
    R = np.array(ranges)
    S = np.array(sigmas)
    X = hypercone(B0[0:2],B[:,0:2],R)
    X = np.array((X[0],X[1],z_est))
    Y,C = hyperjump3Dp(B0,X,B,R,S,theta)
    if delta is None:
        delta = np.amin(S) / 2
    N = 1
    while N < maxiter and _dist(X,Y) > delta:
        X = Y
        N = N + 1
        Y,C = hyperjump3Dp(B0,X,B,R,S,theta)
    return Y,C

