"""Run in FreeCAD's Python environment. Tests for 0.12.9: chamfered pulls and slots
(also at a panel edge) export at exact size, taper levels off the 0.0001 mm grid,
spline edges and chamfer faces that are really lines, arcs and tapers, and layer tokens."""
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


class TaperBoundsTests(unittest.TestCase):
    def export(self, solid):
        part = macro['analyse_solid'](solid, 'test', Z)
        return macro['apply_part_options'](part)

    def assertExactPanel(self, part, width=395, height=299):
        self.assertAlmostEqual(part['width_mm'], width, places=6)
        self.assertAlmostEqual(part['height_mm'], height, places=6)
        box = part['shape'].optimalBoundingBox()
        self.assertLess(max(abs(box.XMin), abs(box.YMin), abs(box.ZMin)), 1e-6)
        outline = part['operations'][0]['face'].optimalBoundingBox()
        self.assertAlmostEqual(outline.XLength, width, places=6)
        self.assertAlmostEqual(outline.YLength, height, places=6)
        self.assertEqual(part['verification']['unexplained_volume_mm3'], 0)
        self.assertTrue(any(op['layer'] == 'TAPER_45DEG_WIDE_START_6MM_END_15MM' for op in part['operations']))

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
        self.assertEqual(part['verification']['unexplained_volume_mm3'], 0)

    def test_spline_edges_become_exact_lines_and_arcs(self):
        line = Part.makeLine(App.Vector(0, 0, 0), App.Vector(100, 20, 0))
        spline_line = Part.Edge(line.Curve.toBSpline(line.FirstParameter, line.LastParameter))
        self.assertIsInstance(macro['canonical_edge'](spline_line).Curve, Part.Line)
        arc = Part.makeCircle(21, App.Vector(5, 5, 0), Z, 0, 90)
        spline_arc = Part.Edge(arc.Curve.toBSpline(arc.FirstParameter, arc.LastParameter))
        rebuilt = macro['canonical_edge'](spline_arc)
        self.assertIsInstance(rebuilt.Curve, Part.Circle)
        self.assertAlmostEqual(rebuilt.Curve.Radius, 21, places=6)
        # A 1 m spline bowed by 0.02 mm must not be drawn as a straight line.
        bowed = Part.BSplineCurve()
        bowed.interpolate([App.Vector(0, 0, 0), App.Vector(500, 0.02, 0), App.Vector(1000, 0, 0)])
        self.assertNotIsInstance(macro['canonical_edge'](bowed.toShape()).Curve, Part.Line)
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


if __name__ == '__main__':
    unittest.main()
