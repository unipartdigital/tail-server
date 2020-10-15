#!/usr/bin/python3
#
# dwarf.py	Decawave and RF support library
#

import os
import sys
import math

import numpy as np


Cabs = 299792458
Cair = 299705000

LIGHT_SPEED = Cabs

DW1000_CLOCK_GHZ = 63.8976
DW1000_CLOCK_HZ  = DW1000_CLOCK_GHZ * 1E9
DW1000_CLOCK = DW1000_CLOCK_HZ

DW1000_64PRF_ANTD_NS = 514.4620
DW1000_16PRF_ANTD_NS = 513.9067

DW1000_64PRF_ANTD_DEFAULT = int(DW1000_64PRF_ANTD_NS * DW1000_CLOCK_GHZ / 2)
DW1000_16PRF_ANTD_DEFAULT = int(DW1000_16PRF_ANTD_NS * DW1000_CLOCK_GHZ / 2)


##
## Splines for RF compensation
##

DW1000_TIME_COMP_SPLINE = {
    500: {
        16: (
             ((-95.0, -89.0), (476.22643132772447, 10.498752594720335, 0.05540904375134925)),
             ((-89.0, -81.0), (654.0804983431934, 14.49547277977005, 0.0778625255433889)),
             ((-81.0, -75.0), (-229.16303620413078, -7.313007847954822, -0.05675771465178503)),
             ((-75.0, -69.0), (-24.46102846149239, -1.8542881911147218, -0.02036625396249292)),
             ((-69.0, -61.0), (-78.59161148160769, -3.4232911289774517, -0.03173584431482546)),
        ),
        64: (
             ((-105.0, -91.0), (61.439812150901005, 1.3418106477809877, 0.005982995146544212)),
             ((-91.0, -81.0),  (191.34215768288774, 4.196806610428823, 0.021669782617599553)),
             ((-81.0, -75.0),  (440.94876334122876, 10.359931569763607, 0.05971375699301895)),
             ((-75.0, -67.0),  (-253.70626375667266, -8.164201085409243, -0.06378045129332577)),
             ((-67.0, -55.0),  (-19.17301348586056, -1.1632092684998827, -0.011534249189049994)),
        ),
    },
    900: {
        16: (
             ((-95.0, -89.0), (195.74173780744627, 3.8534533540981126, 0.014271244395981597)),
             ((-89.0, -81.0), (969.389649037234, 21.23879931204284, 0.11194172524583035)),
             ((-81.0, -75.0), (-84.85331251197003, -4.791890579990105, -0.04874154242191908)),
             ((-75.0, -69.0), (51.089929314753064, -1.1667373171059765, -0.024573852989647094)),
             ((-69.0, -61.0), (-102.03262134917657, -5.6050717524128135, -0.056735694081496035)),
        ),
        64: (
             ((-105.0, -93.0), (218.7397242426187, 4.198261039857095, 0.016587764244901493)),
             ((-93.0, -83.0),  (147.69729139335806, 2.6704676069778817, 0.008373825485012976)),
             ((-83.0, -75.0),  (751.6574783072042, 17.223724348174265, 0.09604404210335793)),
             ((-75.0, -69.0),  (66.43800638064444, -1.048794001702141, -0.025772740804228533)),
             ((-69.0, -63.0),  (-159.7241124813689, -7.60421788039967, -0.07327581340592948)),
             ((-63.0, -55.0),  (4.065332228624562, -2.4045534451922137, -0.03200863918904773)),
        ),
    },
}

DW1000_DIST_COMP_SPLINE = {
    500: {
        16: (
             ((-95.0, -89.0), (446.8684032336355, 9.85153384886164, 0.051993231112440697)),
             ((-89.0, -81.0), (613.7582642483305, 13.601867408226155, 0.07306251852571943)),
             ((-81.0, -75.0), (-215.03577569855327, -6.862181359273789, -0.05325876022234244)),
             ((-75.0, -69.0), (-22.953074443104942, -1.7399765082089482, -0.019110731344085252)),
             ((-69.0, -61.0), (-73.74665835415497, -3.2122548014502623, -0.02977941823744068)),
        ),
        64: (
             ((-105.0, -91.0), (57.65221950050323, 1.2590917726764277, 0.005614160222583764)),
             ((-91.0, -81.0), (179.546448601439, 3.938085216005312, 0.020333901101963092)),
             ((-81.0, -75.0), (413.76550485191035, 9.72127075198824, 0.056032570817557636)),
             ((-75.0, -67.0), (-238.06598188855017, -7.660900913339757, -0.05984856478355027)),
             ((-67.0, -55.0), (-17.991050806895178, -1.091500669108013, -0.010823194973080152)),
        ),
    },
    900: {
        16: (
             ((-95.0, -89.0), (183.67480691132866, 3.6158987280067723, 0.013391462077503746)),
             ((-89.0, -81.0), (909.6294873191769, 19.92948671225841, 0.10504083084258342)),
             ((-81.0, -75.0), (-79.62234302197686, -4.496483922533177, -0.0457367625993812)),
             ((-75.0, -69.0), (47.94037800579669, -1.094811223380935, -0.023058943654632458)),
             ((-69.0, -61.0), (-95.74259549796217, -5.259534749105479, -0.05323809715869743)),
        ),
        64: (
             ((-105.0, -93.0), (205.2550317787694, 3.9394499839253396, 0.01556517495401355)),
             ((-93.0, -83.0), (138.59216629969663, 2.505840744895793, 0.007857602554773635)),
             ((-83.0, -75.0), (705.3198961957823, 16.161929894874312, 0.09012319542025327)),
             ((-75.0, -69.0), (62.34228902955281, -0.9841387836348634, -0.024183923387127493)),
             ((-69.0, -63.0), (-149.87756749129332, -7.135439107361107, -0.06875856436833949)),
             ((-63.0, -55.0), (3.8147158622732773, -2.2563194477618973, -0.030035396070342557)),
        ),
    },
}

DW1000_RX_LEVEL_SPLINE = {
    16: (
        ((-40.0,14.4),(0.0031078824982508266,0.9946676633232663,0.0009046309413235365)),
        ((14.4,16.7),(32.90020098562278,-3.5753769831047637,0.15961952375075705)),
        ((16.7,19.375),(78.28690272560803,-9.011495790881899,0.32239527802153234)),
        ((19.375,26.6),(-48.67100367625461,4.094594808374672,-0.015839400502056122)),
    ),
    64: (
        ((-40.0,14.45),(0.10914877594166128,0.9337929031481064,0.005682419820392526)),
        ((14.45,22.45),(1.5410781009601724,0.72322284247101,0.013412421608872349)),
        ((22.45,24.375),(344.1982254294007,-29.807657288333957,0.6934898000860408)),
        ((24.375,28.85),(957.3183685061152,-80.11393828848666,1.7253933194935)),
    ),
    0: ( ## Open space - not good for our purpose
        ((-40.0,14.4),(-0.07534208194016515,1.0408146870743074,-0.0028066414817764507)),
        ((14.4,22.2),(10.994260775936054,-0.48144640981648307,0.04952307438016412)),
        ((22.2,31.5),(25.872634971567088,-1.8264156614997213,0.07992117150419104)),
    ),
}

DW1000_RX_BASE_LEVEL = {
    16: 113.77,
    64: 121.74,
}


##
## Simple spline support
##

def GenTailSpline(X,Y,borders,ranges,W0=1000,W1=1000):
    NC = 3      # Order, hardcoded
    NR = len(ranges)
    NL = NR*NC
    GX = np.empty((0,NL))
    GY = np.empty((0,1))
    I = 0
    for R in ranges:
        L = np.zeros((1,NL))
        D = np.zeros((1,1))
        for i in range(R[0],R[1]):
            x,y = X[i],Y[i]
            D[0,0] = Y[i]
            L[0,I+0] = 1
            L[0,I+1] = X[i]
            L[0,I+2] = X[i]*X[i]
            GX = np.vstack((GX,L))
            GY = np.vstack((GY,D))
        I += NC
    for j in range(NR-1):
        L = np.zeros((1,NL))
        D = np.zeros((1,1))
        I = j*NC
        x = X[borders[j+1]]
        L[0,I+0] = W0
        L[0,I+1] = W0*x
        L[0,I+2] = W0*x*x
        L[0,I+3] = -W0
        L[0,I+4] = -W0*x
        L[0,I+5] = -W0*x*x
        GX = np.vstack((GX,L))
        GY = np.vstack((GY,D))
    for j in range(NR-1):
        L = np.zeros((1,NL))
        D = np.zeros((1,1))
        I = j*NC
        x = X[borders[j+1]]
        L[0,I+1] = W0
        L[0,I+2] = W0*2*x
        L[0,I+4] = -W0
        L[0,I+5] = -W0*2*x
        GX = np.vstack((GX,L))
        GY = np.vstack((GY,D))
    (SP,_,_,_) = lin.lstsq(GX,GY,rcond=None)
    SPL = [[[X[borders[j]],X[borders[j+1]]], [SP[j*NC+i][0] for i in range(NC)]] for j in range(NR)]
    return SPL


def TailSpline(spline,X):
    for S in spline:
        if S[0][0] < X <= S[0][1]:
            return (S[1][0] + S[1][1]*X + S[1][2]*X*X)
    raise ValueError('Spline X value {} out of range'.format(X))


##
## Decawave power conversion
##

def RxdBu2Power(dBu, prf=64):
    power = math.pow(10, (dBu + DW1000_RX_BASE_LEVEL[prf])/10)
    return power

def RxPower2dBu(power, prf=64):
    dBu = 10*math.log10(power) - DW1000_RX_BASE_LEVEL[prf]
    return dBu

def RxPower2dBm(power, prf=64):
    dBu = RxPower2dBu(power,prf)
    dBm = TailSpline(DW1000_RX_LEVEL_SPLINE[prf], dBu + 105) - 105
    return dBm


##
## Time / distance compensation
##

def dBm2TimeComp(dBm, ch=5, prf=64):
    if ch in (4,7):
        bw = 900
    else:
        bw = 500
    clocks = TailSpline(DW1000_TIME_COMP_SPLINE[bw][prf],dBm)
    return clocks

def dBm2DistComp(dBm, ch=5, prf=64):
    if ch in (4,7):
        bw = 900
    else:
        bw = 500
    dist = TailSpline(DW1000_DIST_COMP_SPLINE[bw][prf],dBm)
    return dist


##
## RF propagation model
##

_UWB_CC = 4*math.pi/Cabs

_UWB_CH = ( None, 3494.4, 3993.6, 4492.8, 3993.6, 6489.6, None, 6489.6 )

def RFDist2Attn(m,MHz):
    return 20*np.log10(m*_UWB_CC*MHz*1e6)

def RFAttn2Dist(dBm,MHz):
    return (10**(dBm/20))/(_UWB_CC*MHz*1e6)

def RFCalcTxPower(ch,dist,rxlevel):
    return rxlevel + RFDist2Attn(dist,_UWB_CH[ch])

def RFCalcRxPower(ch,dist,txlevel):
    return txlevel - RFDist2Attn(dist,_UWB_CH[ch])

def RFCalcDist(ch,txlevel,rxlevel):
    return RFAttn2Dist(txlevel-rxlevel, _UWB_CH[ch])



##
## DW1000 attributes
##

DW1000_SYSFS = '/sys/devices/platform/soc/3f204000.spi/spi_master/spi0/spi0.0/dw1000/'

def SetDWAttr(attr, data):
    if os.path.isfile(DW1000_SYSFS + attr):
        with open(DW1000_SYSFS + attr, 'w') as f:
            f.write(str(data))

def GetDWAttr(attr):
    if os.path.isfile(DW1000_SYSFS + attr):
        with open(DW1000_SYSFS + attr, 'r') as f:
            value = f.read()
        return value.rstrip()
    return None


DW1000_STATS_ATTRS = (
    'dw1000_rx_error',
    'dw1000_rx_fcg',
    'dw1000_rx_frame',
    'dw1000_rx_ovrr',
    'dw1000_rx_ldedone',
    'dw1000_rx_kpi_error',
    'dw1000_rx_stamp_error',
    'dw1000_rx_frame_rep',
    'dw1000_rx_reset',
    'dw1000_tx_error',
    'dw1000_rx_dfr',
    'dw1000_rx_hsrbp',
    'dw1000_rx_resync',
    'dw1000_tx_frame',
    'dw1000_tx_retry',
    'dw1000_spi_error',
    'dw1000_snr_reject',
    'dw1000_fpr_reject',
    'dw1000_noise_reject',
    'dw1000_irq_count',
    'dw1000_hard_reset',
)

DW1000_STATS_SYSFS = '/sys/devices/platform/soc/3f204000.spi/spi_master/spi0/spi0.0/statistics/'

def GetDWStats(attr):
    if os.path.isfile(DW1000_STATS_SYSFS + attr):
        with open(DW1000_STATS_SYSFS + attr, 'r') as f:
            value = f.read()
        return value.rstrip()
    return None


DW1000_SYSDT = '/sys/devices/platform/soc/3f204000.spi/spi_master/spi0/spi0.0/of_node/'

def GetDTAttrRaw(attr):
    if os.path.isfile(DW1000_SYSDT + attr):
        with open(DW1000_SYSDT + attr, 'rb') as f:
            data = f.read()
        return data
    return None

def GetDTAttrStr(attr):
    if os.path.isfile(DW1000_SYSDT + attr):
        with open(DW1000_SYSDT + attr, 'r') as f:
            data = f.read()
        return data.rstrip('\n\r\0')
    return None

def GetDTAttr(attr, form):
    if os.path.isfile(DW1000_SYSDT + attr):
        with open(DW1000_SYSDT + attr, 'rb') as f:
            data = f.read()
        return struct.unpack(form, data)
    return []



