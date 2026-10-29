"""Fig. 1: methodology diagram."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({'font.family': 'serif',
                     'font.serif': ['Times New Roman', 'Liberation Serif', 'Nimbus Roman', 'DejaVu Serif'],
                     'font.size': 7})
INK, MUTED = '#0b0b0b', '#52514e'
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'

fig, ax = plt.subplots(figsize=(3.5, 3.55))
ax.set_xlim(0, 100); ax.set_ylim(2, 100); ax.axis('off')


def box(x, y, w, h, title, body, edge):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.4,rounding_size=1.5',
                                fc='white', ec=edge, lw=1.0))
    ax.text(x + w / 2, y + h - 2.2, title, ha='center', va='top', fontsize=7, weight='bold', color=INK)
    ax.text(x + w / 2, y + h - 7.6, body, ha='center', va='top', fontsize=5.6, color=MUTED, linespacing=1.25)


def arrow(x0, y0, x1, y1):
    ax.annotate('', xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle='-|>', color='#555555', lw=0.8, shrinkA=0, shrinkB=0,
                                mutation_scale=7))


# Row 1: inputs
box(1, 81, 30, 18, 'Weather', 'TMYx 2011–2025\nRiyadh, Jeddah\nASHRAE design days', BLUE)
box(35, 81, 30, 18, 'Building', 'PNNL medium office\n90.1-2019, CZ0 glazing\nSun–Thu, Eid, summer', BLUE)
box(69, 81, 30, 18, 'Economics', 'Import 0.35 SAR/kWh\nExport 0.05 or 0\nCleaning 79–2214 SAR', BLUE)

# Row 2: models
box(1, 56, 30, 18, 'PV model', 'pvlib, 150 kWp, 20° S\nHay–Davies, Faiman\nhourly P_PV,clean', ORANGE)
box(35, 56, 30, 18, 'EnergyPlus', 'hourly load L(t)\noffice-like and\nuniversity calendars', ORANGE)
box(69, 56, 30, 18, 'Soiling model', 'linear rate r (%/day)\nrain ≥ 3 mm resets\ncap 60%', ORANGE)

# Row 3: policies
box(1, 31, 98, 18, 'Daily cleaning decision (no cleaning on Fridays or Eid)',
    'Fixed N · Fixed + summer skip · Threshold θ · Pred. energy-only\n'
    'Predictive SC-aware: clean if  Σ_H [V(clean) − V(dirty)] ≥ C\n'
    'V = 0.35·min(P, L) + p_x·(P − min(P, L)), forecast P and L', AQUA)

# Row 4: outputs
box(1, 4, 98, 16, 'Evaluation (8760 h)',
    'Net benefit vs no cleaning · cleanings/yr · self-consumed\n'
    'and exported energy · sensitivity · 100 kWh battery', INK)

for x in (16, 50, 84):
    arrow(x, 81, x, 74.6)
for x in (16, 50, 84):
    arrow(x, 56, x, 49.6)
arrow(50, 31, 50, 20.6)
arrow(16, 81, 16, 74.6)
from common import FIGURES
fig.savefig(FIGURES / 'fig1_method.png', dpi=300, bbox_inches='tight')
fig.savefig(FIGURES / 'fig1_method.pdf', bbox_inches='tight')
print('ok')
