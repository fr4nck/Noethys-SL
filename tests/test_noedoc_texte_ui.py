import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy
import wx
from wx.lib.floatcanvas import FloatCanvas
from wx.lib.wordwrap import wordwrap
import wx.lib.colourselect as csel

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'noethys'))
from Utils import UTILS_Adaptations
tree=ast.parse((root/'noethys/Dlg/DLG_Noedoc.py').read_text(encoding='utf-8'))
class MovingObjectMixin:
    def __init__(self,*args,**kwargs): pass
ns=dict(wx=wx,numpy=numpy,FloatCanvas=FloatCanvas,MovingObjectMixin=MovingObjectMixin,wordwrap=wordwrap,csel=csel,_=lambda x:x,DLG_Saisie_formule=SimpleNamespace(DetecteFormule=lambda text:[]))
for name in ['MovingScaledTextBox','Proprietes_texte']:
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'noedoc','exec'),ns)
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Panel_canvas')
methods=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name in ['_CopieEtat','_Etat','MemoriserEtat','Annuler']]
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Panel_canvas',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])),'history','exec'),ns)

import unittest

class NoedocTexteTests(unittest.TestCase):
    def test_reglages_et_historique_wx(self):
        app=wx.GetApp() or wx.App(False)
        frame=wx.Frame(None,size=(850,650))
        canvas=FloatCanvas.FloatCanvas(frame,size=(800,600))
        history=ns['Panel_canvas']()
        history.canvas=canvas;history.mode='edition';history._undo=[];history._redo=[]
        history.Deselection=lambda **kwargs:None
        history.Selection=lambda *args,**kwargs:None
        text='Un paragraphe qui doit rester dans les limites du bloc et conserver tous ses accents. '*4
        obj=ns['MovingScaledTextBox'](text,(0,0),Size=9/3.7,Width=70,InForeground=True)
        obj.categorie='bloc_texte';obj.nom='Test';obj.taillePolicePDF=9
        canvas.AddObject(obj)
        assert len(obj.Strings)>3
        for alignment in ['left','center','right','justify']:
            obj.Alignment=alignment;obj.LayoutText()
            assert obj.BoxWidth==70
            assert obj.Points[:,0].min()>=-0.01
        obj.Alignment='left';obj.LayoutText()
        history.MemoriserEtat();obj.SetTexte('Texte remplacé')
        history.Annuler();assert obj.texte==text
        history.Annuler(refaire=True);assert obj.texte=='Texte remplacé'
        history.MemoriserEtat();canvas.RemoveObject(obj)
        history.Annuler();assert obj in canvas._ForeDrawList
        history.Annuler(refaire=True);assert obj not in canvas._ForeDrawList
        canvas.AddObject(obj)
        panel=ns['Proprietes_texte'](frame,history)
        panel.SetObjet(obj)
        font=wx.Font(14,wx.FONTFAMILY_DEFAULT,wx.FONTSTYLE_NORMAL,wx.FONTWEIGHT_NORMAL,False,'AR CHRISTY')
        panel.ctrl_police.SetSelectedFont(font)
        panel.OnSelectPolice(None)
        assert obj.FaceName=='AR CHRISTY' and obj.taillePolicePDF==14
        assert obj.Size==14/3.7
        panel.ctrl_alignement.SetSelection(3);panel.OnAlignement(None)
        assert obj.Alignment=='justify'
        history.Annuler();assert obj.Alignment=='left'
        obj.show_editor_bounds=True
        canvas.ZoomToBB();canvas.Draw(True)
        frame.Destroy()
        print('Tests wx OK : police par bloc, taille, 4 alignements, retours à la ligne, contours, annuler/rétablir texte et suppression.')



if __name__ == '__main__':
    unittest.main()
