"""Engine layout: firing intervals and reciprocating balance.

Every assertion here is a result that can be derived from the geometry rather
than looked up, which is the point: the module computes balance from cylinder
axes and crank phases, so the classic engines have to fall out of it. If an
inline-six stops reading "perfectly balanced" or an inline-four stops showing a
unit secondary shaking force, the geometry is wrong.
"""

from __future__ import annotations

import pytest

from app.engine_core.piston.layout import (
    EngineLayout,
    even_fire_bank_angle_deg,
)

TOL = 1e-6


def _inline(n: int) -> EngineLayout:
    return EngineLayout(kind="inline", cylinders=n)


# --------------------------------------------------------------- balance

def test_single_cylinder_is_the_unit_of_imbalance() -> None:
    # The normalisation is defined so one cylinder scores 1.0 on both orders,
    # and a lone cylinder has no lever arm so it cannot rock.
    b = EngineLayout(kind="single", cylinders=1).balance()
    assert b["primary_force"] == pytest.approx(1.0, abs=1e-6)
    assert b["secondary_force"] == pytest.approx(1.0, abs=1e-6)
    assert b["primary_couple"] == pytest.approx(0.0, abs=TOL)


def test_inline_four_cancels_primary_but_leaves_a_full_secondary_force() -> None:
    # The textbook inline-four: pistons pair up so the primary forces cancel,
    # but all four secondaries are in phase and add. This is the entire reason
    # balance shafts exist on large fours.
    b = _inline(4).balance()
    assert b["primary_force"] == pytest.approx(0.0, abs=1e-9)
    assert b["secondary_force"] == pytest.approx(1.0, abs=1e-9)
    assert b["primary_couple"] == pytest.approx(0.0, abs=1e-9)
    assert "secondary shaking force" in _inline(4).balance_verdict()


def test_inline_six_is_inherently_balanced() -> None:
    # Three mirrored throw pairs: forces and couples all cancel to both orders.
    b = _inline(6).balance()
    for key in ("primary_force", "secondary_force", "primary_couple", "secondary_couple"):
        assert b[key] == pytest.approx(0.0, abs=1e-9), key
    assert "balanced" in _inline(6).balance_verdict().lower()


def test_inline_three_balances_forces_but_rocks() -> None:
    # Evenly spaced throws cancel the forces; the outer cylinders are on
    # opposite sides of centre, so the couple survives.
    b = _inline(3).balance()
    assert b["primary_force"] == pytest.approx(0.0, abs=1e-9)
    assert b["secondary_force"] == pytest.approx(0.0, abs=1e-9)
    assert b["primary_couple"] > 0.5
    assert b["secondary_couple"] > 0.5


def test_boxer_twin_balances_forces_and_keeps_a_rocking_couple() -> None:
    # Opposed pistons reach TDC together, so the forces cancel exactly; the two
    # rods cannot share an axial station, and that offset is the couple.
    b = EngineLayout(kind="flat", cylinders=2).balance()
    assert b["primary_force"] == pytest.approx(0.0, abs=1e-9)
    assert b["secondary_force"] == pytest.approx(0.0, abs=1e-9)
    assert b["primary_couple"] > 0.5


def test_flat_six_is_inherently_balanced_on_four_mains() -> None:
    layout = EngineLayout(kind="flat", cylinders=6)
    b = layout.balance()
    for key in ("primary_force", "secondary_force", "primary_couple", "secondary_couple"):
        assert b[key] == pytest.approx(0.0, abs=1e-9), key
    # An opposed pair shares a throw station, so a flat-six runs four mains
    # where an inline-six needs seven.
    assert layout.main_bearings == 4
    assert _inline(6).main_bearings == 7


def test_cross_plane_crank_cancels_the_flat_plane_v8_secondary() -> None:
    flat = EngineLayout(kind="vee", cylinders=8, bank_angle_deg=90)
    cross = EngineLayout(
        kind="vee", cylinders=8, bank_angle_deg=90, crank_type="cross_plane",
    )
    # Flat-plane: throws on 0/180, secondaries survive.
    assert flat.balance()["secondary_force"] > 0.5
    # Cross-plane: throws on 0/90/270/180, secondary shaking force cancels, at
    # the cost of a primary rocking couple the counterweights must carry.
    assert cross.balance()["secondary_force"] == pytest.approx(0.0, abs=1e-9)
    assert cross.balance()["primary_couple"] > 0.1
    assert cross.throw_angles_deg() == [0.0, 90.0, 270.0, 180.0]


def test_secondary_force_ratio_scales_with_rod_ratio() -> None:
    # The physical secondary force is the shape factor over the rod ratio, so a
    # longer rod genuinely shakes less.
    short = EngineLayout(kind="inline", cylinders=4, rod_ratio=3.0).balance()
    long_ = EngineLayout(kind="inline", cylinders=4, rod_ratio=4.0).balance()
    assert short["secondary_force_ratio"] > long_["secondary_force_ratio"]
    assert long_["secondary_force_ratio"] == pytest.approx(1.0 / 4.0, rel=1e-6)


# ------------------------------------------------------- firing intervals

def test_four_stroke_firing_intervals_always_span_one_full_cycle() -> None:
    for layout in (
        _inline(4), _inline(5), _inline(6),
        EngineLayout(kind="flat", cylinders=6),
        EngineLayout(kind="vee", cylinders=6, bank_angle_deg=90),
        EngineLayout(kind="vee", cylinders=8, bank_angle_deg=90),
        EngineLayout(kind="radial", cylinders=9),
    ):
        assert sum(layout.firing_intervals_deg()) == pytest.approx(720.0, abs=1e-6)


def test_ninety_degree_v6_is_the_classic_odd_fire() -> None:
    # Ideal interval is 720/6 = 120, but a shared crankpin fires the pair 90
    # apart, so the events alternate 90/150.
    v6 = EngineLayout(kind="vee", cylinders=6, bank_angle_deg=90)
    assert not v6.is_even_fire()
    assert sorted(set(round(g, 6) for g in v6.firing_intervals_deg())) == [90.0, 150.0]


def test_split_crankpin_brings_the_odd_fire_v6_back_to_even() -> None:
    # Adding a 30 deg pin offset to a 90 deg V6 makes the effective separation
    # 120, which is exactly the ideal interval.
    fixed = EngineLayout(
        kind="vee", cylinders=6, bank_angle_deg=90, crankpin_offset_deg=30,
    )
    assert fixed.is_even_fire()
    assert all(g == pytest.approx(120.0) for g in fixed.firing_intervals_deg())


def test_bank_angle_matching_the_ideal_interval_is_even_fire() -> None:
    # V6 wants 120, V8 wants 90, V12 wants 60 -- all just 720/n.
    for cylinders in (6, 8, 12):
        angle = even_fire_bank_angle_deg(cylinders)
        assert angle == pytest.approx(720.0 / cylinders)
        layout = EngineLayout(kind="vee", cylinders=cylinders, bank_angle_deg=angle)
        assert layout.is_even_fire()


def test_inline_and_boxer_layouts_are_even_fire() -> None:
    for layout in (_inline(3), _inline(4), _inline(6),
                   EngineLayout(kind="flat", cylinders=4),
                   EngineLayout(kind="flat", cylinders=6)):
        assert layout.is_even_fire()
        ideal = layout.ideal_firing_interval_deg
        assert all(g == pytest.approx(ideal) for g in layout.firing_intervals_deg())


def test_two_stroke_fires_twice_as_often() -> None:
    two = EngineLayout(kind="inline", cylinders=2, strokes_per_cycle=2)
    assert two.ideal_firing_interval_deg == pytest.approx(180.0)
    assert sum(two.firing_intervals_deg()) == pytest.approx(360.0)


# --------------------------------------------------------------- friction

def test_friction_scale_is_anchored_on_the_inline_four() -> None:
    assert _inline(4).friction_scale() == pytest.approx(1.0, abs=1e-9)
    # More mains rub more; more heads drive more valvetrain.
    assert _inline(6).friction_scale() > _inline(4).friction_scale()
    assert (EngineLayout(kind="vee", cylinders=8, bank_angle_deg=90).friction_scale()
            > _inline(4).friction_scale())


# ------------------------------------------------------------- validation

@pytest.mark.parametrize("kwargs", [
    {"kind": "banana", "cylinders": 4},
    {"kind": "vee", "cylinders": 5, "bank_angle_deg": 90},      # V needs even count
    {"kind": "w", "cylinders": 6, "bank_angle_deg": 72},        # W needs multiple of 4
    {"kind": "radial", "cylinders": 8},                          # 4-stroke radial is odd
    {"kind": "single", "cylinders": 2},
    {"kind": "inline", "cylinders": 0},
    {"kind": "inline", "cylinders": 4, "rod_ratio": 0.9},
    {"kind": "vee", "cylinders": 8, "bank_angle_deg": 200},
    {"kind": "inline", "cylinders": 4, "strokes_per_cycle": 3},
    {"kind": "inline", "cylinders": 4, "crank_type": "wobble"},
])
def test_invalid_layouts_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        EngineLayout(**kwargs)


def test_boxer_bank_angle_is_always_opposed() -> None:
    # A boxer is 180 deg by definition; a stray input must not un-oppose it.
    assert EngineLayout(kind="flat", cylinders=4, bank_angle_deg=60).effective_bank_angle_deg == 180.0
    assert _inline(4).effective_bank_angle_deg == 0.0


def test_to_dict_reports_the_full_arrangement() -> None:
    payload = EngineLayout(kind="vee", cylinders=8, bank_angle_deg=90).to_dict()
    for key in ("kind", "cylinders", "banks", "crank_throws", "main_bearings",
                "ideal_firing_interval_deg", "firing_intervals_deg", "even_fire",
                "balance", "balance_verdict", "friction_scale", "description"):
        assert key in payload
    assert payload["description"] == "90 deg V8"
    assert payload["banks"] == 2
    assert payload["cylinders_per_bank"] == 4


# --------------------------------------------------------------------------- #
# who fires when: the per-cylinder assignment the 3D engine draws from
# --------------------------------------------------------------------------- #
_EVERY_LAYOUT = [
    dict(kind="single", cylinders=1),
    *[dict(kind="inline", cylinders=n) for n in (2, 3, 4, 5, 6, 8)],
    dict(kind="vee", cylinders=2, bank_angle_deg=90),
    dict(kind="vee", cylinders=2, bank_angle_deg=45),
    dict(kind="vee", cylinders=4, bank_angle_deg=90),
    dict(kind="vee", cylinders=6, bank_angle_deg=60),
    dict(kind="vee", cylinders=6, bank_angle_deg=90, crankpin_offset_deg=30),
    dict(kind="vee", cylinders=6, bank_angle_deg=60, crankpin_offset_deg=60),
    dict(kind="vee", cylinders=8, bank_angle_deg=90, crank_type="cross_plane"),
    dict(kind="vee", cylinders=8, bank_angle_deg=90),
    dict(kind="vee", cylinders=10, bank_angle_deg=72),
    dict(kind="vee", cylinders=12, bank_angle_deg=60),
    dict(kind="vee", cylinders=16, bank_angle_deg=45),
    *[dict(kind="flat", cylinders=n, bank_angle_deg=180) for n in (2, 4, 6, 12)],
]


@pytest.mark.parametrize("spec", _EVERY_LAYOUT, ids=lambda s: f"{s['kind']}{s['cylinders']}")
def test_every_cylinder_fires_at_its_own_tdc(spec) -> None:
    # A cylinder can only fire with its piston at the top, so each assigned
    # firing angle must be a TDC of that cylinder's own crank geometry.
    layout = EngineLayout(**spec)
    for angle, cyl in zip(layout.cylinder_firing_deg(), layout.cylinder_map()):
        off = (angle + cyl.phase_deg) % 360.0
        assert min(off, 360.0 - off) < 0.5, (cyl.index, angle, cyl.phase_deg)


@pytest.mark.parametrize("spec", _EVERY_LAYOUT, ids=lambda s: f"{s['kind']}{s['cylinders']}")
def test_the_assignment_reproduces_the_reported_intervals(spec) -> None:
    # The drawn engine and the console must agree on how evenly it fires.
    layout = EngineLayout(**spec)
    if layout.cylinders == 1:
        return
    angles = sorted(layout.cylinder_firing_deg())
    gaps = sorted(round((b - a) % 720.0, 3) for a, b in zip(angles, angles[1:] + [angles[0] + 720.0]))
    assert gaps == sorted(round(g, 3) for g in layout.firing_intervals_deg())


@pytest.mark.parametrize("spec", _EVERY_LAYOUT, ids=lambda s: f"{s['kind']}{s['cylinders']}")
def test_the_firing_order_is_a_permutation_starting_at_one(spec) -> None:
    order = EngineLayout(**spec).firing_order()
    assert order[0] == 1
    assert sorted(order) == list(range(1, spec["cylinders"] + 1))


def test_a_split_pin_moves_the_pistons_the_same_way_it_moves_the_firing() -> None:
    # Regression: the cylinder map applied the split-pin offset with the
    # opposite sign to firing_angles_deg, so a 90 deg V6 with a 30 deg split
    # was reported even at 120 deg while its pistons, and therefore its
    # balance, reached TDC 60 and 180 deg apart.
    v6 = EngineLayout(kind="vee", cylinders=6, bank_angle_deg=90, crankpin_offset_deg=30)
    tdc = sorted({round((-c.phase_deg) % 360.0, 6) for c in v6.cylinder_map()})
    gaps = {round((b - a) % 360.0, 6) for a, b in zip(tdc, tdc[1:] + [tdc[0] + 360.0])}
    assert gaps == {120.0}


def test_inline_four_pairs_share_tdc_but_not_firing() -> None:
    # Cylinders 1 and 4 are at the top together; only one of them is firing.
    layout = _inline(4)
    fire = layout.cylinder_firing_deg()
    assert abs(((fire[0] - fire[3]) % 720.0) - 360.0) < 1e-6
