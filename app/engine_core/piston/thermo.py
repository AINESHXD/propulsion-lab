"""Temperature-dependent gas properties for the in-cylinder charge.

The cycle integrator originally ran on a single constant ``gamma = 1.35``. That
is a fair average for a burned charge but it is wrong at both ends of the cycle,
and it is wrong in the direction that flatters the engine: real specific heats
*rise* steeply with temperature as vibrational modes activate, so a fixed low
``cv`` converts the same heat release into far too much temperature rise. Peak
temperatures came out optimistically high as a direct consequence, and the whole
expansion stroke inherited the error.

Two effects are captured here.

**Temperature.** ``cp`` for air climbs from about 1003 J/kg/K at 300 K to
1251 at 2000 K, so ``gamma`` falls from 1.40 to about 1.30 across the cycle.

**Composition.** Combustion products hold far more heat than air — 1432 J/kg/K
against 1251 at 2000 K, because CO2 and H2O are triatomic — which drops
``gamma`` further, to about 1.25. A cylinder part-way through its burn is a
mixture of the two, so properties are blended by burned mass fraction.

Where the numbers come from
---------------------------
The polynomial coefficients below were fitted offline against **Cantera**
(GRI-Mech 3.0) over 250-3500 K and are hard-coded, so nothing here needs Cantera
at runtime — which matters because the crank-angle march evaluates these
hundreds of times per solve and the console re-solves on every slider drag.
The fits hold to better than 0.5% of Cantera across the whole range, and
:mod:`tests.test_piston_thermo` re-checks them against Cantera directly whenever
it happens to be installed.

The product composition is not a generic "burned gas": it is the stoichiometric
product of PistonLab's own gasoline model (``C8H16 + 12 O2 -> 8 CO2 + 8 H2O``,
carrying its nitrogen), so it is consistent with :mod:`fuel`. Composition is
**frozen** — dissociation at very high temperature is not modelled, which means
peak temperatures are still somewhat high, just far less so than before.

Energy bookkeeping
------------------
Internal energy is referenced to zero at :data:`REFERENCE_TEMPERATURE_K` for
*both* compositions. That is deliberate: combustion energy enters the cycle as
Wiebe heat release, not as an enthalpy of formation, so the datum must not
double-count it. The integrator marches total internal energy and inverts back
to temperature, which keeps the first law closing exactly even as composition
shifts underneath it.
"""

from __future__ import annotations

import math

# Fitted cp(T) [J/kg/K] as a polynomial in x = T / 1000, ascending powers.
# Generated from Cantera GRI-Mech 3.0; see module docstring.
_AIR_CP = (
    1.03176593e03, -3.42232046e02, 1.06023165e03, -9.23160225e02,
    3.85163891e02, -7.87993459e01, 6.34218730e00,
)
_PRODUCT_CP = (
    1.03214427e03, -5.41770572e01, 7.48936832e02, -6.87166182e02,
    2.84529903e02, -5.73309153e01, 4.55147420e00,
)

_AIR_CP_INT = tuple(c / (i + 1) for i, c in enumerate(_AIR_CP))
_PRODUCT_CP_INT = tuple(c / (i + 1) for i, c in enumerate(_PRODUCT_CP))

# Specific gas constants for the two compositions [J/kg/K].
R_AIR = 287.0416
R_PRODUCT = 288.7114

#: Datum for specific internal energy. Arbitrary, but shared by both
#: compositions so that a change of composition at fixed temperature releases
#: no spurious energy.
REFERENCE_TEMPERATURE_K = 298.15

# The fit was made over this window; outside it the polynomial is extrapolating
# and the caller should not trust it. The upper end is set above any temperature
# a real charge reaches, because dissociation -- which this frozen composition
# does not model -- absorbs energy and caps real burned gas near 2800-3000 K.
# A two-zone burned temperature above that band is therefore an over-estimate,
# not a measurement.
VALID_MIN_K = 250.0
VALID_MAX_K = 3500.0


def _poly(coeffs: tuple[float, ...], x: float) -> float:
    """Evaluate an ascending-power polynomial by Horner's method."""

    total = 0.0
    for c in reversed(coeffs):
        total = total * x + c
    return total


def _integral_coeffs(coeffs: tuple[float, ...]) -> tuple[float, ...]:
    """Coefficients of the antiderivative, divided out once at import time."""

    return tuple(c / (i + 1) for i, c in enumerate(coeffs))


def _poly_integral(coeffs: tuple[float, ...], x: float) -> float:
    """Integral of the polynomial with respect to *temperature*, not x.

    ``dT = 1000 dx``, so the antiderivative in T carries that factor. Evaluated
    in Horner form: this sits in the innermost loop of the crank-angle march, so
    it must not be doing repeated ``pow`` calls.
    """

    return 1000.0 * x * _poly(_integral_coeffs(coeffs), x)


def mixture_gas_constant(burned_fraction: float = 0.0) -> float:
    """Specific gas constant of the charge [J/kg/K], blended by burned mass."""

    x = _clamp_fraction(burned_fraction)
    return (1.0 - x) * R_AIR + x * R_PRODUCT


def cp_J_per_kg_K(temperature_K: float, burned_fraction: float = 0.0) -> float:
    """Constant-pressure specific heat of the charge [J/kg/K]."""

    if temperature_K <= 0.0:
        raise ValueError("temperature_K must be positive.")
    x = _clamp_fraction(burned_fraction)
    t = _clamp_temperature(temperature_K) / 1000.0
    return (1.0 - x) * _poly(_AIR_CP, t) + x * _poly(_PRODUCT_CP, t)


def cv_J_per_kg_K(temperature_K: float, burned_fraction: float = 0.0) -> float:
    """Constant-volume specific heat of the charge [J/kg/K]."""

    return (cp_J_per_kg_K(temperature_K, burned_fraction)
            - mixture_gas_constant(burned_fraction))


def gamma(temperature_K: float, burned_fraction: float = 0.0) -> float:
    """Ratio of specific heats at this temperature and composition."""

    cp = cp_J_per_kg_K(temperature_K, burned_fraction)
    return cp / (cp - mixture_gas_constant(burned_fraction))


def internal_energy_J_per_kg(temperature_K: float,
                             burned_fraction: float = 0.0) -> float:
    """Specific internal energy relative to :data:`REFERENCE_TEMPERATURE_K`.

    ``u(T) = integral of cv dT`` from the datum, evaluated analytically from the
    fitted cp polynomial less ``R T``.
    """

    if temperature_K <= 0.0:
        raise ValueError("temperature_K must be positive.")
    x = _clamp_fraction(burned_fraction)
    r = mixture_gas_constant(x)
    t = _clamp_temperature(temperature_K) / 1000.0
    t0 = REFERENCE_TEMPERATURE_K / 1000.0

    enthalpy = ((1.0 - x) * (_poly_integral(_AIR_CP, t) - _poly_integral(_AIR_CP, t0))
                + x * (_poly_integral(_PRODUCT_CP, t) - _poly_integral(_PRODUCT_CP, t0)))
    return enthalpy - r * (_clamp_temperature(temperature_K) - REFERENCE_TEMPERATURE_K)


def temperature_from_internal_energy(internal_energy_J_per_kg_: float,
                                     burned_fraction: float = 0.0,
                                     guess_K: float = 1000.0,
                                     tolerance_K: float = 1e-6,
                                     max_iterations: int = 30) -> float:
    """Invert ``u(T)`` for temperature by Newton iteration.

    ``cv`` is the exact derivative of ``u``, so with a decent starting guess
    this lands in one or two steps. The integrator marches internal energy
    rather than temperature — that is what keeps energy conserved by
    construction — and hands in its explicit estimate of the new temperature as
    the guess, which is almost always already within a kelvin.

    A tolerance of 1e-6 K is ~5e-10 relative at combustion temperatures, far
    tighter than the physics and well inside the fit's own accuracy.
    """

    x = _clamp_fraction(burned_fraction)
    r = mixture_gas_constant(x)
    # Blend the two compositions' coefficients once; the iteration below is then
    # two Horner evaluations and nothing else.
    y = 1.0 - x
    cp_c = tuple(y * a + x * b for a, b in zip(_AIR_CP, _PRODUCT_CP))
    int_c = tuple(y * a + x * b for a, b in zip(_AIR_CP_INT, _PRODUCT_CP_INT))

    t0 = REFERENCE_TEMPERATURE_K / 1000.0
    # Constant part of u(T): the datum offset, hoisted out of the loop.
    datum = 1000.0 * t0 * _poly(int_c, t0) - r * REFERENCE_TEMPERATURE_K

    t = min(max(guess_K, VALID_MIN_K), VALID_MAX_K)
    for _ in range(max_iterations):
        z = t / 1000.0
        u_here = 1000.0 * z * _poly(int_c, z) - r * t - datum
        slope = _poly(cp_c, z) - r
        if slope <= 0.0:                       # pragma: no cover - cv is never <= 0 here
            raise ValueError("Non-physical specific heat during inversion.")
        step = (u_here - internal_energy_J_per_kg_) / slope
        t -= step
        # Keep the iterate inside the range the fit is valid over.
        t = min(max(t, VALID_MIN_K), VALID_MAX_K)
        if abs(step) < tolerance_K:
            return t
    return t


def entropy_function_J_per_kg_K(temperature_K: float,
                                burned_fraction: float = 0.0) -> float:
    """The temperature part of specific entropy, ``phi(T) = integral cp dT / T``.

    With variable specific heats an isentropic change is no longer
    ``T p**((1-g)/g) = const``. The exact statement is that
    ``phi(T) - R ln p`` is conserved, so ``phi`` is what an isentropic
    compression needs. Integrating the fitted polynomial gives a closed form:
    the constant term contributes a logarithm and every higher term integrates
    to ``c_i x**i / i``.
    """

    if temperature_K <= 0.0:
        raise ValueError("temperature_K must be positive.")
    x = _clamp_fraction(burned_fraction)
    z = _clamp_temperature(temperature_K) / 1000.0
    coeffs = tuple((1.0 - x) * a + x * b for a, b in zip(_AIR_CP, _PRODUCT_CP))

    total = coeffs[0] * math.log(z)
    for i, c in enumerate(coeffs[1:], start=1):
        total += c * z ** i / i
    return total


def isentropic_temperature_K(from_temperature_K: float,
                             from_pressure_Pa: float,
                             to_pressure_Pa: float,
                             burned_fraction: float = 0.0,
                             tolerance_K: float = 1e-6,
                             max_iterations: int = 40) -> float:
    """Temperature after an isentropic change of pressure.

    Solves ``phi(T2) = phi(T1) + R ln(p2 / p1)`` by Newton, using
    ``dphi/dT = cp / T`` as the derivative. This is what compresses the unburned
    zone in the two-zone model, and it is the reason the end-gas temperature can
    be reported as a computed quantity rather than a proxy.
    """

    if from_pressure_Pa <= 0.0 or to_pressure_Pa <= 0.0:
        raise ValueError("Pressures must be positive.")

    x = _clamp_fraction(burned_fraction)
    r = mixture_gas_constant(x)
    target = (entropy_function_J_per_kg_K(from_temperature_K, x)
              + r * math.log(to_pressure_Pa / from_pressure_Pa))

    # Constant-gamma answer is an excellent starting guess.
    g = gamma(from_temperature_K, x)
    t = from_temperature_K * (to_pressure_Pa / from_pressure_Pa) ** ((g - 1.0) / g)
    t = min(max(t, VALID_MIN_K), VALID_MAX_K)

    for _ in range(max_iterations):
        residual = entropy_function_J_per_kg_K(t, x) - target
        slope = cp_J_per_kg_K(t, x) / t
        step = residual / slope
        t -= step
        t = min(max(t, VALID_MIN_K), VALID_MAX_K)
        if abs(step) < tolerance_K:
            return t
    return t


#: Below this burned fraction the burned zone is too small to carry a
#: meaningful temperature, and above ``1 - it`` the unburned zone is. Outside
#: the band the cylinder is treated as a single zone.
TWO_ZONE_MIN_FRACTION = 1.0e-3


def two_zone_state(volume_m3: float,
                   internal_energy_J: float,
                   mass_kg: float,
                   burned_fraction: float,
                   unburned_reference_temperature_K: float,
                   unburned_reference_pressure_Pa: float,
                   pressure_guess_Pa: float,
                   tolerance: float = 1e-8,
                   max_iterations: int = 12) -> tuple[float, float, float]:
    """Split the cylinder into burned and unburned zones at a common pressure.

    A flame front does not raise the whole cylinder to one temperature. Behind
    it sits burned gas, far hotter than the mean; ahead of it sits unburned
    end-gas, merely compressed by the pressure the flame is generating. That
    end-gas is what knocks, so its temperature is worth computing properly
    rather than approximating from the bulk.

    Both zones share the cylinder pressure, which makes the system close on a
    single unknown. For a trial pressure:

    * the unburned zone has only been compressed, so its temperature follows the
      isentropic relation from the intake-valve-close state;
    * its volume then follows from the ideal-gas law, and the burned zone takes
      whatever volume is left;
    * the burned temperature follows from *its* ideal-gas law.

    That gives a total internal energy for the trial pressure. Internal energy
    rises monotonically with pressure here, so a secant iteration on the
    pressure recovers the state that matches the energy the march has arrived
    at. Returns ``(pressure_Pa, unburned_temperature_K, burned_temperature_K)``.
    """

    x = _clamp_fraction(burned_fraction)
    m_u = (1.0 - x) * mass_kg
    m_b = x * mass_kg

    def energy_at(pressure: float) -> tuple[float, float, float]:
        t_u = isentropic_temperature_K(
            unburned_reference_temperature_K, unburned_reference_pressure_Pa,
            pressure, 0.0,
        )
        v_u = m_u * R_AIR * t_u / pressure
        v_b = volume_m3 - v_u
        if v_b <= 0.0:
            # The unburned zone alone would fill the cylinder; hold a sliver for
            # the burned gas so the solve stays finite.
            v_b = 1.0e-12 * volume_m3
        t_b = pressure * v_b / (m_b * R_PRODUCT)
        t_b = min(max(t_b, VALID_MIN_K), VALID_MAX_K)
        total = m_u * internal_energy_J_per_kg(t_u, 0.0) + m_b * internal_energy_J_per_kg(t_b, 1.0)
        return total, t_u, t_b

    p0 = max(pressure_guess_Pa, 1.0)
    f0, t_u, t_b = energy_at(p0)
    p1 = p0 * 1.02
    f1, _, _ = energy_at(p1)

    for _ in range(max_iterations):
        denom = f1 - f0
        if abs(denom) < 1e-30:
            break
        p2 = p1 - (f1 - internal_energy_J) * (p1 - p0) / denom
        # Keep the iterate positive and from running away on a bad secant step.
        p2 = min(max(p2, 0.25 * p1), 4.0 * p1)
        p0, f0 = p1, f1
        p1 = p2
        f1, t_u, t_b = energy_at(p1)
        if abs(f1 - internal_energy_J) <= tolerance * max(1.0, abs(internal_energy_J)):
            break

    return p1, t_u, t_b


def _clamp_fraction(burned_fraction: float) -> float:
    return min(1.0, max(0.0, burned_fraction))


def _clamp_temperature(temperature_K: float) -> float:
    """Hold the polynomial inside the window it was fitted over.

    Beyond the fitted range the charge would be dissociating heavily, which
    this frozen composition does not model, so extrapolating the fit would add
    error rather than remove it.
    """

    return min(max(temperature_K, VALID_MIN_K), VALID_MAX_K)
