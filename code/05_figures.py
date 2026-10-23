"""Step 5: paper figures 2-5 (IEEE single-column width). Fig. 1 is drawn by fig1_method.py."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from common import RESULTS, PV, METERS, FIGURES, read_meter

plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'Liberation Serif', 'DejaVu Serif'],
                     'font.size': 8, 'axes.titlesize': 8, 'axes.labelsize': 8, 'legend.fontsize': 7,
                     'xtick.labelsize': 7, 'ytick.labelsize': 7, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.grid': True, 'grid.color': '#e6e6e6',
                     'grid.linewidth': 0.5, 'axes.axisbelow': True, 'savefig.dpi': 300})
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'
W = 3.5
S0, S1 = pd.Timestamp('2026-06-14'), pd.Timestamp('2026-08-22')


def save(fig, name):
    FIGURES.mkdir(exist_ok=True)
    for ext in ('png', 'pdf'):
        fig.savefig(FIGURES / f'{name}.{ext}', bbox_inches='tight')
    plt.close(fig)


def month_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 3, 5, 7, 9, 11]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))


def main():
    main_df = pd.read_csv(RESULTS / 'results_main.csv')

    # Fig. 2: daily load vs PV (university calendar)
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.0), sharex=True)
    for ax, city in zip(axes, ['riyadh', 'jeddah']):
        pv = pd.read_csv(PV / f'{city}_base.csv', index_col=0, parse_dates=True)['pv_kwh']
        load = pd.Series(read_meter(METERS / f'office_{city}_sbMeter.csv').ravel(), index=pv.index)
        dl = (load.resample('D').sum() / 1000).rolling(7, center=True, min_periods=1).mean()
        dp = (pv.resample('D').sum() / 1000).rolling(7, center=True, min_periods=1).mean()
        ax.axvspan(S0, S1, color='#efefef', lw=0, zorder=0)
        ax.text(S0 + (S1 - S0) / 2, 0.04, 'Summer\nbreak', transform=ax.get_xaxis_transform(),
                ha='center', va='bottom', fontsize=6.5, color='#52514e')
        ax.plot(dl.index, dl, color=C1, lw=1.2, label='Building load')
        ax.plot(dp.index, dp, color=C2, lw=1.2, label='PV generation (clean)')
        ax.set_ylabel('MWh/day (7-day mean)'); ax.set_title(city.capitalize(), loc='left'); ax.set_ylim(0, 2.1)
    month_axis(axes[1])
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1)); save(fig, 'fig2_load_pv')

    # Fig. 3: value of cleaning
    v = main_df[(main_df.strategy == 'Fixed interval') & (main_df.cost == 'base')]
    cases = [('office-like', '5 halala'), ('office-like', 'zero'), ('university', '5 halala'), ('university', 'zero')]
    labels = ['Office\n5 halala', 'Office\nzero export', 'University\n5 halala', 'University\nzero export']
    fig, ax = plt.subplots(figsize=(W, 2.2)); x = np.arange(4); w = 0.38
    for i, (city, col) in enumerate([('riyadh', C1), ('jeddah', C2)]):
        vals = [v[(v.scenario == s) & (v.export == e) & (v.city == city)].gain.iloc[0] / 1000 for s, e in cases]
        b = ax.bar(x + (i - 0.5) * w, vals, w * 0.92, color=col, label=city.capitalize())
        ax.bar_label(b, fmt='%.1f', fontsize=6.5, padding=1.5)
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel('Net benefit of cleaning\n(k SAR/yr)')
    ax.set_ylim(0, 23); ax.legend(frameon=False, ncol=2, loc='upper right'); ax.grid(axis='x', visible=False)
    fig.tight_layout(); save(fig, 'fig3_value_of_cleaning')

    # Fig. 4: % vs best fixed (university)
    strats = [('Soiling threshold', C1, ''), ('Predictive energy-only', C2, ''), ('Predictive SC-aware', C3, '///')]
    fig, axes = plt.subplots(2, 2, figsize=(W, 3.4), sharey='col')
    for r, exp in enumerate(['zero', '5 halala']):
        for c, cost in enumerate(['base', 'high']):
            ax = axes[r, c]
            sub = main_df[(main_df.scenario == 'university') & (main_df.export == exp) & (main_df.cost == cost)]
            for i, (s, col, h) in enumerate(strats):
                vals = [sub[(sub.city == city) & (sub.strategy == s)].vs_fixed_pct.iloc[0] for city in ['riyadh', 'jeddah']]
                b = ax.bar(np.arange(2) + (i - 1) * 0.27, vals, 0.25, color=col, hatch=h, edgecolor='white',
                           lw=0.3, label=s.replace('Predictive ', 'Pred. '))
                ax.bar_label(b, fmt='%.1f', fontsize=5.5, padding=1)
            ax.set_xticks([0, 1]); ax.set_xticklabels(['Riyadh', 'Jeddah'])
            ax.set_title(f'{"Zero export" if exp == "zero" else "Export 5 halala"}, {cost} cost', loc='left', fontsize=7)
            ax.grid(axis='x', visible=False); ax.axhline(0, color='#888', lw=0.5); ax.margins(y=0.18)
            if c == 0:
                ax.set_ylabel('% vs best fixed')
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1)); save(fig, 'fig4_improvement')

    # Fig. 5: soiling-loss trajectories
    tr = pd.read_csv(RESULTS / 'trajectories.csv', index_col=0, parse_dates=True)
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.0), sharex=True)
    for ax, city in zip(axes, ['riyadh', 'jeddah']):
        ax.axvspan(S0, S1, color='#efefef', lw=0, zorder=0)
        ax.plot(tr.index, tr[f'{city}_Fixed interval'] * 100, color=C1, lw=1.0, label='Best fixed interval')
        ax.plot(tr.index, tr[f'{city}_Predictive SC-aware'] * 100, color=C3, lw=1.2, label='Predictive SC-aware')
        ax.set_ylabel('Soiling loss (%)'); ax.set_title(city.capitalize(), loc='left'); ax.set_ylim(0, 28)
    axes[0].text(S0 + (S1 - S0) / 2, 0.97, 'Summer break', transform=axes[0].get_xaxis_transform(),
                 ha='center', va='top', fontsize=6.5, color='#52514e',
                 bbox=dict(facecolor='#efefef', edgecolor='none', pad=0.5))
    month_axis(axes[1])
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1)); save(fig, 'fig5_trajectories')
    print('figures written to', FIGURES)


if __name__ == '__main__':
    main()
