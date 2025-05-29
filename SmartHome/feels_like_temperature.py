#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Author:      E:V:A
#  Date:        2022-02-01
#  Last:        2024-10-21
#  Repo/Bugs:   https://github.com/E3V3A/iata-arrivals-cli
#  Version:     1.0.3   (pyflightdata-0.8.5)
#  Codec:       utf_8
#  License:     GPLv3
#  Donate?
# ----------------------------------------------------------------------------
#
#  Description:
#
#   A number of functions used to calculate the *Feels Like* temperature,
#   given ambient bulb (without wind or radiation) temperature [°C],
#   wind speed [Km/h] and *Relative Humidty" [%] (RH).
#
#   There are literally several dozens of formulas and 100's of science
#   publications on how to do this, so we just chose a well known method,
#   namely that used by NOAA (US).
#
#   That method relies on also calculating:
#   - The Heat Index (HI)
#   - The Wind Chill (WS)
#
#  References:
#   [1] https://github.com/malexer/meteocalc/tree/master/meteocalc
#   [2] http://www.bom.gov.au/info/thermal_stress/#atapproximation
# ----------------------------------------------------------------------------
import math

# taken from https://gist.github.com/E3V3A/8f9f0aa18380d4ab2546cd50b725a219

# ----------------------------------------------------------------------------
# Heat Index
# ----------------------------------------------------------------------------

def heat_index(temperature, humidity):
    """
    Calculate the Heat Index (feels like temperature) based on the NOAA equation.

    The Heat Index (HI), or humiture, or "feels like temperature", is an index that combines
    air-temperature and relative humidity in an attempt to determine the human-perceived
    equivalent temperature.

    HI is only useful when (T > 27 °C) & (RH > 40 %)
    Tf = (Tc * 9/5) + 32
    Tc = (Tf - 32) * 5/9

    See:
    [1] https://en.wikipedia.org/wiki/Heat_index
    [2] http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
    [3] https://github.com/geanders/weathermetrics/blob/master/R/heat_index.R
    [4] https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3801457/
    """

    T = temperature  # Celsius
    H = humidity  # Relative Humidity

    # SI units (Celsius)
    c1 = -8.78469475556
    c2 = 1.61139411
    c3 = 2.33854883889
    c4 = -0.14611605
    c5 = -0.012308094
    c6 = -0.0164248277778
    c7 = 0.002211732
    c8 = 0.00072546
    c9 = -0.000003582

    # ----------------------------------------------------------------
    # Maybe consider [4] in "Formula-18" by [Costanzo et al. 2006]
    # HIc   = Tc – 0.55 * (1 – 0.001 H)(Tc – 14.5)
    #       = Tc - 0.55 * (Tc - 14.5 - 0.001*H*Tc + 0.001*14.5*H
    # ----------------------------------------------------------------

    Tf = (T * 9 / 5) + 32
    # Try the simplified formula from [2] first (used for HI < 80)
    HIf = 0.5 * (Tf + 61.0 + (Tf - 68.0) * 1.2 + H * 0.094)
    Tavg = (HIf + Tf) / 2  # Instructions in [3] call for averaging

    if Tavg >= 80:  # [°F]
        # IF (T > 27C) & (H > 40 %):
        # Use the full Rothfusz regression formula (now in Celsius)
        HI = math.fsum([
            c1,
            c2 * T,
            c3 * H,
            c4 * T * H,
            c5 * T ** 2,
            c6 * H ** 2,
            c7 * T ** 2 * H,
            c8 * T * H ** 2,
            c9 * T ** 2 * H ** 2,
        ])
    else:
        HI = (HIf - 32) * 5 / 9

    return HI


# ----------------------------------------------------------------------------
# Wind Chill
# ----------------------------------------------------------------------------

def wind_chill(temperature, wind_speed):
    """
    Calculate the Wind Chill (feels like temperature) based on NOAA.

    Wind-chill or windchill (popularly wind chill factor) is the lowering of
    body temperature due to the passing-flow of lower-temperature air.

    Wind chill numbers are always lower than the air temperature for values
    where the formula is valid. When the apparent temperature is higher than
    the air temperature, the heat index is used instead.

    Wind Chill Temperature is only defined for temperatures at or below
    50 °F and wind speeds above 3 mph. (10°C, 4.8 Km/h)

    3 Mph = 4.828 [Km/h] = 1.34 [m/s]
    50°F  = (50 - 32) * 5/9 = 10°C

    See:
    [1] https://en.wikipedia.org/wiki/Wind_chill
    [2] https://www.wpc.ncep.noaa.gov/html/windchill.shtml
    """

    T = temperature  # Celsius
    V = wind_speed  # Kilometer per hour

    # We should never get here...
    if T > 10 or V <= 4.8:  # if T > 50 or V <= 3:    # (°F, Mph)
        e = "Wind Chill Temperature is only defined for temperatures at or below 10°C and wind speeds above 4.8 Km/h."
        raise ValueError(e)

    # ----------------------------------
    # WC = Wind Chill [2]
    # ----------------------------------
    # (Farenheit, Mph)
    # WC = 35.74 + (0.6215 * T) - 35.75 * V**0.16 + 0.4275 * T * V**0.16
    # (Celsius, Kph)
    WC = 13.12 + (0.6215 * T) - 11.37 * V ** 0.16 + 0.3965 * T * V ** 0.16

    return WC


# ----------------------------------------------------------------------------
# (Australian) Apparent Temperature
# ----------------------------------------------------------------------------
def apparent_temp(temperature, humidity, wind_speed):
    """
    The apparent temperature (AT) used here is based on a mathematical model
    of an adult, walking outdoors, in the shade (Steadman 1994). The AT is
    defined as; the temperature, at the reference humidity level, producing
    the same amount of discomfort as that experienced under the current
    ambient temperature and humidity.

    [WIP] ??? Practically speaking, this means that you have to adjust the ambient
    temparature by the AT. In this function the returned value, is the
    already adjusted temperature.

    The vapour pressure can be calculated from the temperature and
    relative humidity (RH) using the equation:

    P =  (RH/100) * 6.105 * exp( (17.27 * Ta) / (237.7 + Ta) )

    -----------------------------------------------------
    RH = relative humidity [%]
    Ta = dry bulb temperature [°C]
     e = water vapour pressure [hPa]
     v = wind speed [m/s] at an elevation of 10 m.
    -----------------------------------------------------

    References:
    [1] http://www.bom.gov.au/info/thermal_stress/#atapproximation
    """
    H = humidity  # [%]   relative humidity
    T = temperature  # [°C]
    V = wind_speed  # [m/s]

    # [hPa] water vapor pressure
    P = (H / 100) * 6.105 * math.exp((17.27 * T) / (237.7 + T))

    #
    AT = T + 0.33 * P - 0.7 * V - 4

    # return round(T + AT, 1)
    return round(AT, 1)


# ----------------------------------------------------------------------------
# Feels Like
# ----------------------------------------------------------------------------
def feels_like(temperature, humidity, wind_speed):
    """
    Calculate the "Feels Like" temperature based on NOAA.

    Logic:
    * Wind Chill:   temperature <= 50 F and wind > 3 mph
    * Heat Index:   temperature >= 80 F
    * Temperature as is: all other cases

    -----------------------------------------------------
    50°F  = (50°F - 32) * 5/9 = 10°C
    80°F  = (80°F - 32) * 5/9 = 26.7 °C
    3 Mph = 4.828 [Km/h] = 1.34 [m/s]
    1 [m/s] =   1/[1000 m/Km] * [3600 s/hour] = 3.6 [Km/h]
    -----------------------------------------------------
    """

    T = temperature  # [°C]

    # ----------------------------------
    # FL = Feels Like
    # ----------------------------------
    if T <= 10 and wind_speed > 4.8:
        # Wind Chill for low temp cases (and wind)
        FL = wind_chill(T, wind_speed)
    elif T >= 26.7:
        # Heat Index for High temp cases
        FL = heat_index(T, humidity)
    else:
        FL = T

    return round(FL, 1)

# ----------------------------------------------------------------------------
#  EOF
# ----------------------------------------------------------------------------
