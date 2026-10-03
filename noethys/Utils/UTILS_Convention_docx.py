# -*- coding: utf-8 -*-
"""Remplit un mod�le Word avec les champs Convention existants de Noedoc.

Utilise uniquement la biblioth�que standard. Ne modifie ni le mod�le ni la
base : styles, tableaux, images, en-t�tes et pieds de page sont conserv�s.
"""
import datetime
import decimal
import os
import re
import tempfile
import zipfile
from xml.etree import ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
CODE = re.compile(r'\{[A-Z][A-Z0-9_]*\}')
STORY = re.compile(r'^word/(document|header\d+|footer\d+|footnotes|endnotes)\.xml$')

def _Texte(valeur):
    if valeur is None:
        return ''
    if isinstance(valeur, (datetime.datetime, datetime.date)):
        return valeur.strftime('%d/%m/%Y')
    if isinstance(valeur, (float, decimal.Decimal)):
        return ('%.2f' % valeur).replace('.', ',')
    return str(valeur)

def _Segments(paragraph):
    """Un champ peut �tre coup� en plusieurs runs par Word, jamais en deux paragraphes."""
    def visit(node):
        for child in node:
            if child.tag == '{%s}p' % W:
                continue
            if child.tag == '{%s}t' % W:
                yield child
            elif child.tag in ('{%s}br' % W, '{%s}tab' % W):
                yield None
            else:
                yield from visit(child)
    segment = []
    for node in visit(paragraph):
        if node is None:
            if segment:
                yield segment
            segment = []
        else:
            segment.append(node)
    if segment:
        yield segment

def _Remplacer(nodes, champs):
    text = ''.join(n.text or '' for n in nodes)
    matches = list(CODE.finditer(text))
    missing = sorted(set(m.group() for m in matches if m.group() not in champs))
    if missing:
        raise ValueError('Mots-cl�s inconnus dans le mod�le Word : %s' % ', '.join(missing))
    if '[[' in text:
        raise ValueError('Les formules [[...]] de Noedoc ne sont pas prises en charge dans Word. Utilisez les mots-cl�s {CODE}.')
    offsets = []
    offset = 0
    for node in nodes:
        offsets.append((offset, offset + len(node.text or ''), node))
        offset += len(node.text or '')
    for match in reversed(matches):
        affected = [(a, b, n) for a, b, n in offsets if a < match.end() and b > match.start()]
        first = True
        for a, b, node in affected:
            old = node.text or ''
            lo, hi = max(0, match.start() - a), min(b - a, match.end() - a)
            node.text = old[:lo] + (_Texte(champs[match.group()]) if first else '') + old[hi:]
            node.set(XML_SPACE, 'preserve')
            first = False
    return len(matches)

def _SautsDeLigne(root):
    for parent in list(root.iter()):
        for node in list(parent):
            if node.tag != '{%s}t' % W or '\n' not in (node.text or ''):
                continue
            index = list(parent).index(node)
            parts = node.text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            node.text = parts[0]
            for value in parts[1:]:
                index += 1
                parent.insert(index, ET.Element('{%s}br' % W))
                index += 1
                new = ET.Element('{%s}t' % W, {XML_SPACE: 'preserve'})
                new.text = value
                parent.insert(index, new)

def GenererDOCX(modele, champs, destination):
    if os.path.normcase(os.path.realpath(modele)) == os.path.normcase(os.path.realpath(destination)):
        raise ValueError('Le document g�n�r� doit �tre enregistr� s�par�ment du mod�le.')
    if not str(modele).lower().endswith('.docx') or not str(destination).lower().endswith('.docx'):
        raise ValueError('Choisissez un fichier .docx (Word).')
    fd, temporary = tempfile.mkstemp(suffix='.docx', dir=os.path.dirname(os.path.abspath(destination)))
    os.close(fd)
    try:
        with zipfile.ZipFile(modele) as source, zipfile.ZipFile(temporary, 'w') as output:
            if 'word/document.xml' not in source.namelist():
                raise ValueError('Ce fichier ne contient pas un document Word valide.')
            total = 0
            for item in source.infolist():
                data = source.read(item)
                if STORY.match(item.filename):
                    # Les pr�fixes d�clar�s (notamment mc:Ignorable) restent valides.
                    from io import BytesIO
                    namespaces = {}
                    for _, pair in ET.iterparse(BytesIO(data), events=['start-ns']):
                        prefix, uri = pair
                        namespaces[prefix] = uri
                        if not re.match(r'^ns\d+$', prefix):
                            ET.register_namespace(prefix, uri)
                    root = ET.fromstring(data)
                    for paragraph in root.iter('{%s}p' % W):
                        for segment in _Segments(paragraph):
                            total += _Remplacer(segment, champs)
                    _SautsDeLigne(root)
                    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                    # ElementTree omet les namespaces utilis�s seulement dans
                    # mc:Ignorable. Word exige n�anmoins leurs d�clarations.
                    from xml.sax.saxutils import quoteattr
                    start = re.search(rb'<(?![?!])[^>]+>', data)
                    declarations = []
                    for prefix, uri in namespaces.items():
                        name = 'xmlns' + (':' + prefix if prefix else '')
                        if not re.search(rb'\s' + re.escape(name.encode()) + rb'=', start.group()):
                            declarations.append(' %s=%s' % (name, quoteattr(uri)))
                    if declarations:
                        data = data[:start.end() - 1] + ''.join(declarations).encode('utf-8') + data[start.end() - 1:]
                output.writestr(item, data)
            if not total:
                raise ValueError('Le mod�le ne contient aucun mot-cl� Noedoc {CODE}.')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return str(destination)

def Impression(IDfamille, modele, date_debut=None, date_fin=None, saison=None,
               overrides=None, nomDoc=None, afficherDoc=True):
    import wx
    import FonctionsPerso
    from Utils import UTILS_Convention_champs
    from Dlg import DLG_Noedoc
    try:
        champs, _ = UTILS_Convention_champs.GetChampsConvention(
            IDfamille=IDfamille, date_debut=date_debut, date_fin=date_fin,
            saison=saison, overrides=overrides)
        # Le lecteur Noedoc fournit les champs organisateur historiques.
        # Cette m�thode ne d�pend d'aucun objet de mod�le ni de son rendu.
        champs.update(DLG_Noedoc.ModeleDoc.ImportationOrganisateur(None))
        if nomDoc is None:
            dialog = wx.FileDialog(None, 'Enregistrer la convention Word',
                                   defaultFile='Convention-%s.docx' % IDfamille,
                                   wildcard='Document Word (*.docx)|*.docx',
                                   style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return False
                nomDoc = dialog.GetPath()
            finally:
                dialog.Destroy()
        path = GenererDOCX(modele, champs, nomDoc)
        if afficherDoc:
            FonctionsPerso.LanceFichierExterne(path)
        return {'nomDoc': path, 'champs': champs}
    except Exception as err:
        dialog = wx.MessageDialog(None, 'Impossible de g�n�rer la convention Word.\n\n%s' % err,
                                  'Convention Word', wx.OK | wx.ICON_ERROR)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        return False
