"""Step 2: clean-array PV output with pvlib (150 kWp, 20 deg tilt, south).

Input : weather/riyadh.epw, weather/jeddah.epw
Output: data/pv/<city>_base.csv  (hourly pv_kwh, poa, rain_mm, plus the EnergyPlus load for reference)
"""
import pandas as pd
import pvlib
from common import WEATHER, PV, METERS, CITIES, PV_KWP, read_meter

TILT, AZIM = 20, 180
IDX = pd.date_range('2026-01-01 00:00', periods=8760, freq='h')


def pv_output(epw):
    w, meta = pvlib.iotools.read_epw(epw, coerce_year=2026)
    times = w.index - pd.Timedelta('30min')                    # mid-hour solar position
    loc = pvlib.location.Location(meta['latitude'], meta['longitude'],
                                  tz='Asia/Riyadh', altitude=meta['altitude'])
    sp = loc.get_solarposition(times)
    S = lambda c: pd.Series(w[c].values, index=times)
    poa = pvlib.irradiance.get_total_irradiance(
        TILT, AZIM, sp['apparent_zenith'], sp['azimuth'], S('dni'), S('ghi'), S('dhi'),
        dni_extra=pvlib.irradiance.get_extra_radiation(times), model='haydavies')
    poa_g = poa['poa_global'].fillna(0).clip(lower=0)
    tcell = pvlib.temperature.faiman(poa_g, S('temp_air'), S('wind_speed'))
    dc = pvlib.pvsystem.pvwatts_dc(poa_g, tcell, PV_KWP * 1000, -0.0035)
    dc = dc * (1 - pvlib.pvsystem.pvwatts_losses(soiling=0) / 100)     # ~12% losses, soiling excluded
    ac = pvlib.inverter.pvwatts(dc, PV_KWP * 1000 / 1.2 / 0.96).clip(lower=0)   # DC/AC 1.2, 96%
    return pd.DataFrame({'pv_kwh': ac.values / 1000, 'poa': poa_g.values,
                         'rain_mm': w['liquid_precipitation_depth'].fillna(0).values}, index=IDX), meta


def main():
    PV.mkdir(parents=True, exist_ok=True)
    for city in CITIES:
        df, meta = pv_output(WEATHER / f'{city}.epw')
        df['load_kwh'] = read_meter(METERS / f'office_{city}Meter.csv').ravel()
        df.to_csv(PV / f'{city}_base.csv')
        print(f"{city} ({meta['city']}): {df.pv_kwh.sum() / 1000:.1f} MWh, "
              f"{df.pv_kwh.sum() / PV_KWP:.0f} kWh/kWp, rain {df.rain_mm.sum():.0f} mm")


if __name__ == '__main__':
    main()
