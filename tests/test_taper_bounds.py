"""Run in FreeCAD's Python environment. Tests for 0.12.9: chamfered pulls and slots
(also at a panel edge) export at exact size, taper levels off the 0.0001 mm grid,
spline edges and chamfer faces that are really lines, arcs and tapers, and layer tokens.
0.12.10: pulls that a panel edge cuts off-centre (paired pulls centred on the gap between
two panels) are rebuilt exactly by the reconstruction check."""
import math
import unittest
from pathlib import Path

import FreeCAD as App
import Part

MACRO = Path(__file__).resolve().parents[1] / 'FreeCAD_Lay_Flat_for_CNC.FCMacro'
macro = {'__name__': 'layflat_test', '__file__': str(MACRO)}
exec(compile(MACRO.read_text(), str(MACRO), 'exec'), macro)
Z = App.Vector(0, 0, 1)


def capsule_wire(x0, x1, y, radius, z):
    """Closed slot outline along X at height z."""
    return Part.Wire(Part.__sortEdges__([
        Part.makeLine(App.Vector(x0, y - radius, z), App.Vector(x1, y - radius, z)),
        Part.makeCircle(radius, App.Vector(x1, y, z), Z, -90, 90),
        Part.makeLine(App.Vector(x1, y + radius, z), App.Vector(x0, y + radius, z)),
        Part.makeCircle(radius, App.Vector(x0, y, z), Z, 90, 270)]))


def pull(cutter_at, chamfer_from=6.0, chamfer_to=15.0, narrow=15.0):
    """A door-style pull: back recess to chamfer_from, 45 degree chamfer to
    chamfer_to, then a through opening. cutter_at(radius, z0, z1) makes one solid."""
    wide = narrow + (chamfer_to - chamfer_from)
    recess = cutter_at(wide, -1, chamfer_from)
    chamfer = cutter_at((wide, narrow), chamfer_from, chamfer_to)
    through = cutter_at(narrow, chamfer_to - 1, 19)
    return Part.makeBox(395, 299, 18).cut(recess.fuse(chamfer).fuse(through)).removeSplitter()


def round_cutter(cx, cy):
    def make(radius, z0, z1):
        if isinstance(radius, tuple):
            return Part.makeCone(radius[0], radius[1], z1 - z0, App.Vector(cx, cy, z0))
        return Part.makeCylinder(radius, z1 - z0, App.Vector(cx, cy, z0))
    return make


def slot_cutter(x0, x1, y):
    def make(radius, z0, z1):
        if isinstance(radius, tuple):
            return Part.makeLoft([capsule_wire(x0, x1, y, radius[0], z0), capsule_wire(x0, x1, y, radius[1], z1)], True, True)
        return Part.Face(capsule_wire(x0, x1, y, radius, z0)).extrude(App.Vector(0, 0, z1 - z0))
    return make


class PanelAssertions:
    def assertExactPanel(self, part, width=395, height=299):
        self.assertAlmostEqual(part['width_mm'], width, places=6)
        self.assertAlmostEqual(part['height_mm'], height, places=6)
        box = part['shape'].optimalBoundingBox()
        self.assertLess(max(abs(box.XMin), abs(box.YMin), abs(box.ZMin)), 1e-6)
        outline = part['operations'][0]['face'].optimalBoundingBox()
        self.assertAlmostEqual(outline.XLength, width, places=6)
        self.assertAlmostEqual(outline.YLength, height, places=6)
        self.assertLessEqual(part['verification']['unexplained_volume_mm3'], part['verification']['tolerance_mm3'])
        self.assertTrue(any(op['layer'] == 'TAPER_45DEG_WIDE_START_6MM_END_15MM' for op in part['operations']))


class TaperBoundsTests(PanelAssertions, unittest.TestCase):
    def export(self, solid):
        part = macro['analyse_solid'](solid, 'test', Z)
        return macro['apply_part_options'](part)

    def test_half_pull_on_panel_edge_keeps_exact_size(self):
        # Paired pulls: the chamfer cone is cut by the panel edge.
        self.assertExactPanel(self.export(pull(round_cutter(197.5, 0))))

    def test_chamfered_slot(self):
        self.assertExactPanel(self.export(pull(slot_cutter(200, 350, 150))))

    def test_chamfered_slot_on_panel_edge(self):
        self.assertExactPanel(self.export(pull(slot_cutter(120, 270, 0))))

    def test_taper_level_off_the_rounding_grid(self):
        # 18/7 mm is not a multiple of 0.0001 mm: grouping must not move the level.
        start = 18 / 7
        part = macro['analyse_solid'](pull(round_cutter(197.5, 150), start, start + 9), 'test', Z)
        self.assertLessEqual(part['verification']['unexplained_volume_mm3'], part['verification']['tolerance_mm3'])

    def test_spline_edges_become_exact_lines_and_arcs(self):
        line = Part.makeLine(App.Vector(0, 0, 0), App.Vector(100, 20, 0))
        spline_line = Part.Edge(line.Curve.toBSpline(line.FirstParameter, line.LastParameter))
        self.assertIsInstance(macro['canonical_edge'](spline_line).Curve, Part.Line)
        arc = Part.makeCircle(21, App.Vector(5, 5, 0), Z, 0, 90)
        spline_arc = Part.Edge(arc.Curve.toBSpline(arc.FirstParameter, arc.LastParameter))
        rebuilt = macro['canonical_edge'](spline_arc)
        self.assertIsInstance(rebuilt.Curve, Part.Circle)
        self.assertAlmostEqual(rebuilt.Curve.Radius, 21, places=6)
        # A 1 m spline bowed by 0.02 mm must not be drawn as a straight line. It
        # may become an exact very flat arc, but only one that follows the spline.
        bowed = Part.BSplineCurve()
        bowed.interpolate([App.Vector(0, 0, 0), App.Vector(500, 0.02, 0), App.Vector(1000, 0, 0)])
        original = bowed.toShape()
        rebuilt = macro['canonical_edge'](original)
        self.assertNotIsInstance(rebuilt.Curve, Part.Line)
        for k in range(1, 20):
            point = original.valueAt(original.FirstParameter + (original.LastParameter - original.FirstParameter) * k / 20)
            self.assertLess(rebuilt.distToShape(Part.Vertex(point))[0], macro['EXACT_FIT_TOL'])
        # Neither a line nor an arc: left as a spline for validate_edges to reject.
        wave = Part.BSplineCurve()
        wave.interpolate([App.Vector(0, 0, 0), App.Vector(250, 0.5, 0), App.Vector(500, 0, 0),
                          App.Vector(750, -0.5, 0), App.Vector(1000, 0, 0)])
        self.assertIsInstance(macro['canonical_edge'](wave.toShape()).Curve, Part.BSplineCurve)

    def test_spline_chamfer_face_is_a_taper_but_a_dome_is_not(self):
        strip = Part.Face(Part.makePolygon([App.Vector(0, 0, 0), App.Vector(18, 0, 0), App.Vector(18, 9, 9),
                                            App.Vector(0, 9, 9), App.Vector(0, 0, 0)])).toNurbs().Faces[0]
        self.assertIsInstance(strip.Surface, Part.BSplineSurface)
        self.assertAlmostEqual(macro['bspline_taper_angle'](strip), 45, places=6)
        dome = Part.makeSphere(10).toNurbs().Faces[0]
        self.assertIsNone(macro['bspline_taper_angle'](dome))

    def test_layer_tokens_have_no_negative_zero(self):
        self.assertEqual(macro['token'](-1e-7), '0')


TAPER_TOL_MM3 = 1e-3  # the loft error being tested is about 0.1 mm3; volume noise is about 1e-4


def taper_faces(shape):
    """The faces analyse_solid treats as tapers: sloping planes, tapered cones and
    constant-slope spline faces."""
    faces = []
    for face in shape.Faces:
        surface = face.Surface
        if isinstance(surface, Part.Plane):
            if 1e-7 < abs(face.normalAt(0, 0).z) < 1 - 1e-7:
                faces.append(face)
        elif isinstance(surface, Part.Cone):
            if macro['tapered_cone'](face):
                faces.append(face)
        elif isinstance(surface, Part.BSplineSurface) and macro['bspline_taper_angle'](face) is not None:
            faces.append(face)
    return faces


def pulls(*cutters):
    """Several pulls cut by one call of pull()."""
    def make(radius, z0, z1):
        solids = [cutter(radius, z0, z1) for cutter in cutters]
        return solids[0].multiFuse(solids[1:])
    return make


class Broken:
    """Stands in for an invalid boolean result."""
    def isValid(self):
        return False


class OffCentreTaperTests(PanelAssertions, unittest.TestCase):
    """A panel edge that cuts a chamfer cone off its axis meets the cone at a different
    angle at each depth. A ruled loft between the two contours then falls short of the
    cone, and the reconstruction check either rejects an exact part or misses the gap."""

    def assertTaperCuttersExact(self, solid):
        """Each taper cutter, trimmed to the panel, is the part's real taper void: the
        same volume (a missed sliver shows here even when a boolean misses it), nothing
        left over on either side (no compensating errors), and the drawn contours stay
        on the panel."""
        shape = macro['orient_pull_front'](macro['flatten_solid'](solid, Z))
        bounds = shape.optimalBoundingBox()
        tapers = macro['extract_tapers'](shape, taper_faces(shape))
        self.assertTrue(tapers)
        for taper in tapers:
            wide_z, narrow_z = taper['wide'].CenterOfMass.z, taper['narrow'].CenterOfMass.z
            low, high = min(wide_z, narrow_z), max(wide_z, narrow_z)
            base = Part.Face(taper['wide'].OuterWire)
            base.translate(App.Vector(0, 0, low - wide_z))
            prism = base.extrude(App.Vector(0, 0, high - low))
            void = prism.cut(shape)
            panel = Part.makeBox(bounds.XLength, bounds.YLength, high - low, App.Vector(bounds.XMin, bounds.YMin, low))
            cutter = taper['solid'].common(panel)
            self.assertAlmostEqual(cutter.Volume, prism.Volume - prism.common(shape).Volume, delta=TAPER_TOL_MM3)
            self.assertLess(abs(cutter.cut(void).Volume), TAPER_TOL_MM3)
            self.assertLess(abs(void.cut(cutter).Volume), TAPER_TOL_MM3)
            for contour in (taper['wide'], taper['narrow']):
                box = contour.optimalBoundingBox()
                self.assertGreaterEqual(box.XMin, bounds.XMin - 1e-6)
                self.assertGreaterEqual(box.YMin, bounds.YMin - 1e-6)
                self.assertLessEqual(box.XMax, bounds.XMax + 1e-6)
                self.assertLessEqual(box.YMax, bounds.YMax + 1e-6)

    def assertExports(self, solid):
        self.assertExactPanel(macro['apply_part_options'](macro['analyse_solid'](solid, 'test', Z)))

    def assertExactAndExports(self, solid):
        self.assertTaperCuttersExact(solid)
        self.assertExports(solid)

    def test_half_slot_centred_past_panel_edge(self):
        # Paired vertical capsule: slot axis along the edge, 1 mm outside the panel.
        self.assertExactAndExports(pull(slot_cutter(120, 270, -1)))

    def test_half_pull_centred_past_panel_edge(self):
        # Paired circle: centre 1 mm outside the panel.
        self.assertExactAndExports(pull(round_cutter(197.5, -1)))

    def test_pulls_past_the_far_panel_edges(self):
        # Centres 1 mm past the X max and Y max edges.
        for cutter in (round_cutter(396, 150), round_cutter(197.5, 300)):
            with self.subTest(cutter=cutter):
                self.assertExactAndExports(pull(cutter))

    def test_two_pulls_on_one_edge(self):
        # One taper group, two contours that each end on the same panel edge.
        self.assertExactAndExports(pull(pulls(round_cutter(100, -1), round_cutter(300, -1))))

    def test_upside_down_pull_is_turned_over_first(self):
        # orient_pull_front turns the part over before the tapers are read.
        solid = pull(slot_cutter(120, 270, -1))
        solid.rotate(App.Vector(0, 0, 9), App.Vector(1, 0, 0), 180)
        self.assertExactAndExports(solid)

    def test_pull_centred_inside_panel_edge(self):
        # Centre 5 mm inside the panel: both chamfer contours are cut by the edge.
        self.assertExactAndExports(pull(round_cutter(197.5, 5)))

    def test_only_the_wide_contour_reaches_the_panel_edge(self):
        # Centre 20 mm inside: the R15 contour is a whole circle, the R24 one is cut.
        self.assertExactAndExports(pull(round_cutter(197.5, 20)))

    def test_slot_end_cut_by_a_short_panel_edge(self):
        # Slot running into the X = 0 edge: its end arc's centre is 5 mm inside the
        # panel, so the edge leaves two pieces of that arc, one on each side.
        self.assertExactAndExports(pull(slot_cutter(5, 100, 150)))

    def test_slot_where_only_the_wide_contour_reaches_the_edge(self):
        # The R24 end arc is cut into two pieces; once continued they must become one
        # arc again, to match the uncut R15 contour edge for edge.
        self.assertExactAndExports(pull(slot_cutter(20, 100, 150)))

    def test_centres_almost_on_the_edge_keep_the_plain_loft(self):
        # Within PANEL_EDGE_CONTINUE_MIN the plain loft's error is negligible, and new
        # edges that close to the blank's could break the boolean.
        for cutter in (round_cutter(197.5, -1e-4), round_cutter(197.5, 5e-5), slot_cutter(120, 270, -3e-5)):
            with self.subTest(cutter=cutter):
                self.assertExports(pull(cutter))

    def test_wide_contour_grazing_the_edge_keeps_the_plain_loft(self):
        # The R24 contour crosses the edge by 0.0001 mm.
        self.assertExports(pull(round_cutter(197.5, 24 - 1e-4)))

    def test_broken_rebuild_is_refused(self):
        # A broken boolean can return an invalid solid with negative volumes, which
        # would otherwise pass the comparison whatever the operations are.
        original = macro['rebuild_part']
        macro['rebuild_part'] = lambda blank, removals, shape: (Broken(), -2e6, 0.0)
        try:
            with self.assertRaisesRegex(macro['ExportError'], 'could not be checked'):
                macro['analyse_solid'](pull(round_cutter(197.5, 150)), 'test', Z)
        finally:
            macro['rebuild_part'] = original

    def test_broken_rebuild_is_retried_with_the_plain_lofts(self):
        original = macro['rebuild_part']
        calls = []

        def first_breaks(blank, removals, shape):
            calls.append(list(removals))
            return (Broken(), -2e6, 0.0) if len(calls) == 1 else original(blank, removals, shape)

        macro['rebuild_part'] = first_breaks
        try:
            macro['analyse_solid'](pull(slot_cutter(120, 270, -1)), 'test', Z)
        except macro['ExportError']:
            pass  # the plain loft may be judged short; the retry is what is tested
        finally:
            macro['rebuild_part'] = original
        self.assertEqual(len(calls), 2)
        swapped = [i for i, (first, second) in enumerate(zip(*calls)) if first is not second]
        self.assertEqual(len(swapped), 1)

if __name__ == '__main__':
    unittest.main()
