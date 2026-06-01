"""Physical constants and default gas properties for PropulsionLab v1.

The v1 model uses constant perfect-gas properties. Air properties are used
upstream of combustion, while representative hot-gas properties are used from
the combustor exit through the turbine and nozzle.
"""

gamma_air = 1.4
cp_air = 1004.0  # J/kg/K
R_air = 287.0  # J/kg/K

gamma_gas = 1.33
cp_gas = 1150.0  # J/kg/K

g0 = 9.80665  # m/s^2
T_SL = 288.15  # K
P_SL = 101325.0  # Pa
rho_SL = 1.225  # kg/m^3
L_lapse = 0.0065  # K/m

fuel_heating_value_default = 43e6  # J/kg

