from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "astrology" / "skills" / "synastry" / "scripts"))

from astro_math import (
    ASPECT_KINDS,
    SIGNS,
    degrees_in_sign,
    dignities,
    find_aspects,
    format_degrees,
    house_of,
    is_critical,
    is_diurnal,
    lots,
    normalize,
    separation,
    sign_of,
)

# Thirty-degree cusps: house N starts at (N - 1) * 30, which makes every
# expectation below readable without a chart in front of you.
EQUAL_CUSPS = [index * 30.0 for index in range(12)]


class DegreeTests(unittest.TestCase):
    def test_normalize_folds_both_directions(self) -> None:
        self.assertAlmostEqual(normalize(370.5), 10.5)
        self.assertAlmostEqual(normalize(-10.0), 350.0)
        self.assertAlmostEqual(normalize(0.0), 0.0)

    def test_sign_and_offset_partition_the_circle(self) -> None:
        for index, sign in enumerate(SIGNS):
            longitude = index * 30.0 + 15.0
            self.assertEqual(sign_of(longitude), sign)
            self.assertAlmostEqual(degrees_in_sign(longitude), 15.0)

    def test_format_carries_a_rounded_sixty_upward(self) -> None:
        """59.9 arc-minutes rounds to 60, which is the next degree, not `12°60'`."""

        self.assertEqual(format_degrees(12.5), "12°30'")
        self.assertEqual(format_degrees(12.999), "13°00'")
        self.assertEqual(format_degrees(0.0), "0°00'")

    def test_separation_never_exceeds_half_a_circle(self) -> None:
        self.assertAlmostEqual(separation(10.0, 350.0), 20.0)
        self.assertAlmostEqual(separation(350.0, 10.0), 20.0)
        self.assertAlmostEqual(separation(0.0, 180.0), 180.0)
        self.assertAlmostEqual(separation(0.0, 200.0), 160.0)


class HouseTests(unittest.TestCase):
    def test_each_house_holds_its_own_arc(self) -> None:
        for number in range(1, 13):
            self.assertEqual(house_of((number - 1) * 30.0 + 1.0, EQUAL_CUSPS), number)

    def test_a_cusp_belongs_to_the_house_it_opens(self) -> None:
        self.assertEqual(house_of(30.0, EQUAL_CUSPS), 2)

    def test_the_house_wrapping_zero_is_found(self) -> None:
        """A rotated chart puts one house across the 0° seam, where a naive scan fails."""

        rotated = [normalize(340.0 + index * 30.0) for index in range(12)]
        self.assertEqual(house_of(345.0, rotated), 1)
        self.assertEqual(house_of(5.0, rotated), 1)
        self.assertEqual(house_of(335.0, rotated), 12)

    def test_a_malformed_cusp_list_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            house_of(10.0, [0.0, 30.0])
        with self.assertRaises(ValueError):
            house_of(10.0, [0.0] * 12)


class DignityTests(unittest.TestCase):
    def test_classical_assignments_hold(self) -> None:
        self.assertEqual(dignities("Sun", "Leo"), ("domicile",))
        self.assertEqual(dignities("Sun", "Lib"), ("fall",))
        self.assertEqual(dignities("Saturn", "Can"), ("detriment",))

    def test_mercury_holds_two_states_in_virgo_in_a_fixed_order(self) -> None:
        self.assertEqual(dignities("Mercury", "Vir"), ("domicile", "exaltation"))

    def test_a_body_outside_the_classical_seven_holds_none(self) -> None:
        """Uranus in Aquarius is a modern rulership, and stating it would assert a school."""

        self.assertEqual(dignities("Uranus", "Aqu"), ())
        self.assertEqual(dignities("Ceres", "Vir"), ())

    def test_critical_degrees_are_the_first_and_last_of_a_sign(self) -> None:
        self.assertTrue(is_critical(0.4))
        self.assertTrue(is_critical(29.9))
        self.assertFalse(is_critical(15.0))
        self.assertTrue(is_critical(330.2))


class SectAndLotTests(unittest.TestCase):
    def test_sect_follows_the_horizon_not_the_clock(self) -> None:
        self.assertTrue(is_diurnal(200.0, EQUAL_CUSPS))
        self.assertFalse(is_diurnal(20.0, EQUAL_CUSPS))

    def test_fortune_and_spirit_swap_between_sects(self) -> None:
        arguments = dict(ascendant=100.0, sun=200.0, moon=50.0, venus=170.0, jupiter=10.0, saturn=300.0)
        day = lots(**arguments, diurnal=True)
        night = lots(**arguments, diurnal=False)

        self.assertAlmostEqual(day["Lot_of_Fortune"], night["Lot_of_Spirit"])
        self.assertAlmostEqual(day["Lot_of_Spirit"], night["Lot_of_Fortune"])

    def test_every_lot_lands_on_the_circle(self) -> None:
        computed = lots(
            ascendant=350.0,
            sun=20.0,
            moon=340.0,
            venus=5.0,
            jupiter=300.0,
            saturn=100.0,
            diurnal=False,
        )
        self.assertEqual(len(computed), 6)
        for value in computed.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLess(value, 360.0)


class AspectTests(unittest.TestCase):
    def test_an_exact_contact_of_each_kind_is_named(self) -> None:
        for kind in ASPECT_KINDS:
            found = find_aspects({"Sun": 0.0}, {"Moon": kind.angle}, major_orb=8.0, minor_orb=3.0)
            self.assertEqual([aspect.kind for aspect in found], [kind.name], kind.name)
            self.assertAlmostEqual(found[0].orb, 0.0)

    def test_the_two_orbs_are_applied_separately(self) -> None:
        """A 5° miss is inside the Ptolemaic orb and outside the minor one."""

        square = find_aspects({"Sun": 0.0}, {"Moon": 95.0}, major_orb=8.0, minor_orb=3.0)
        self.assertEqual([aspect.kind for aspect in square], ["square"])

        quincunx = find_aspects({"Sun": 0.0}, {"Moon": 155.0}, major_orb=8.0, minor_orb=3.0)
        self.assertEqual(quincunx, [])

    def test_nothing_is_reported_beyond_both_orbs(self) -> None:
        self.assertEqual(find_aspects({"Sun": 0.0}, {"Moon": 20.0}, major_orb=8.0, minor_orb=3.0), [])

    def test_both_sides_are_compared_in_full(self) -> None:
        """Asteroid to asteroid is found on the same pass, which the old engine skipped."""

        found = find_aspects(
            {"Juno": 10.0, "Sun": 100.0},
            {"Juno": 12.0, "Vesta": 280.0},
            major_orb=8.0,
            minor_orb=3.0,
        )
        pairs = {(aspect.left, aspect.right, aspect.kind) for aspect in found}
        self.assertIn(("Juno", "Juno", "conjunction"), pairs)
        self.assertIn(("Sun", "Vesta", "opposition"), pairs)

    def test_results_are_ordered_by_orb_and_stable_on_ties(self) -> None:
        found = find_aspects(
            {"Sun": 0.0, "Mars": 0.0},
            {"Moon": 4.0, "Venus": 1.0},
            major_orb=8.0,
            minor_orb=3.0,
        )
        orbs = [round(aspect.orb, 6) for aspect in found]
        self.assertEqual(orbs, sorted(orbs))
        self.assertEqual(found, find_aspects({"Sun": 0.0, "Mars": 0.0}, {"Moon": 4.0, "Venus": 1.0}))

    def test_a_contact_is_named_once_by_its_closest_kind(self) -> None:
        """46° is inside a semi-square orb and nowhere near anything else."""

        found = find_aspects({"Sun": 0.0}, {"Moon": 46.0}, major_orb=8.0, minor_orb=3.0)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "semi-square")


if __name__ == "__main__":
    unittest.main()
