"""Run in FreeCAD's Python environment; no user model is modified."""
import math
import unittest
from pathlib import Path

import FreeCAD as App
import Part

MACRO = Path(__file__).resolve().parents[1] / 'FreeCAD_Lay_Flat_for_CNC.FCMacro'
macro = {'__name__': 'layflat_test', '__file__': str(MACRO)}
exec(compile(MACRO.read_text(), str(MACRO), 'exec'), macro)


class FilletRemovalTests(unittest.TestCase):
    def setUp(self):
        self.previous = App.ActiveDocument
        self.doc = App.newDocument('LayFlatFilletRegression')

    def tearDown(self):
        App.closeDocument(self.doc.Name)
        if self.previous:
            App.setActiveDocument(self.previous.Name)

    def panel(self, radius=1):
        body = self.doc.addObject('PartDesign::Body', 'Panel')
        base = body.newObject('PartDesign::Feature', 'Blank')
        base.Shape = Part.makeBox(120, 80, 18)
        fillet = body.newObject('PartDesign::Fillet', 'FinishingFillet')
        fillet.Base = (base, ['Edge%d' % i for i in range(1, 13)])
        fillet.Radius = radius
        self.doc.recompute()
        self.assertTrue(fillet.Shape.isValid())
        # Operations AFTER the fillet must survive. The tiny hole is below
        # the cutoff but must never be mistaken for a small finishing fillet.
        self.hole = Part.makeCylinder(0.4, 20, App.Vector(30, 30, -1))
        self.pocket = Part.makeBox(12, 10, 6, App.Vector(60, 40, 13))
        final = body.newObject('PartDesign::Feature', 'LaterMachining')
        final.Shape = fillet.Shape.cut(self.hole).cut(self.pocket)
        self.doc.recompute()
        self.assertEqual(final.BaseFeature, fillet)
        return body

    def test_inclusive_cutoff_preserves_later_machining_and_source(self):
        body = self.panel()
        before = body.Shape.exportBrepToString()
        result, report = macro['remove_small_fillets'](body, 1)
        expected = Part.makeBox(120, 80, 18).cut(self.hole).cut(self.pocket)
        self.assertEqual(report['status'], 'removed')
        self.assertLess(result.cut(expected).Volume + expected.cut(result).Volume, 1e-5)
        self.assertEqual(body.Shape.exportBrepToString(), before)
        part = macro['analyse_solid'](result, 'Test panel')
        self.assertTrue(any(op['kind'] == 'HOLE' and abs(op['diameter_mm'] - 0.8) < 1e-6 for op in part['operations']))
        self.assertFalse(any(isinstance(e.Curve, Part.Circle) for e in part['operations'][0]['face'].Edges))

    def test_off_and_below_radius_keep_original(self):
        body = self.panel()
        for cutoff, status in [(0, 'disabled'), (0.999, 'no_qualifying_fillets')]:
            result, report = macro['remove_small_fillets'](body, cutoff)
            self.assertEqual(report['status'], status)
            self.assertLess(result.cut(body.Shape).Volume + body.Shape.cut(result).Volume, 1e-6)

    def test_larger_fillet_stays(self):
        body = self.panel(2.5)
        _, report = macro['remove_small_fillets'](body, 1)
        self.assertEqual(report['status'], 'no_qualifying_fillets')

    def test_imported_solid_is_not_guessed(self):
        body = self.panel()
        imported = self.doc.addObject('Part::Feature', 'Imported')
        imported.Shape = body.Shape.copy()
        result, report = macro['remove_small_fillets'](imported, 1)
        self.assertEqual(report['status'], 'no_native_fillet_history')
        self.assertAlmostEqual(result.Volume, imported.Shape.Volume)

    def test_invalid_cutoff_is_rejected(self):
        body = self.panel()
        for cutoff in [-1, math.nan, math.inf]:
            with self.assertRaises(macro['ExportError']):
                macro['remove_small_fillets'](body, cutoff)

    def test_rotated_instance_keeps_placement(self):
        body = self.panel()
        body.Placement = App.Placement(App.Vector(20, 30, 40), App.Rotation(App.Vector(0, 1, 0), 30))
        self.doc.recompute()
        link = self.doc.addObject('App::Link', 'Instance')
        link.setLink(body)
        link.Placement = App.Placement(App.Vector(300, 200, 100), App.Rotation(App.Vector(0, 0, 1), 70))
        self.doc.recompute()
        placed = Part.getShape(link).Solids[0]
        candidate = {'shape': placed, 'source_document': self.doc.Name, 'source_object': body.Name}
        result, report = macro['prepare_candidate'](candidate, 1)
        original = body.Shape.Solids[0]
        transform = placed.Placement.multiply(original.Placement.inverse())
        expected = Part.makeBox(120, 80, 18).cut(self.hole).cut(self.pocket)
        expected.Placement = transform.multiply(body.Placement).multiply(expected.Placement)
        self.assertEqual(report['status'], 'removed')
        self.assertLess(result.cut(expected).Volume + expected.cut(result).Volume, 1e-5)

    def test_failed_or_destructive_defeaturing_is_rejected(self):
        body = self.panel()
        hole = self.hole

        class ShapeProxy:
            def __init__(self, unchanged):
                self.unchanged = unchanged

            def __getattr__(self, name):
                return getattr(body.Shape, name)

            def copy(self):
                return self

            def defeaturing(self, faces):
                if self.unchanged:
                    return body.Shape.copy()
                # Simulate a kernel result that also fills an unrelated hole.
                return body.Shape.defeaturing(faces).fuse(hole)

        class BodyProxy:
            def __init__(self, unchanged):
                self.Shape = ShapeProxy(unchanged)

            def __getattr__(self, name):
                return getattr(body, name)

        for unchanged in (True, False):
            with self.assertRaises(macro['ExportError']):
                macro['remove_small_fillets'](BodyProxy(unchanged), 1)

    def test_mirrored_body_follows_binder_to_native_fillets(self):
        left = self.panel()
        left.Placement.Base = App.Vector(-170, 15, 20)
        binder = self.doc.addObject('PartDesign::SubShapeBinder', 'MirrorReference')
        binder.Support = [(left, [''])]
        mirror = self.doc.addObject('Part::Mirroring', 'Mirror')
        mirror.Source = binder
        mirror.Base = App.Vector(0, 0, 0)
        mirror.Normal = App.Vector(1, 0, 0)
        right = self.doc.addObject('PartDesign::Body', 'RightPanel')
        right.BaseFeature = mirror
        self.doc.recompute()
        self.assertEqual(right.Tip.TypeId, 'PartDesign::FeatureBase')
        snapshots = [o.Shape.exportBrepToString() for o in (left, binder, mirror, right)]
        placed = Part.getShape(right).Solids[0]
        candidate = {'shape': placed, 'source_document': self.doc.Name, 'source_object': right.Name}
        result, report = macro['prepare_candidate'](candidate, 1)
        self.assertEqual(report['status'], 'removed')
        expected = Part.makeBox(120, 80, 18).cut(self.hole).cut(self.pocket)
        expected.Placement = left.Placement
        expected = expected.mirror(mirror.Base, mirror.Normal)
        self.assertLess(result.cut(expected).Volume + expected.cut(result).Volume, 1e-5)
        self.assertEqual(snapshots, [o.Shape.exportBrepToString() for o in (left, binder, mirror, right)])
        for cutoff in (0, 0.999):
            unchanged, kept = macro['prepare_candidate'](candidate, cutoff)
            self.assertNotEqual(kept['status'], 'removed')
            self.assertLess(unchanged.cut(placed).Volume + placed.cut(unchanged).Volume, 1e-5)

    def test_reference_with_extra_machining_is_not_replaced(self):
        body = self.panel()
        prepared, _ = macro['remove_small_fillets'](body, 1)
        modified_copy = body.Shape.cut(Part.makeCylinder(2, 20, App.Vector(90, 30, -1)))
        with self.assertRaises(macro['ExportError']):
            macro['transfer_fillet_copy'](body.Shape, prepared, modified_copy, 'Changed reference')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FilletRemovalTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError('Fillet removal regression tests failed')
