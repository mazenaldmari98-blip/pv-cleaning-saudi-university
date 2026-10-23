"""Step 4: robustness tests (university calendar).

A) decomposition of calendar and export effects (from results_main.csv)
B) calendar heuristic 'Fixed + summer skip'
C) summer occupancy 0% (base) and 50%
D) out-of-sample Monte Carlo: parameters tuned on the deterministic base year are evaluated on
   100 synthetic soiling years (seasonal factors, lognormal noise, dust storms)
Output: data/results/robust_*.csv
"""
import time
import numpy as np
import pandas as pd
from common import (RESULTS, CITIES, DAYS, AREA, P_IMP, RATE, COST_M2, EXPORT, GRID_N, GRID_TH, GRID_H,
                    simulate, fixed, fixed_summer_skip, threshold, predictive, load_case)

COSTS = {k: COST_M2[k] for k in ['base', 'high']}
N_MC = 100
# synthetic soiling assumptions (stated in the paper)
SEASON = {'riyadh': [0.6, 0.9, 1.6, 2.0, 1.6, 1.0, 0.6, 0.6, 0.7, 0.8, 0.7, 0.6],
          'jeddah': [0.8, 0.9, 1.2, 1.3, 1.1, 1.0, 0.9, 0.9, 1.0, 1.4, 0.8, 0.7]}
STORMS = {'riyadh': dict(rate=4, months=[3, 4, 5, 6], step=(0.10, 0.20)),
          'jeddah': dict(rate=3, months=[3, 4, 5, 10], step=(0.15, 0.30))}
NOISE_SIGMA = 0.5


def makers(fc, pe, rate, C):
    return {'Fixed interval': [(N, lambda N=N: fixed(N)) for N in GRID_N],
            'Fixed + summer skip': [(N, lambda N=N: fixed_summer_skip(N)) for N in GRID_N],
            'Soiling threshold': [(th, lambda th=th: threshold(th)) for th in GRID_TH],
            'Predictive energy-only': [(H, lambda H=H: predictive(H, P_IMP, fc, rate, C)) for H in GRID_H],
            'Predictive SC-aware': [(H, lambda H=H: predictive(H, pe, fc, rate, C)) for H in GRID_H]}


def tune(pv, load, rain, rate, pe, C, fc):
    v0 = simulate(pv, load, rain, rate, lambda d, L: False, pe)['value']
    best = {}
    for s, cands in makers(fc, pe, rate, C).items():
        b = None
        for par, make in cands:
            r = simulate(pv, load, rain, rate, make(), pe)
            g = r['value'] - r['n'] * C - v0
            if b is None or g > b[2]['gain']:
                b = (par, make, dict(r, gain=g))
        best[s] = b
    return best


def synth_year(city, rng):
    r = RATE[city] * np.array([SEASON[city][m - 1] for m in DAYS.month])
    r = r / r.mean() * RATE[city]
    r = r * rng.lognormal(-NOISE_SIGMA ** 2 / 2, NOISE_SIGMA, 365)
    st = np.zeros(365)
    cfg = STORMS[city]
    elig = np.where(DAYS.month.isin(cfg['months']))[0]
    for d in rng.choice(elig, size=rng.poisson(cfg['rate']), replace=False):
        st[d] = rng.uniform(*cfg['step'])
    return r, st


def main():
    t0 = time.time()
    # A) decomposition
    m = pd.read_csv(RESULTS / 'results_main.csv')
    fx = m[(m.strategy == 'Fixed interval') & (m.cost == 'base')].set_index(['scenario', 'export', 'city'])['gain']
    dec = pd.DataFrame([dict(city=c,
                             export_effect_office_pct=round((fx['office-like', 'zero', c] / fx['office-like', '5 halala', c] - 1) * 100, 1),
                             export_effect_univ_pct=round((fx['university', 'zero', c] / fx['university', '5 halala', c] - 1) * 100, 1),
                             calendar_effect_5h_pct=round((fx['university', '5 halala', c] / fx['office-like', '5 halala', c] - 1) * 100, 1),
                             calendar_effect_zero_pct=round((fx['university', 'zero', c] / fx['office-like', 'zero', c] - 1) * 100, 1))
                        for c in CITIES])
    dec.to_csv(RESULTS / 'robust_decomposition.csv', index=False)
    print(dec.to_string(index=False))

    # B + C) deterministic
    rows, tuned = [], {}
    for occ in [0.0, 0.5]:
        for city in CITIES:
            pv, load, rain, fc, _ = load_case(city, 'university', summer_occ=occ)
            for ename, pe in EXPORT.items():
                for cname, cm2 in COSTS.items():
                    best = tune(pv, load, rain, RATE[city], pe, cm2 * AREA, fc)
                    f = best['Fixed interval'][2]['gain']
                    for s, (par, _, r) in best.items():
                        rows.append(dict(summer_occ=occ, city=city, export=ename, cost=cname, policy=s, param=par,
                                         n=r['n'], summer_n=r['summer_n'], gain=round(r['gain']),
                                         vs_fixed_pct=round((r['gain'] / f - 1) * 100, 1)))
                    if occ == 0.0:
                        tuned[(city, ename, cname)] = best
    pd.DataFrame(rows).to_csv(RESULTS / 'robust_deterministic.csv', index=False)
    print(f'deterministic done ({time.time() - t0:.0f}s)')

    # D) Monte Carlo
    mc = []
    for city in CITIES:
        pv, load, rain, fc, _ = load_case(city, 'university')
        rng = np.random.default_rng(2027 if city == 'riyadh' else 4054)
        years = [synth_year(city, rng) for _ in range(N_MC)]
        for ename, pe in EXPORT.items():
            for cname, cm2 in COSTS.items():
                C = cm2 * AREA
                for y, (rates, st) in enumerate(years):
                    v0 = simulate(pv, load, rain, rates, lambda d, L: False, pe, st)['value']
                    for s, (par, make, _) in tuned[(city, ename, cname)].items():
                        r = simulate(pv, load, rain, rates, make(), pe, st)
                        mc.append(dict(city=city, export=ename, cost=cname, year=y, policy=s, param=par,
                                       n=r['n'], summer_n=r['summer_n'], gain=r['value'] - r['n'] * C - v0))
    mc = pd.DataFrame(mc)
    key = ['city', 'export', 'cost', 'year']
    fixg = mc[mc.policy == 'Fixed interval'].set_index(key)['gain']
    scg = mc[mc.policy == 'Predictive SC-aware'].set_index(key)['gain']
    idx = pd.MultiIndex.from_frame(mc[key])
    mc['vs_fixed_pct'] = (mc.gain.values / fixg.reindex(idx).values - 1) * 100
    mc['sc_beats'] = scg.reindex(idx).values > mc.gain.values
    mc.to_csv(RESULTS / 'robust_montecarlo.csv', index=False)
    summ = mc.groupby(['city', 'export', 'cost', 'policy'], sort=False).agg(
        gain_mean=('gain', 'mean'), gain_sd=('gain', 'std'), vs_fixed_mean=('vs_fixed_pct', 'mean'),
        vs_fixed_p10=('vs_fixed_pct', lambda x: np.percentile(x, 10)),
        vs_fixed_p90=('vs_fixed_pct', lambda x: np.percentile(x, 90)),
        n_mean=('n', 'mean'), summer_n_mean=('summer_n', 'mean'),
        sc_wins_pct=('sc_beats', lambda x: 100 * x.mean())).round(1)
    summ.to_csv(RESULTS / 'robust_montecarlo_summary.csv')
    print(summ.to_string())
    print(f'total {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
