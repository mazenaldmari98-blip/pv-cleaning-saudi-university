"""Step 6: repeat the out-of-sample test with alternative soiling generators (zero export, university)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import numpy as np, pandas as pd, importlib.util
spec=importlib.util.spec_from_file_location('rb',str(__import__('pathlib').Path(__file__).resolve().parent / '04_robustness.py')); rb=importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
from common import *
variants={'base generator':{}, 'no seasonality':{'season':False}, 'noise sigma 1.0':{'sigma':1.0},
          'storms x2':{'storm_mult':2}, 'no storms':{'storm_mult':0}}
def synth(city,rng,season=True,sigma=0.5,storm_mult=1):
    r=RATE[city]*(np.array([rb.SEASON[city][m-1] for m in DAYS.month]) if season else np.ones(365))
    r=r/r.mean()*RATE[city]; r=r*rng.lognormal(-sigma**2/2,sigma,365)
    st=np.zeros(365); cfg=rb.STORMS[city]; elig=np.where(DAYS.month.isin(cfg['months']))[0]
    k=min(len(elig),rng.poisson(cfg['rate']*storm_mult))
    for d in rng.choice(elig,size=k,replace=False): st[d]=rng.uniform(*cfg['step'])
    return r,st
rows=[]
for city in CITIES:
    pv,load,rain,fc,_=load_case(city,'university')
    for cname in ['base','high']:
        C=COST_M2[cname]*AREA; pe=0.0
        best=rb.tune(pv,load,rain,RATE[city],pe,C,fc)
        for vn,kw in variants.items():
            rng=np.random.default_rng(2027 if city == 'riyadh' else 4054)   # same seeds as 04_robustness.py
            g={s:[] for s in best}
            for y in range(100):
                rates,st=synth(city,rng,**kw)
                v0=simulate(pv,load,rain,rates,lambda d,L:False,pe,st)['value']
                for s,(par,make,_) in best.items():
                    r=simulate(pv,load,rain,rates,make(),pe,st); g[s].append(r['value']-r['n']*C-v0)
            g={s:np.array(v) for s,v in g.items()}
            f=g['Fixed interval']; sc=g['Predictive SC-aware']
            other=np.maximum(g['Soiling threshold'],g['Predictive energy-only'])
            rows.append(dict(city=city,cost=cname,variant=vn,
              SC_vs_fixed=round(((sc/f-1)*100).mean(),1),
              thr_vs_fixed=round(((g['Soiling threshold']/f-1)*100).mean(),1),
              eo_vs_fixed=round(((g['Predictive energy-only']/f-1)*100).mean(),1),
              skip_vs_fixed=round(((g['Fixed + summer skip']/f-1)*100).mean(),1),
              fixed_mean=round(f.mean()), thr_mean=round(g['Soiling threshold'].mean()),
              eo_mean=round(g['Predictive energy-only'].mean()), sc_mean=round(sc.mean()),
              adv_pp=round(((sc/f-1)*100).mean()-max(((g['Soiling threshold']/f-1)*100).mean(),((g['Predictive energy-only']/f-1)*100).mean()),1),
              SC_best_mean=bool(((sc/f-1)*100).mean()>=max(((g['Soiling threshold']/f-1)*100).mean(),((g['Predictive energy-only']/f-1)*100).mean())),
              SC_beats_thr=int((sc>g['Soiling threshold']).mean()*100), SC_beats_eo=int((sc>g['Predictive energy-only']).mean()*100)))
df=pd.DataFrame(rows); pd.set_option('display.width',250); print(df.to_string(index=False))
df.to_csv(RESULTS / 'robust_generator_sensitivity.csv',index=False)
