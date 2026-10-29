"""Step 1: adapt the PNNL ASHRAE 90.1-2019 medium-office prototype to Riyadh and Jeddah.

Input : idf/base_ASHRAE901_OfficeMedium_STD2019_Denver_meter.idf  (prototype + hourly Electricity:Facility meter)
        weather/riyadh.ddy, weather/jeddah.ddy                      (from the TMYx 2011-2025 zip files)
Output: idf/office_<city>.idf      office-like calendar
        idf/office_<city>_sb.idf   university calendar with summer break (14 Jun - 22 Aug)

Changes: full-year RunPeriod starting on Friday (Sunday-Thursday working week), ASHRAE 99.6% heating and
0.4% cooling design days and site location from the .ddy, U.S. holidays and DST removed, Eid holidays added,
glazing set to ASHRAE 90.1-2019 climate zone 0 (U = 2.84 W/m2K, SHGC = 0.22).
Then run each IDF in EnergyPlus (EP-Launch) with the matching EPW and copy <name>Meter.csv to
data/energyplus_meters/.
"""
from common import IDF, WEATHER, CITIES

ORDER = ['name', 'month', 'day of month', 'day type', 'maximum dry-bulb temperature',
         'daily dry-bulb temperature range', 'dry-bulb temperature range modifier type',
         'dry-bulb temperature range modifier day schedule name', 'humidity condition type',
         'wetbulb or dewpoint at maximum dry-bulb', 'humidity condition day schedule name',
         'humidity ratio at maximum dry-bulb', 'enthalpy at maximum dry-bulb',
         'daily wet-bulb temperature range', 'barometric pressure', 'wind speed',
         'wind direction', 'rain indicator', 'snow indicator', 'daylight saving time indicator',
         'solar model indicator', 'beam solar day schedule name', 'diffuse solar day schedule name',
         'taub', 'taud', 'sky clearness']
DEFAULTS = {'rain indicator': 'No', 'snow indicator': 'No', 'daylight saving time indicator': 'No',
            'dry-bulb temperature range modifier type': 'DefaultMultipliers'}
# old .ddy field labels -> EnergyPlus 26 field names
RULES = [('taub', 'taub'), ('taud', 'taud'), ('sky clearness', 'sky clearness'),
         ('wind speed', 'wind speed'), ('wind direction', 'wind direction'),
         ('wetbulb at max', 'wetbulb or dewpoint at maximum dry-bulb'),
         ('wetbulb or dewpoint', 'wetbulb or dewpoint at maximum dry-bulb'),
         ('humidity indicating day', 'humidity condition day schedule name'),
         ('humidity indicating type', 'humidity condition type')]

RUNPERIOD = """
RunPeriod,
    Annual,                  !- Name
    1,                       !- Begin Month
    1,                       !- Begin Day of Month
    ,                        !- Begin Year
    12,                      !- End Month
    31,                      !- End Day of Month
    ,                        !- End Year
    Friday,                  !- Day of Week for Start Day (shifts the U.S. Mon-Fri week to Sun-Thu)
    No,                      !- Use Weather File Holidays and Special Days
    No,                      !- Use Weather File Daylight Saving Period
    No,                      !- Apply Weekend Holiday Rule
    Yes,                     !- Use Weather File Rain Indicators
    Yes;                     !- Use Weather File Snow Indicators
"""
HOLIDAYS = """
RunPeriodControl:SpecialDays,
    Eid al-Fitr,             !- Name
    3/19,                    !- Start Date
    7,                       !- Duration {days}
    Holiday;                 !- Special Day Type

RunPeriodControl:SpecialDays,
    Eid al-Adha,             !- Name
    5/25,                    !- Start Date
    7,                       !- Duration {days}
    Holiday;                 !- Special Day Type
"""
SUMMER_BREAK = """
RunPeriodControl:SpecialDays,
    Summer Break,            !- Name
    6/14,                    !- Start Date
    70,                      !- Duration {days}
    Holiday;                 !- Special Day Type
"""
GLAZING = """  WindowMaterial:SimpleGlazingSystem,
    Glazing Layer,           !- Name
    2.84,                    !- U-Factor {W/m2-K}
    0.22,                    !- Solar Heat Gain Coefficient
    0.418;                   !- Visible Transmittance"""


def get_objects(text, cls):
    """Return the full text of every object of class cls (ignores ';' inside comments)."""
    objs, cur = [], None
    for line in text.splitlines():
        code = line.split('!', 1)[0]
        if cur is None and code.strip().lower().startswith(cls.lower() + ','):
            cur = []
        if cur is not None:
            cur.append(line)
            if ';' in code:
                objs.append('\n'.join(cur)); cur = None
    return objs


def remove(text, cls):
    for o in get_objects(text, cls):
        text = text.replace(o, '')
    return text


def canon(label):
    k = label.split('{')[0].strip().lower()
    for sub, c in RULES:
        if sub in k:
            return c
    return k


def design_day(src):
    vals = {}
    for line in src.splitlines()[1:]:
        if '!' in line:
            code, lab = line.split('!', 1)
            vals[canon(lab.lstrip('-').strip())] = code.strip().rstrip(',;').strip()
    lines = ['SizingPeriod:DesignDay,']
    for i, k in enumerate(ORDER):
        end = ';' if i == len(ORDER) - 1 else ','
        lines.append(f'    {vals.get(k, DEFAULTS.get(k, ""))}{end}    !- {k}')
    return '\n'.join(lines)


def main():
    base = (IDF / 'base_ASHRAE901_OfficeMedium_STD2019_Denver_meter.idf').read_text(encoding='latin-1')
    for cls in ['RunPeriod', 'SizingPeriod:DesignDay', 'Site:Location',
                'RunPeriodControl:SpecialDays', 'RunPeriodControl:DaylightSavingTime']:
        base = remove(base, cls)
    glz = get_objects(base, 'WindowMaterial:SimpleGlazingSystem')
    assert len(glz) == 1
    base = base.replace(glz[0], GLAZING) + RUNPERIOD + HOLIDAYS

    for city in CITIES:
        ddy = (WEATHER / f'{city}.ddy').read_text(encoding='latin-1')
        loc = get_objects(ddy, 'Site:Location')[0]
        dds = get_objects(ddy, 'SizingPeriod:DesignDay')
        htg = [d for d in dds if 'Htg 99.6%' in d and 'Humidification' not in d][0]
        clg = [d for d in dds if 'Clg .4%' in d and 'DB=>MWB' in d][0]
        idf = base + '\n' + loc + '\n\n' + design_day(htg) + '\n\n' + design_day(clg) + '\n'
        (IDF / f'office_{city}.idf').write_text(idf, encoding='latin-1')
        (IDF / f'office_{city}_sb.idf').write_text(idf + SUMMER_BREAK, encoding='latin-1')
        print(f'{city}: written office_{city}.idf and office_{city}_sb.idf')


if __name__ == '__main__':
    main()
