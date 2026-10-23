"""Shared paths, assumptions and model functions."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / 'weather'                 # riyadh.epw, jeddah.epw, riyadh.ddy, jeddah.ddy
IDF = ROOT / 'idf'
METERS = ROOT / 'data' / 'energyplus_meters'
PV = ROOT / 'data' / 'pv'
RESULTS = ROOT / 'data' / 'results'
FIGURES = ROOT / 'figures'
CITIES = ['riyadh', 'jeddah']

# ---------------- economic and technical assumptions ----------------
P_IMP = 0.32                    # SAR/kWh, governmental import tariff
PV_KWP = 150                    # kWp
FLOOR = 4982                    # m2, prototype floor area
AREA = PV_KWP / 0.21            # module area, m2 (~714)
L_MAX = 0.60                    # maximum soiling loss
RAIN_CLEAN = 3.0                # mm/day that cleans the modules
RATE = {'riyadh': 0.0025, 'jeddah': 0.0035}          # base soiling rate, fraction/day
RATE_LOW = {'riyadh': 0.0010, 'jeddah': 0.0015}
RATE_HIGH = {'riyadh': 0.0050, 'jeddah': 0.0060}
COST_M2 = {'low': 0.11, 'base': 0.375, 'high': 1.1, 'stress': 3.1}   # SAR/m2 per cleaning
EXPORT = {'5 halala': 0.05, 'zero': 0.0}
GRID_N = [7, 10, 14, 21, 30, 45, 60, 90, 120, 180]
GRID_TH = [0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
GRID_H = [7, 14, 21, 30, 45, 60, 90]
B_E, B_P, ETA = 100.0, 50.0, 0.95          # battery kWh, kW, one-way efficiency
SOC_MIN, SOC_MAX = 0.1 * B_E, 0.9 * B_E

# ---------------- calendar (2026, Saudi working week) ----------------
DAYS = pd.date_range('2026-01-01', periods=365, freq='D')
EID = DAYS.isin(pd.date_range('2026-03-19', periods=7).append(pd.date_range('2026-05-25', periods=7)))
SUMMER = DAYS.isin(pd.date_range('2026-06-14', periods=70))
FRI, SAT = DAYS.dayofweek == 4, DAYS.dayofweek == 5
ALLOWED = ~(FRI | EID)                     # no cleaning on Fridays or Eid
PRESEM = int(np.where(DAYS == pd.Timestamp('2026-08-16'))[0][0])
SCEN = {'office-like': ('office_{}Meter.csv', False),
        'university': ('office_{}_sbMeter.csv', True)}


def read_meter(path):
    m = pd.read_csv(path)
    col = [c for c in m.columns if 'Electricity:Facility' in c][0]
    return (m[col].values / 3.6e6).reshape(365, 24)          # J -> kWh per hour


def value(pv, load, p_exp):
    s = np.minimum(pv, load)
    return P_IMP * s + p_exp * (pv - s)


def simulate(pv, load, rain, rates, decide, p_exp, storms=None):
    """Daily soiling/cleaning loop. rates: scalar or array(365). Returns energy and value."""
    rates = np.broadcast_to(np.asarray(rates, dtype=float), (365,))
    L, Ls, cdays = 0.0, np.zeros(365), []
    for d in range(365):
        if ALLOWED[d] and decide(d, L):
            L = 0.0; cdays.append(d)
        Ls[d] = L
        L = min(L + rates[d] + (storms[d] if storms is not None else 0.0), L_MAX)
        if rain[d] >= RAIN_CLEAN:
            L = 0.0
    pvs = pv * (1 - Ls[:, None]); s = np.minimum(pvs, load)
    return dict(n=len(cdays), summer_n=int(SUMMER[cdays].sum()) if cdays else 0,
                pv_MWh=pvs.sum() / 1000, self_MWh=s.sum() / 1000, export_MWh=(pvs - s).sum() / 1000,
                value=value(pvs, load, p_exp).sum(), mean_loss_pct=Ls.mean() * 100, Ls=Ls)


def fixed(N):
    st = {'due': N}
    def f(d, L):
        if d >= st['due']:
            st['due'] = d + N; return True
        return False
    return f


def fixed_summer_skip(N):
    """Calendar heuristic: fixed interval, no cleaning in the summer break except once before the semester."""
    st = {'due': N, 'pre': False}
    def f(d, L):
        if SUMMER[d]:
            if d >= PRESEM and not st['pre']:
                st['pre'] = True; st['due'] = d + N; return True
            return False
        if d >= st['due']:
            st['due'] = d + N; return True
        return False
    return f


def threshold(th):
    return lambda d, L: L >= th


def predictive(H, p_assumed, fc, rate, C):
    """Clean today if the forecast value recovered over H days exceeds the cleaning cost C.
    p_assumed = P_IMP gives the energy-only rule; p_assumed = export price gives the SC-aware rule."""
    def f(d, L):
        if d == 0:
            return False
        n = min(H, 365 - d); P, Lh = fc(d, n); k = np.arange(n)
        Lc = np.minimum(rate * k, L_MAX)[:, None]
        Ld = np.minimum(L + rate * k, L_MAX)[:, None]
        return (value(P * (1 - Lc), Lh, p_assumed) - value(P * (1 - Ld), Lh, p_assumed)).sum() >= C
    return f


def batt_value(pvs, load, pe):
    """Greedy self-consumption battery dispatch; returns annual value (SAR)."""
    soc, self_e, exp_e = SOC_MIN, 0.0, 0.0
    for p, l in zip(pvs.ravel(), load.ravel()):
        if p >= l:
            ch = min(p - l, B_P, (SOC_MAX - soc) / ETA)
            soc += ch * ETA; self_e += l; exp_e += p - l - ch
        else:
            dis = min(l - p, B_P, (soc - SOC_MIN) * ETA)
            soc -= dis / ETA; self_e += p + dis
    return P_IMP * self_e + pe * exp_e


def load_case(city, scen='university', load_mult=1.0, summer_occ=0.0):
    """Returns pv, load, rain (daily), realistic forecaster and perfect forecaster."""
    df = pd.read_csv(PV / f'{city}_base.csv', index_col=0, parse_dates=True)
    pv = df.pv_kwh.values.reshape(365, 24)
    rain = df.rain_mm.values.reshape(365, 24).sum(axis=1)
    meter, has_sb = SCEN[scen]
    load = read_meter(METERS / meter.format(city)) * load_mult
    if summer_occ > 0:
        office = read_meter(METERS / SCEN['office-like'][0].format(city)) * load_mult
        load[SUMMER] = summer_occ * office[SUMMER] + (1 - summer_occ) * load[SUMMER]
        dt = np.where(EID | SAT, 2, np.where(FRI, 1, np.where(SUMMER, 3, 0)))
    else:
        off = EID | SAT | (SUMMER if has_sb else False)
        dt = np.where(off, 2, np.where(FRI, 1, 0))
    pvhat = np.array([pv[max(0, d - 7):d].mean(0) if d > 0 else pv[0] for d in range(365)])
    ntype = int(dt.max()) + 1
    lp = np.zeros((365, ntype, 24))
    for d in range(1, 365):
        for t in range(ntype):
            ix = np.where(dt[:d] == t)[0][-3:]
            if len(ix) == 0:
                ix = np.arange(max(0, d - 3), d)
            lp[d, t] = load[ix].mean(0)
    fc_real = lambda d, n: (np.tile(pvhat[d], (n, 1)), lp[d][dt[d:d + n]])
    fc_perf = lambda d, n: (pv[d:d + n], load[d:d + n])
    return pv, load, rain, fc_real, fc_perf
