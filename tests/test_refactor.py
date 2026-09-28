"""Cache and validation regressions for the behaviour-preserving refactor."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from unittest import mock
import FreeCAD as App
import Part

repo = Path(__file__).resolve().parents[1]
if str(repo) not in sys.path:sys.path.insert(0, str(repo))
import lay_flat_sheet as runtime
spec = importlib.util.spec_from_file_location('fillet_fixture', Path(__file__).with_name('test_fillet_removal.py'))
fixture_module = importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture_module)


class RefactorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.FilletRemovalTests()
        self.fixture.setUp()
        self.ns = fixture_module.macro
        self.temp = tempfile.TemporaryDirectory(prefix='layflat-refactor-')
        self.folder = Path(self.temp.name)
        self.layouts = []

    def tearDown(self):
        for doc in self.layouts:
            if doc.Name in App.listDocuments():App.closeDocument(doc.Name)
        self.fixture.tearDown();self.temp.cleanup()

    def layout(self):
        shape = Part.makeBox(100,60,18)
        parts = [self.ns['apply_part_options'](self.ns['analyse_solid'](shape,'Panel'))]
        settings = dict(width_mm=2440,height_mm=1220,margin_mm=10,gap_mm=10,grain_axis='X')
        sheets = self.ns['pack_sheets'](parts,settings)
        doc = self.ns['save_sheet_preview'](sheets,settings)
        self.layouts.append(doc)
        return doc.getObject('SheetLayouts'),parts,sheets,settings

    def test_shared_fillet_source_prepared_once_and_new_run_is_fresh(self):
        body = self.fixture.panel()
        mirror = body.Document.addObject('Part::Mirroring','Mirror')
        mirror.Source = body;mirror.Normal = App.Vector(1,0,0);body.Document.recompute()
        calls=[];original=self.ns['_prepare_fillets']
        def prepare(obj,*args):
            calls.append(obj.Name);return original(obj,*args)
        cache={}
        with mock.patch.dict(self.ns, {'_prepare_fillets':prepare}):
            self.ns['remove_small_fillets'](body,1,cache=cache)
            self.ns['remove_small_fillets'](mirror,1,cache=cache)
            self.assertEqual(calls.count(body.Name),1)
            self.ns['remove_small_fillets'](body,1)
            self.assertEqual(calls.count(body.Name),2)
        with self.assertRaises(self.ns['ExportError']):
            self.ns['remove_small_fillets'](body,1,ancestors=(self.ns['object_id'](body),),cache=cache)

    def test_styles_reuse_placements_and_update_part_references(self):
        root,parts,sheets,_ = self.layout()
        before = [{k:v for k,v in p.items() if k!='part'} for p in sheets[0]['placements']]
        styled,placed = self.ns['apply_layout_styles'](parts,sheets,{'OUTLINE_THROUGH':{'name':'Outside cut','hex':'#123456'}})
        self.assertEqual(before,[{k:v for k,v in p.items() if k!='part'} for p in placed[0]['placements']])
        self.assertIs(placed[0]['placements'][0]['part'],styled[0])
        self.assertEqual(styled[0]['operations'][0]['layer'],'Outside cut')
        self.assertEqual(parts[0]['operations'][0]['layer'],'OUTLINE_THROUGH')

    def test_package_packs_once_and_changed_saved_placements_fail_before_writing(self):
        root,_,_,_ = self.layout()
        with mock.patch.object(runtime,'core',return_value=self.ns):
            original = self.ns['pack_sheets']
            with mock.patch.dict(self.ns, {'pack_sheets':mock.Mock(wraps=original)}):
                runtime.export_layout(root,self.folder,('dxf',),True)
                self.assertEqual(self.ns['pack_sheets'].call_count,1)
            before = set(self.folder.iterdir())
            payload = json.loads(root.ExportPayload);payload['sheets'][0]['placements'][0]['x_mm'] += 1
            root.ExportPayload = json.dumps(payload)
            with self.assertRaisesRegex(self.ns['ExportError'],'cannot be reproduced exactly'):
                runtime.export_layout(root,self.folder,('dxf',),True)
            self.assertEqual(before,set(self.folder.iterdir()))

    def test_exact_geometry_skips_brep_import_but_layers_are_still_checked(self):
        root,_,_,_ = self.layout();payload=json.loads(root.ExportPayload)
        with mock.patch.object(runtime.Part,'Shape',side_effect=AssertionError('Unnecessary BREP import')):
            runtime.validate_layout(root,payload)
        obj=root.Document.getObject(payload['objects'][0]['name'])
        obj.DxfLayer='Changed layer'
        with self.assertRaisesRegex(ValueError,'layers have changed'):runtime.validate_layout(root,payload)

    def test_changed_geometry_uses_fallback_and_is_rejected(self):
        root,_,_,_ = self.layout();payload=json.loads(root.ExportPayload)
        obj=root.Document.getObject(payload['objects'][0]['name'])
        copy=obj.Shape.copy();copy.translate(App.Vector(0.5,0,0));obj.Shape=copy
        with self.assertRaisesRegex(ValueError,'geometry was edited'):runtime.validate_layout(root,payload)

    def test_shared_parser_rejects_nonfinite_open_and_incomplete_paths(self):
        samples = [[(0,'LWPOLYLINE'),(70,0),(10,0),(20,0),(10,1),(20,1)],
                   [(0,'LWPOLYLINE'),(70,1),(10,0),(20,0),(10,1)],
                   [(0,'LWPOLYLINE'),(70,1),(10,0),(20,0),(10,float('nan')),(20,1)]]
        for sample in samples:
            with self.assertRaises(ValueError):runtime.closed_polyline_vertices(sample)

    def test_panel_tags_and_export_share_the_cached_core(self):
        path=Path(runtime.__file__).with_name('FreeCAD_Lay_Flat_for_CNC.FCMacro')
        with mock.patch.object(runtime,'_CORE',None), mock.patch.object(runtime,'_CORE_STAMP',None):
            with mock.patch.object(runtime.runpy,'run_path',wraps=runtime.runpy.run_path) as load:
                first=runtime.core()
                self.assertIs(first,runtime.core(path))
                self.assertEqual(load.call_count,1)

    def test_cached_preview_accepts_latest_style_and_rebuilds_after_geometry_edit(self):
        from PySide import QtWidgets,QtCore,QtGui
        import FreeCADGui as Gui
        part=self.ns['apply_part_options'](self.ns['analyse_solid'](Part.makeBox(100,60,18),'Panel'))
        original=self.ns['pack_sheets'];state={'packs':0,'phase':0,'errors':[],'started':time.monotonic()}
        def pack(*args):
            state['packs']+=1;return original(*args)
        def drive():
            dialog=QtWidgets.QApplication.activeModalWidget()
            if dialog is None:return
            if time.monotonic()-state['started']>12:
                state['errors'].append('Timed out');dialog.reject();return
            if isinstance(dialog,QtWidgets.QMessageBox):
                state['errors'].append(dialog.text());dialog.accept();return
            tables=dialog.findChildren(QtWidgets.QTableWidget)
            parts=next((t for t in tables if t.columnCount()==7),None)
            styles=next((t for t in tables if t.columnCount()==3),None)
            if parts is None or styles is None or state['packs']==0:return
            if state['phase']==0:
                styles.item(0,1).setText('Preview outline');state.update(phase=1,changed=time.monotonic())
            elif state['phase']==1 and time.monotonic()-state['changed']>0.7:
                if state['packs']!=1:state['errors'].append('Styling repacked geometry')
                parts.cellWidget(0,2).setValue(2);parts.cellWidget(0,3).setCurrentIndex(1)
                state['phase']=2
            elif state['phase']==2 and state['packs']>=2:
                # Accept before the style timer fires: pending styles must apply.
                styles.item(0,1).setText('Final outline');state['phase']=3
                button=dialog.findChild(QtWidgets.QDialogButtonBox).button(QtWidgets.QDialogButtonBox.Ok)
                QtCore.QTimer.singleShot(0,button.click)
        timer=QtCore.QTimer(Gui.getMainWindow());timer.timeout.connect(drive);timer.start(75)
        try:
            with mock.patch.dict(self.ns,{'pack_sheets':pack}):
                choice=self.ns['configure_parts']([part],QtWidgets,QtCore,QtGui,Gui.getMainWindow())
            self.assertFalse(state['errors'],state['errors'])
            self.assertEqual(state['packs'],2)
            self.assertEqual(len(choice['parts']),2)
            self.assertEqual(choice['parts'][0]['rotation_deg'],90)
            self.assertEqual(choice['parts'][0]['operations'][0]['layer'],'Final outline')
            self.assertIs(choice['sheets'][0]['placements'][0]['part'],choice['parts'][0])
        finally:timer.stop();timer.deleteLater()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RefactorTests))
    if not result.wasSuccessful():raise RuntimeError('Refactor regression tests failed')
