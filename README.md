# Self-consumption-aware PV cleaning scheduling for Saudi university buildings

Code and data for the paper:

> M. A. Al-Dhamari and M. E. Khlifi, "Self-Consumption-Aware Predictive Cleaning Scheduling for Rooftop PV on a Saudi University Building under Net Billing with Low Export Compensation: Riyadh versus Jeddah," submitted to ICAISC 2027, Jeddah, Saudi Arabia.

The study combines hourly EnergyPlus building loads, pvlib PV output and a soiling model to compare PV cleaning policies for a 150 kWp rooftop array when exported energy is credited at 0.05 SAR/kWh or not at all, against the 2027 governmental import tariff of 0.35 SAR/kWh.

## Repository layout

| Path | Content |
|---|---|
| `code/common.py` | Assumptions, calendar, soiling and valuation model, cleaning policies |
| `code/01_prepare_idf.py` | Adapts the PNNL ASHRAE 90.1-2019 medium-office prototype to Riyadh and Jeddah |
| `code/02_pv_model.py` | Clean-array PV output with pvlib |
| `code/03_cleaning_analysis.py` | Main results, sensitivity analysis and battery case |
| `code/04_robustness.py` | Calendar/export decomposition, calendar heuristic, summer occupancy, out-of-sample Monte Carlo |
| `code/05_figures.py`, `code/fig1_method.py` | Paper figures |
| `code/06_generator_sensitivity.py` | Out-of-sample test repeated with alternative soiling generators |
| `idf/` | Base prototype (with hourly `Electricity:Facility` meter) and the four adapted building models |
| `data/energyplus_meters/` | Hourly EnergyPlus electricity meters for the four building models |
| `data/pv/` | Hourly clean PV output and rain for each city |
| `data/results/` | All result tables used in the paper |
| `figures/` | Paper figures (PNG and PDF) |

## Reproducing the results

The result tables can be reproduced from the included data with Python only (steps 3–5, about one minute in total). Steps 1–2 regenerate the inputs.

**Requirements:** Python 3.10+, `pip install -r requirements.txt`, and EnergyPlus 26.2 for step 1.

1. **Weather.** Download the TMYx 2011–2025 files from [climate.onebuilding.org](https://climate.onebuilding.org) for `SAU_RI_Riyadh` and `SAU_MK_Jeddah-Abdulaziz.Intl.AP.410240`. Put the `.epw` and `.ddy` files in `weather/` as `riyadh.epw`, `riyadh.ddy`, `jeddah.epw` and `jeddah.ddy`.
2. **Building models.** `python code/01_prepare_idf.py` writes `idf/office_<city>.idf` (office-like calendar) and `idf/office_<city>_sb.idf` (university calendar with a summer break). Run each IDF in EnergyPlus with the matching EPW and copy `<name>Meter.csv` to `data/energyplus_meters/`.
3. **PV.** `python code/02_pv_model.py` writes `data/pv/<city>_base.csv`.
4. **Analysis.** `python code/03_cleaning_analysis.py`, then `python code/04_robustness.py` and `python code/06_generator_sensitivity.py`.
5. **Figures.** `python code/fig1_method.py` and `python code/05_figures.py`.

All scripts are run from the repository root or from `code/`; paths are resolved relative to the repository.

## Main assumptions

| Item | Value |
|---|---|
| Building | PNNL ASHRAE 90.1-2019 medium office, 4,982 m², climate zone 0 glazing (U = 2.84 W/m²K, SHGC = 0.22) |
| Calendar | 2026, Sunday–Thursday week, Eid al-Fitr 19–25 Mar, Eid al-Adha 25–31 May; university case adds a summer break 14 Jun–22 Aug |
| PV | 150 kWp, 20° tilt, south, Hay–Davies, Faiman, PVWatts, 12% losses, DC/AC 1.2 |
| Soiling | linear, 0.25 %/day (Riyadh), 0.35 %/day (Jeddah), cap 60%, reset by rain ≥ 3 mm/day |
| Tariffs | import 0.35 SAR/kWh (governmental tariff from 1 January 2027); export 0.05 SAR/kWh or zero |
| Cleaning cost | 0.11 / 0.375 / 1.1 / 3.1 SAR/m² per event (module area 714 m²) |
| Battery case | 100 kWh / 50 kW, 95% one-way efficiency, 10–90% SOC |

## Licence

Code: MIT licence (see `LICENSE`). The building model is derived from the U.S. DOE/PNNL prototype building models. Weather files are not redistributed; download them from climate.onebuilding.org.
