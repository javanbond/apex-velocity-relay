"""Shared bounds and validation for direct and online race transports."""
import math
from handling import NEUTRAL

PROTOCOL=1
TRACK_ID='harbor-gp-1735-v2'
MAX_FRAME=32768


def valid_controls(value):
    if not isinstance(value,dict) or set(value)!=set(NEUTRAL): return None
    if type(value['steer']) is not int or value['steer'] not in (-1,0,1): return None
    if any(type(value[k]) is not bool for k in NEUTRAL if k!='steer'): return None
    return value.copy()


def valid_snapshot(value):
    if not isinstance(value,dict) or type(value.get('state')) is not int or value.get('state') not in (0,1,2) or type(value.get('epoch')) is not int: return False
    if not isinstance(value.get('cars'),list) or len(value['cars'])!=4: return False
    def finite(x,limit): return type(x) in (int,float) and math.isfinite(x) and abs(x)<=limit
    if not all(finite(value.get(k),1000000) for k in ('elapsed','countdown')): return False
    for c in value['cars']:
        if not isinstance(c,dict): return False
        if type(c.get('lap')) is not int or not 1<=c['lap']<=4: return False
        if not isinstance(c.get('p'),list) or len(c['p'])!=3 or not all(finite(x,10000) for x in c['p']): return False
        if not all(finite(c.get(k),1000000) for k in ('yaw','speed','steer','slip','nitro','distance','lap_time','best','score','combo','lap')): return False
        if c.get('finish') is not None and not finite(c['finish'],1000000): return False
        if 'finish' not in c: return False
        if not all(type(c.get(k)) is bool for k in ('drifting','boosting','wrong')): return False
    return True

