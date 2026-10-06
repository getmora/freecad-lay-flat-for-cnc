"""FreeCAD tests for the standard AC1018 DXF object graph (VCarve/ODA readers)."""
from pathlib import Path
import tempfile
import unittest
import sys
import FreeCAD as App
import Part

repo = Path(__file__).resolve().parents[1]
if str(repo) not in sys.path:sys.path.insert(0,str(repo))
path = repo/'FreeCAD_Lay_Flat_for_CNC.FCMacro'
ns = {'__name__':'dxf_structure_test','__file__':str(path)}
exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),ns)


def records(path):
    lines=path.read_text().splitlines()
    pairs=list(zip(map(int,lines[::2]),lines[1::2]))
    result=[];entity=[]
    for code,value in pairs:
        if code==0 and entity:result.append(entity);entity=[]
        entity.append((code,value))
    if entity:result.append(entity)
    return pairs,result


class DxfStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='layflat-dxf-')
        drawing=ns['Dxf']()
        drawing.add_wire(ns['rectangle_wire'](100,60),'OUTLINE_THROUGH')
        drawing.add_wire(Part.Wire([Part.makeCircle(5,App.Vector(20,20,0))]),'HOLE_D10_THROUGH')
        drawing.add_line((0,0),(50,0))
        drawing.add_text('Part 1',5,5)
        self.path=Path(self.temp.name)/'part.dxf'
        drawing.save(self.path)
        self.pairs,self.records=records(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def sections(self):
        return [r[1][1] for r in self.records if r[0]==(0,'SECTION')]

    def test_has_every_r2000_section(self):
        self.assertEqual(self.sections(),['HEADER','CLASSES','TABLES','BLOCKS','ENTITIES','OBJECTS'])
        tables=[r[1][1] for r in self.records if r[0]==(0,'TABLE')]
        for name in ('VPORT','LTYPE','LAYER','STYLE','APPID','DIMSTYLE','BLOCK_RECORD'):
            self.assertIn(name,tables)

    def test_entities_are_owned_by_model_space(self):
        model=[r for r in self.records if r[0]==(0,'BLOCK_RECORD') and (2,'*Model_Space') in r]
        self.assertEqual(len(model),1)
        model_handle=dict(model[0])[5]
        geometry=[r for r in self.records if r[0][1] in ('LWPOLYLINE','CIRCLE','LINE','TEXT')]
        self.assertEqual(len(geometry),4)
        for record in geometry:self.assertEqual(dict(record).get(330),model_handle)
        self.assertTrue(any(r[0]==(0,'BLOCK') and (2,'*Model_Space') in r for r in self.records))

    def test_handles_unique_and_below_seed(self):
        handles=[int(v,16) for c,v in self.pairs[self.pairs.index((9,'$HANDSEED'))+2:] if c in (5,105)]
        seed=int(self.pairs[self.pairs.index((9,'$HANDSEED'))+1][1],16)
        self.assertEqual(len(handles),len(set(handles)))
        self.assertTrue(all(h<seed for h in handles))

    def test_owner_pointers_resolve(self):
        handles={v for c,v in self.pairs if c in (5,105)}|{'0'}
        for code,value in self.pairs:
            if code in (330,340,350):self.assertIn(value,handles)

    def test_no_blank_value_lines(self):
        self.assertFalse(any(value=='' for _,value in self.pairs))


if __name__=='__main__':unittest.main()
