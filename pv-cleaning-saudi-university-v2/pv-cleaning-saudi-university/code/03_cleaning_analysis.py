"""Step 3: main results, sensitivity and battery case (deterministic base year).

Output: data/results/results_main.csv, sensitivity.csv, results_battery.csv, trajectories.csv
"""
import time
import numpy as np
import pandas as pd
from common import (RESULTS, CITIES, SCEN, DAYS, AREA, FLOOR, P_IMP, RATE, RATE_LOW, RATE_HIGH, COST_M2,
                    EXPORT, GRID_N, GRID_TH, GRID_H, simulate, fixed, threshold, predictive, batt_value,
                    load_case)

ORDER = ['Fixed interval', 'Soiling threshold', 'Predictive energy-only',
         'Predictive SC-aware', 'SC-aware perfect fcst']


def strategies(fcr, fcp, pe, rate, C, perfect=True):
    S = {'Fixed interval': [(N, lambda N=N: fixed(N)) for N in GRID_N],
         'Soiling threshold': [(th, lambda th=th: threshold(th)) for th in GRID_TH],
         'Predictive energy-only': [(H, lambda H=H: predictive(H, P_IMP, fcr, rate, C)) for H in GRID_H],
         'Predictive SC-aware': [(H, lambda H=H: predictive(H, pe, fcr, rate, C)) for H in GRID_H]}
    if perfect:
        S['SC-aware perfect fcst'] = [(H, lambda H=H: predictive(H, pe, fcp, rate, C)) for H in GRID_H]
    return S


def best_runs(pv, load, rain, rate, pe, C, S, batt=False):
    nc = simulate(pv, load, rain, rate, lambda d, L: False, pe)
    v0 = batt_value(pv * (1 - nc['Ls'][:, None]), load, pe) if batt else nc['value']
    out = {}
    for s, cands in S.items():
        best = None
        for par, make in cands:
            r = simulate(pv, load, rain, rate, make(), pe)
            if batt:
                r['value'] = batt_value(pv * (1 - r['Ls'][:, None]), load, pe)
            r['net'] = r['value'] - r['n'] * C
            if best is None or r['net'] > best['net']:
                best = dict(r, param=par)
        best['gain'] = best['net'] - v0
        out[s] = best
    return out


def to_rows(out, **keys):
    f = out['Fixed interval']['gain']
    return [dict(**keys, strategy=s, param=b['param'], n=b['n'], summer_n=b['summer_n'],
                 pv_MWh=round(b['pv_MWh'], 1), self_MWh=round(b['self_MWh'], 1),
                 export_MWh=round(b['export_MWh'], 1), mean_loss_pct=round(b['mean_loss_pct'], 2),
                 gain=round(b['gain']), vs_fixed_pct=round((b['gain'] / f - 1) * 100, 1))
            for s, b in out.items()]


def main():
    t0 = time.time()
    RESULTS.mkdir(parents=True, exist_ok=True)
    # 1) main results
    rows, traj = [], {}
    for scen in SCEN:
        for city in CITIES:
            pv, load, rain, fcr, fcp = load_case(city, scen)
            print(f'{scen:11s} {city}: load {load.sum() / 1000:.0f} MWh, EUI {load.sum() / FLOOR:.0f} kWh/m2, '
                  f'self-consumption {np.minimum(pv, load).sum() / pv.sum() * 100:.0f}%')
            for ename, pe in EXPORT.items():
                for cname, cm2 in COST_M2.items():
                    C = cm2 * AREA
                    out = best_runs(pv, load, rain, RATE[city], pe, C, strategies(fcr, fcp, pe, RATE[city], C))
                    rows += to_rows(out, scenario=scen, city=city, export=ename, cost=cname)
                    if scen == 'university' and ename == 'zero' and cname == 'base':
                        for s in ['Fixed interval', 'Predictive SC-aware']:
                            traj[f'{city}_{s}'] = out[s]['Ls']
    main_df = pd.DataFrame(rows)
    main_df.to_csv(RESULTS / 'results_main.csv', index=False)
    pd.DataFrame(traj, index=DAYS).to_csv(RESULTS / 'trajectories.csv')
    print(f'main done ({time.time() - t0:.0f}s)')

    # 2) sensitivity (university calendar)
    cases = {'base': (RATE, 1.0), 'soiling low': (RATE_LOW, 1.0), 'soiling high': (RATE_HIGH, 1.0),
             'load -20%': (RATE, 0.8), 'load +20%': (RATE, 1.2), 'load +40%': (RATE, 1.4), 'load +60%': (RATE, 1.6)}
    srows = []
    for case, (rt, lm) in cases.items():
        for city in CITIES:
            pv, load, rain, fcr, fcp = load_case(city, 'university', lm)
            for ename, pe in EXPORT.items():
                for cname in ['base', 'high']:
                    C = COST_M2[cname] * AREA
                    out = best_runs(pv, load, rain, rt[city], pe, C,
                                    strategies(fcr, fcp, pe, rt[city], C, perfect=False))
                    srows += to_rows(out, case=case, city=city, export=ename, cost=cname,
                                     EUI=round(load.sum() / FLOOR))
    pd.DataFrame(srows).to_csv(RESULTS / 'sensitivity.csv', index=False)
    print(f'sensitivity done ({time.time() - t0:.0f}s)')

    # 3) battery
    brows = []
    for scen in SCEN:
        for city in CITIES:
            pv, load, rain, fcr, fcp = load_case(city, scen)
            for ename, pe in EXPORT.items():
                for cname in ['base', 'high']:
                    C = COST_M2[cname] * AREA
                    out = best_runs(pv, load, rain, RATE[city], pe, C,
                                    strategies(fcr, fcp, pe, RATE[city], C, perfect=False), batt=True)
                    brows += to_rows(out, scenario=scen, city=city, export=ename, cost=cname)
    pd.DataFrame(brows).to_csv(RESULTS / 'results_battery.csv', index=False)
    print(f'battery done ({time.time() - t0:.0f}s)')

    v = main_df[(main_df.strategy == 'Fixed interval') & (main_df.cost == 'base')]
    print('\nValue of cleaning, best fixed schedule, base cost (SAR/yr):')
    print(v.pivot_table(index='city', columns=['scenario', 'export'], values='gain'))
    u = main_df[(main_df.scenario == 'university') & (main_df.export == 'zero')]
    print('\nUniversity, zero export: % vs best fixed')
    print(u.pivot_table(index=['city', 'strategy'], columns='cost', values='vs_fixed_pct')
          [['low', 'base', 'high', 'stress']])


if __name__ == '__main__':
    main()
