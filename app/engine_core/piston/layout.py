"""Engine layout: cylinder arrangement, firing intervals and inertia balance.

The cycle solver in :mod:`cycle` models one representative cylinder and scales
by cylinder count, which is the right reduced-order call for thermodynamics —
every cylinder runs the same cycle. But *how those cylinders are arranged*
changes three things that are genuinely computable, and this module computes
them.

Firing intervals
----------------
A four-stroke fires ``n`` times per 720 deg of crank, so the even-fire interval
is ``720 / n``. Whether a given layout actually achieves it depends on the bank
angle and the crankpin arrangement. A V engine whose two banks share a crankpin
fires the pair ``V`` degrees apart, so the intervals alternate between ``V`` and
``2 * ideal - V``: even-fire exactly when ``V == ideal``. That single relation
reproduces the familiar cases — a 90 deg V8 (ideal 90) is even-fire, a 90 deg V6
(ideal 120) is the classic 90/150 odd-fire, and a split (offset) crankpin adds
its offset to the effective bank angle to bring an odd-fire V back to even.

Reciprocating balance
---------------------
For each cylinder the reciprocating inertia force acts along that cylinder's
bore axis with the standard two-term expansion::

    F(theta) ~ cos(theta + phi) + (1 / R) * cos(2 * (theta + phi))
               \\________________/   \\_____________________________/
                    primary                    secondary

where ``R`` is the rod ratio ``L/a`` and ``phi`` is the crank phase of that
cylinder *measured relative to its own bore axis* (a boxer's opposed pair has
pins 180 deg apart and axes 180 deg apart, so both pistons reach TDC together
and share a phase — which is exactly why a boxer cancels where a 180 deg V does
not).

Summing those force vectors over the cylinders gives the net shaking force;
weighting by each cylinder's axial station along the crankshaft before summing
gives the shaking couple. Both are evaluated numerically over a full rotation
and reported as dimensionless residuals, normalised so that a single cylinder
scores 1.0 and perfect cancellation scores 0.0. Nothing here is fitted: the
numbers fall out of the geometry.

The one place a *model parameter* enters is the friction scale, which is a
coarse bearing- and head-count correction relative to an inline-four reference.
It is labelled as such and is not measured for any engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Layout kinds. "flat" is a true boxer (opposed cylinders on separate crankpins
# 180 deg apart), which is mechanically distinct from a 180 deg V sharing pins.
LAYOUT_KINDS = ("single", "inline", "vee", "flat", "w", "radial")

# Crank plane. A flat-plane crank spaces its throws over the *firing* cycle
# (720 / throws, so a four-throw crank lands on 0/180); a cross-plane crank
# spaces them over the *rotation* (360 / throws, landing on 0/90/180/270). That
# single difference is the whole flat-plane-vs-cross-plane V8 argument: the
# cross-plane arrangement cancels the secondary shaking force the flat-plane
# leaves behind, at the cost of a heavier counterweighted crank.
CRANK_TYPES = ("flat_plane", "cross_plane")

# Banks (cylinder rows) per layout kind.
_BANKS = {"single": 1, "inline": 1, "vee": 2, "flat": 2, "w": 4, "radial": 1}

# Axial offset between banks, in bore-spacing units. Two cylinders sharing a
# crank throw cannot occupy the same axial station -- their rods sit side by
# side on the pin. That small offset is what turns an otherwise cancelling pair
# into a rocking couple, so it is modelled rather than idealised away.
_BANK_AXIAL_OFFSET = 0.125

# Samples per crank revolution when searching for the peak residual. 720 gives
# half-degree resolution, well past what the reported precision needs.
_BALANCE_SAMPLES = 720

# Friction scale reference: an inline-four has 5 main bearings and 1 head.
_REF_BEARINGS = 5.0


@dataclass(slots=True, frozen=True)
class Cylinder:
    """One cylinder's placement, as the balance sum needs it.

    ``axis_deg`` is the bore axis direction measured from vertical (positive
    toward +x), ``pin_deg`` is the crankpin's angular position, and
    ``phase_deg`` is the crank phase relative to this cylinder's own axis --
    the quantity that actually drives its piston. ``station`` is the axial
    position along the crankshaft in bore-spacing units, measured from the
    engine's axial centre.
    """

    index: int
    bank: int
    axis_deg: float
    pin_deg: float
    phase_deg: float
    station: float


@dataclass(slots=True, frozen=True)
class EngineLayout:
    """A cylinder arrangement, and everything derivable from it."""

    kind: str = "inline"
    cylinders: int = 4
    bank_angle_deg: float = 0.0          # included angle between banks (V/W)
    crankpin_offset_deg: float = 0.0     # split-pin offset, brings odd-fire V back to even
    strokes_per_cycle: int = 4
    rod_ratio: float = 3.5
    crank_type: str = "flat_plane"       # flat_plane | cross_plane

    def __post_init__(self) -> None:
        if self.kind not in LAYOUT_KINDS:
            raise ValueError(f"kind must be one of {LAYOUT_KINDS}.")
        if self.crank_type not in CRANK_TYPES:
            raise ValueError(f"crank_type must be one of {CRANK_TYPES}.")
        if self.cylinders < 1:
            raise ValueError("cylinders must be >= 1.")
        if self.strokes_per_cycle not in (2, 4):
            raise ValueError("strokes_per_cycle must be 2 or 4.")
        if self.rod_ratio <= 1.0:
            raise ValueError("rod_ratio (L/a) must exceed 1.")
        if not 0.0 <= self.bank_angle_deg <= 180.0:
            raise ValueError("bank_angle_deg must be in [0, 180].")
        if not -180.0 <= self.crankpin_offset_deg <= 180.0:
            raise ValueError("crankpin_offset_deg must be in [-180, 180].")
        if self.kind == "single" and self.cylinders != 1:
            raise ValueError("A single-cylinder layout must have exactly 1 cylinder.")
        if self.kind in ("vee", "flat") and self.cylinders % 2 != 0:
            raise ValueError(f"A {self.kind} layout needs an even cylinder count.")
        if self.kind == "w" and self.cylinders % 4 != 0:
            raise ValueError("A W layout needs a cylinder count divisible by 4.")
        if self.kind == "radial" and self.strokes_per_cycle == 4 and self.cylinders % 2 != 1:
            # A single-row four-stroke radial must have an odd cylinder count or
            # the every-other-cylinder firing sequence cannot close.
            raise ValueError("A four-stroke radial needs an odd cylinder count.")

    # ---------------------------------------------------------------- basics

    @property
    def banks(self) -> int:
        return 1 if self.cylinders == 1 else _BANKS[self.kind]

    @property
    def effective_bank_angle_deg(self) -> float:
        """Included angle actually used by the geometry.

        A boxer is opposed by definition, so its banks are 180 deg apart
        whatever was passed in; a single row has no included angle at all.
        Only V and W layouts take the caller's value.
        """

        if self.kind == "flat":
            return 180.0
        if self.kind in ("single", "inline", "radial"):
            return 0.0
        return self.bank_angle_deg

    @property
    def cylinders_per_bank(self) -> int:
        return self.cylinders // self.banks

    @property
    def crank_throws(self) -> int:
        """Distinct crank throws. V and W layouts share a throw between banks."""

        if self.kind == "radial":
            return 1                      # one master throw, all rods on it
        if self.kind in ("vee", "w", "flat"):
            # A boxer's opposed pair rides one throw station on two pins 180 deg
            # apart, so it counts as a single throw for bearing purposes -- which
            # is why a flat-six runs four mains where an inline-six runs seven.
            return self.cylinders_per_bank
        return self.cylinders             # inline and single

    @property
    def main_bearings(self) -> int:
        """Main bearings, on the usual one-between-each-throw-plus-two rule."""

        if self.kind == "radial":
            return 2
        return self.crank_throws + 1

    @property
    def cylinder_heads(self) -> int:
        return self.banks

    @property
    def ideal_firing_interval_deg(self) -> float:
        """Crank degrees between firings if the engine is perfectly even-fire."""

        degrees_per_cycle = 360.0 * (self.strokes_per_cycle / 2.0)
        return degrees_per_cycle / self.cylinders

    # ------------------------------------------------------- cylinder layout

    def throw_angles_deg(self) -> list[float]:
        """Crank throw angles, ordered along the crankshaft.

        The angles themselves come from the crank plane; the *order* is chosen
        the way real cranks are ordered — mirror-symmetric about the middle, so
        that equal and opposite inertia forces act at equal and opposite
        stations and the rocking couples cancel. An inline-six's classic
        0-120-240-240-120-0 arrangement is exactly this rule applied to three
        throw angles, and it is why an inline-six has no couple to balance.
        """

        throws = self.crank_throws
        per_cycle = 360.0 * (self.strokes_per_cycle / 2.0)
        if self.kind == "flat":
            # Each bank of a boxer fires at the engine's own even-fire interval
            # (its opposed partner takes the other revolution), so the bank's
            # throws step by 720/n, not 720/throws.
            base = [(per_cycle * j / self.cylinders) % 360.0 for j in range(throws)]
        elif self.crank_type == "cross_plane":
            base = [(360.0 * j / throws) % 360.0 for j in range(throws)]
        else:
            base = [(per_cycle * j / throws) % 360.0 for j in range(throws)]
        return _mirror_order(base)

    def cylinder_map(self) -> list[Cylinder]:
        """Every cylinder's axis, crankpin and axial station."""

        n = self.cylinders
        per_cycle = 360.0 * (self.strokes_per_cycle / 2.0)

        if self.kind == "radial":
            # One throw; cylinders spread evenly around it.
            return [
                Cylinder(
                    index=i, bank=0,
                    axis_deg=(360.0 * i / n),
                    pin_deg=0.0,
                    phase_deg=(-360.0 * i / n) % 360.0,
                    station=0.0,
                )
                for i in range(n)
            ]

        banks = self.banks
        per_bank = self.cylinders_per_bank

        # Bank axis directions, symmetric about vertical.
        if banks == 1:
            axes = [0.0]
        elif banks == 2:
            half = self.effective_bank_angle_deg / 2.0
            axes = [-half, +half]
        else:                                   # W: two narrow-angle pairs
            half = self.effective_bank_angle_deg / 2.0
            narrow = self.effective_bank_angle_deg / 6.0 or 7.5
            axes = [-half - narrow, -half + narrow, +half - narrow, +half + narrow]

        throw_angles = self.throw_angles_deg()
        shared_pins = self.crank_throws != n
        cylinders: list[Cylinder] = []
        for b in range(banks):
            for j in range(per_bank):
                # A V/W shares one throw between banks; an inline or boxer gives
                # every cylinder its own, so its throws are indexed bank-major.
                pin = throw_angles[j if shared_pins else b * per_bank + j]

                if self.kind == "flat":
                    # A boxer's opposed cylinder rides its own pin, 180 deg
                    # around, so both pistons of a pair reach TDC together.
                    pin = (pin + 180.0 * b) % 360.0
                elif shared_pins and b > 0:
                    # Split-pin offset, applied to the trailing bank(s).
                    pin = (pin + self.crankpin_offset_deg * b) % 360.0

                axis = axes[b]
                # Station: cylinders march along the crank, banks sit a little
                # apart axially because their rods share the pin.
                station = (j - (per_bank - 1) / 2.0)
                if banks > 1:
                    station += _BANK_AXIAL_OFFSET * (b - (banks - 1) / 2.0)

                cylinders.append(Cylinder(
                    index=len(cylinders), bank=b,
                    axis_deg=axis, pin_deg=pin,
                    phase_deg=(pin - axis) % 360.0,
                    station=station,
                ))
        return cylinders

    # ------------------------------------------------------- firing sequence

    def firing_angles_deg(self) -> list[float]:
        """Crank angle of each firing event over one full cycle, sorted.

        Two cases, both derived rather than tabulated:

        * **A throw per cylinder** (inline, boxer, single). Every cylinder owns
          its own crankpin, so the throws can be — and are — laid out to fire at
          the ideal interval. Events land on ``j * per_cycle / n``.
        * **A throw shared between banks** (V, W). The cylinders on a shared pin
          reach TDC as the pin sweeps past each bank axis, so they fire one bank
          separation apart. A split (offset) crankpin adds its offset to that
          separation, which is exactly how an odd-fire V is brought back to even.
        """

        per_cycle = 360.0 * (self.strokes_per_cycle / 2.0)
        n = self.cylinders

        if self.kind in ("single", "inline", "flat", "radial"):
            # Radials fire alternate cylinders around the row; inlines and
            # boxers give every cylinder a pin that can be timed freely. All
            # are even-fire.
            return [per_cycle * j / n for j in range(n)]

        # Shared-pin V/W: bank separations from the bank axes, plus split pins.
        banks = self.banks
        half = self.effective_bank_angle_deg / 2.0
        if banks == 2:
            axes = [-half, +half]
        else:
            narrow = self.effective_bank_angle_deg / 6.0 or 7.5
            axes = [-half - narrow, -half + narrow, +half - narrow, +half + narrow]

        throws = self.crank_throws
        events: list[float] = []
        for j in range(throws):
            base = per_cycle * j / throws
            for b in range(banks):
                separation = (axes[b] - axes[0]) + self.crankpin_offset_deg * b
                events.append((base + separation) % per_cycle)
        return sorted(events)

    def firing_intervals_deg(self) -> list[float]:
        """Gaps between consecutive firings over one full cycle."""

        per_cycle = 360.0 * (self.strokes_per_cycle / 2.0)
        events = self.firing_angles_deg()
        if len(events) == 1:
            return [per_cycle]
        return [
            (events[(i + 1) % len(events)] - events[i]) % per_cycle
            for i in range(len(events))
        ]

    def is_even_fire(self, tolerance_deg: float = 0.5) -> bool:
        ideal = self.ideal_firing_interval_deg
        return all(abs(g - ideal) <= tolerance_deg for g in self.firing_intervals_deg())

    # --------------------------------------------------------------- balance

    def balance(self) -> dict[str, float]:
        """Dimensionless shaking-force and shaking-couple residuals.

        Each is the peak over one crank revolution of the summed inertia
        contribution, normalised so a single cylinder reads 1.0 and perfect
        cancellation reads 0.0. The secondary numbers are *shape* factors: the
        physical secondary force is this times ``1 / rod_ratio``, which is
        reported separately as ``secondary_force_ratio``.
        """

        cyls = self.cylinder_map()
        n = float(len(cyls))
        station_norm = sum(abs(c.station) for c in cyls)

        peak_pf = peak_sf = peak_pc = peak_sc = 0.0
        for k in range(_BALANCE_SAMPLES):
            theta = 2.0 * math.pi * k / _BALANCE_SAMPLES
            pfx = pfy = sfx = sfy = 0.0
            pcx = pcy = scx = scy = 0.0
            for c in cyls:
                phase = math.radians(c.phase_deg)
                axis = math.radians(c.axis_deg)
                ux, uy = math.sin(axis), math.cos(axis)
                primary = math.cos(theta + phase)
                secondary = math.cos(2.0 * (theta + phase))
                pfx += primary * ux
                pfy += primary * uy
                sfx += secondary * ux
                sfy += secondary * uy
                pcx += c.station * primary * ux
                pcy += c.station * primary * uy
                scx += c.station * secondary * ux
                scy += c.station * secondary * uy
            peak_pf = max(peak_pf, math.hypot(pfx, pfy))
            peak_sf = max(peak_sf, math.hypot(sfx, sfy))
            peak_pc = max(peak_pc, math.hypot(pcx, pcy))
            peak_sc = max(peak_sc, math.hypot(scx, scy))

        cnorm = station_norm if station_norm > 1e-12 else 1.0
        return {
            "primary_force": peak_pf / n,
            "secondary_force": peak_sf / n,
            "primary_couple": peak_pc / cnorm if station_norm > 1e-12 else 0.0,
            "secondary_couple": peak_sc / cnorm if station_norm > 1e-12 else 0.0,
            "secondary_force_ratio": (peak_sf / n) / self.rod_ratio,
        }

    def balance_verdict(self) -> str:
        """One honest sentence about what this arrangement shakes."""

        b = self.balance()
        tol = 0.02
        shakes: list[str] = []
        if b["primary_force"] > tol:
            shakes.append("a primary shaking force")
        if b["secondary_force"] > tol:
            shakes.append("a secondary shaking force")
        if b["primary_couple"] > tol:
            shakes.append("a primary rocking couple")
        if b["secondary_couple"] > tol:
            shakes.append("a secondary rocking couple")
        if not shakes:
            return "Inherently balanced: primary and secondary forces and couples all cancel."
        if len(shakes) == 1:
            return f"Leaves {shakes[0]}; everything else cancels."
        return "Leaves " + ", ".join(shakes[:-1]) + f" and {shakes[-1]}."

    # -------------------------------------------------------------- friction

    def friction_scale(self) -> float:
        """Coarse FMEP scale for this arrangement, inline-four = 1.0.

        More main bearings mean more rubbing; more cylinder heads mean more
        valvetrain to drive. This is a **model parameter**, not a measurement:
        it is a two-term linear correction anchored so the inline-four
        reference returns exactly 1.0.
        """

        bearing_term = 0.70 + 0.30 * (self.main_bearings / _REF_BEARINGS)
        head_term = 1.0 + 0.06 * (self.cylinder_heads - 1)
        return bearing_term * head_term

    # ---------------------------------------------------------------- report

    def to_dict(self) -> dict[str, Any]:
        intervals = self.firing_intervals_deg()
        balance = self.balance()
        return {
            "kind": self.kind,
            "cylinders": self.cylinders,
            "banks": self.banks,
            "cylinders_per_bank": self.cylinders_per_bank,
            "bank_angle_deg": self.bank_angle_deg,
            "crankpin_offset_deg": self.crankpin_offset_deg,
            "crank_throws": self.crank_throws,
            "main_bearings": self.main_bearings,
            "cylinder_heads": self.cylinder_heads,
            "ideal_firing_interval_deg": self.ideal_firing_interval_deg,
            "firing_intervals_deg": [round(g, 3) for g in intervals],
            "even_fire": self.is_even_fire(),
            "balance": {k: round(v, 6) for k, v in balance.items()},
            "balance_verdict": self.balance_verdict(),
            "friction_scale": round(self.friction_scale(), 4),
            "description": self.describe(),
        }

    def describe(self) -> str:
        """Human name for the arrangement, e.g. '90 deg V8' or 'flat-6'."""

        n = self.cylinders
        if self.kind == "single":
            return "single cylinder"
        if self.kind == "inline":
            return f"inline-{n}"
        if self.kind == "flat":
            return f"flat-{n}"
        if self.kind == "radial":
            return f"{n}-cylinder radial"
        if self.kind == "w":
            return f"W{n} ({self.bank_angle_deg:g} deg)"
        return f"{self.bank_angle_deg:g} deg V{n}"


def _mirror_order(angles: list[float]) -> list[float]:
    """Order crank throws along the shaft so rocking couples cancel.

    Two structural cases, both of which real cranks use:

    * **Every angle appears twice** (the usual four-stroke result, e.g. three
      distinct angles across an inline-six's six throws). Lay them out as a
      palindrome, so each pair sits at mirrored stations and its couple
      contributions cancel exactly.
    * **Angles pair up 180 deg apart** (a cross-plane crank's 0/90/180/270).
      Place each opposed pair at mirrored stations, widest pair outermost. For a
      four-throw cross-plane crank this reproduces 0-90-270-180 — the real
      cross-plane V8 arrangement.

    Anything else (an odd cylinder count, where the angles are distinct and have
    no 180 deg partner) genuinely cannot cancel, and is left in natural order.
    """

    n = len(angles)
    if n < 2:
        return list(angles)

    rounded = [round(a, 6) for a in angles]
    counts: dict[float, int] = {}
    for a in rounded:
        counts[a] = counts.get(a, 0) + 1

    # Case 1: every angle appears exactly twice -> palindrome.
    if n % 2 == 0 and all(c == 2 for c in counts.values()):
        half = sorted(counts)
        return half + half[::-1]

    # Case 2: angles pair up 180 deg apart -> mirrored opposed pairs.
    if n % 2 == 0 and len(counts) == n:
        remaining = sorted(counts)
        pairs: list[tuple[float, float]] = []
        while remaining:
            a = remaining.pop(0)
            partner = next(
                (x for x in remaining if abs(((x - a) % 360.0) - 180.0) < 1e-6), None
            )
            if partner is None:
                break
            remaining.remove(partner)
            pairs.append((a, partner))
        if len(pairs) == n // 2:
            front = [p[0] for p in pairs]
            back = [p[1] for p in pairs]
            return front + back[::-1]

    return list(angles)


def even_fire_bank_angle_deg(cylinders: int, strokes_per_cycle: int = 4) -> float:
    """Bank angle that makes a shared-crankpin V engine even-fire.

    Falls straight out of the firing relation: the pair on a shared pin fires
    ``V`` apart, so ``V`` must equal the ideal interval ``720 / n``. This is why
    a V8 wants 90 deg, a V6 wants 120 deg and a V12 wants 60 deg.
    """

    if cylinders < 2 or cylinders % 2 != 0:
        raise ValueError("A V engine needs an even cylinder count of at least 2.")
    degrees_per_cycle = 360.0 * (strokes_per_cycle / 2.0)
    return degrees_per_cycle / cylinders
