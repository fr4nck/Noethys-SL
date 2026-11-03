# -*- coding: utf-8 -*-
"""D7 : rendu Word local d'une facture D6 deja numerotee et verifiee.

Aucune mutation base, aucun envoi, aucun statut 'transmise' ou 'payee'.
Le format est une presentation, PAS un moteur de mise en conformite fiscale.
Dependance facultative : python-docx, chargee seulement lors du rendu.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import ZipFile

from Utils.UTILS_Partenaires_D6 import FacturesPartenaires, FactureIntegrite, FactureInvalide


def _s(texte, *, obligatoire=False, max_len=450):
    if texte is None:
        if obligatoire:
            raise FactureInvalide('Mention obligatoire manquante')
        return ''
    if not isinstance(texte, str) or len(texte) > max_len or ('\x00' in texte):
        raise FactureInvalide('Mention de facture invalide')
    v = texte.strip()
    if obligatoire and not v:
        raise FactureInvalide('Mention obligatoire vide')
    return v


def _euro(texte):
    if not isinstance(texte, str):
        raise FactureIntegrite('Montant facture non canonique')
    try:
        d=Decimal(texte)
    except InvalidOperation as exc:
        raise FactureIntegrite('Montant facture illisible') from exc
    if not d.is_finite() or d < 0 or d > Decimal('9999999999.99') or format(d,'.2f') != texte:
        raise FactureIntegrite('Montant facture non canonique')
    return d


def _date_fr(texte):
    try:
        d=date.fromisoformat(texte)
        if d.isoformat() != texte: raise ValueError()
    except (TypeError,ValueError) as exc:
        raise FactureInvalide('Date de facture invalide') from exc
    return d.strftime('%d/%m/%Y')


def _format_eur(d):
    return ('{:,.2f}'.format(d)).replace(',', ' ').replace('.', ',') + ' EUR'


def _verifier_document(doc):
    if not isinstance(doc,dict) or doc.get('type_document') != 'facture_partenaire':
        raise FactureInvalide('Document D6 requis')
    if doc.get('etat') != 'enregistree' or not isinstance(doc.get('numero'), str):
        raise FactureInvalide('Facture non enregistree')
    import re
    if not re.fullmatch(r'PMSL-[0-9]{4}-[0-9]{6}',doc['numero']):
        raise FactureInvalide('Numero de facture invalide')
    for k in ('date_emission','date_echeance','date_prestation','periode_debut','periode_fin'):
        _date_fr(doc.get(k))
    if doc.get('devise') != 'EUR':
        raise FactureInvalide('Devise non autorisee')
    for partie in ('emetteur','destinataire'):
        d=doc.get(partie)
        if not isinstance(d,dict): raise FactureInvalide('Adresse absente')
        for k in ('raison_sociale','adresse_ligne1','code_postal','commune'):
            _s(d.get(k),obligatoire=True,max_len=255)
    e=doc['emetteur']
    for k in ('siret','mention_fiscale','conditions_paiement','penalites_retard'):
        _s(e.get(k),obligatoire=True)
    total=_euro(doc.get('total_eur'))
    lignes=doc.get('lignes')
    if not isinstance(lignes,list) or not 1<=len(lignes)<=2000:
        raise FactureInvalide('Lignes D6 manquantes ou trop nombreuses')
    montants=[]
    for ligne in lignes:
        if not isinstance(ligne,dict): raise FactureInvalide('Ligne non conforme')
        for k in ('date_reelle',): _date_fr(ligne.get(k))
        for k in ('libelle','categorie','unite'):_s(ligne.get(k),obligatoire=True,max_len=120)
        if type(ligne.get('minutes_reelles')) is not int or ligne['minutes_reelles']<=0:
            raise FactureInvalide('Duree invalide')
        _euro(ligne.get('prix_unitaire'))
        montant=_euro(ligne.get('montant'))
        montants.append(montant)
    if sum(montants,Decimal('0'))!=total or total<=0:
        raise FactureIntegrite('Montant de facture different de ses lignes')
    return total


def creer_docx_facture(moteur, IDfacture_partenaire, *, acteur):
    """Produit des octets .docx sans ecriture, uniquement depuis D6 verifie.

    Le statut d'envoi ne change pas. Le document comporte un marquage
    'EDITION DE CONTROLE - NON TRANSMISE' tant que la validation metier manque.
    """
    if not isinstance(moteur,FacturesPartenaires):
        raise FactureInvalide('Registre D6 autorise requis')
    source=moteur.lire_facture(IDfacture_partenaire,acteur=acteur,verifier_source=True)
    if source['transmise'] is not False:
        raise FactureInvalide('Le suivi de transmission n est pas qualifie')
    return _construire(source['facture'])


def _construire(doc):
    """Rendu interne, jamais expose a l'interface sans lecture D6 verifiee."""
    total=_verifier_document(doc)
    try:
        from docx import Document
        from docx.shared import Cm,Pt,RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_BREAK
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError as exc:
        raise FactureInvalide('Dependance python-docx indisponible : edition impossible') from exc

    d=Document();sec=d.sections[0]
    sec.page_width=Cm(21);sec.page_height=Cm(29.7)
    sec.top_margin=Cm(1.9);sec.bottom_margin=Cm(1.9)
    sec.left_margin=Cm(2.0);sec.right_margin=Cm(2.0)
    sec.header_distance=Cm(.7);sec.footer_distance=Cm(.75)
    style=d.styles['Normal'];style.font.name='Aptos';style.font.size=Pt(9.2)
    style.paragraph_format.space_after=Pt(4)
    dark=RGBColor(32,47,61);grey=RGBColor(82,91,101)

    def line(text,bold=False,size=None):
        p=d.add_paragraph();r=p.add_run(str(text));r.bold=bold;r.font.color.rgb=dark
        if size:r.font.size=Pt(size)
        return p
    def celltext(cell,text,bold=False):
        cell.text=''
        p=cell.paragraphs[0]
        p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(3)
        run=p.add_run(str(text));run.bold=bold;run.font.size=Pt(8.6)
        cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER

    h=sec.header.paragraphs[0];h.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    run=h.add_run('EDITION DE CONTROLE  ·  NON TRANSMISE');run.bold=True;run.font.size=Pt(8);run.font.color.rgb=grey
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    fr=footer.add_run('Facture partenaire - document a verifier avant toute remise au destinataire')
    fr.font.size=Pt(8);fr.font.color.rgb=grey

    p=d.add_paragraph();r=p.add_run('FACTURE');r.bold=True;r.font.size=Pt(20);r.font.color.rgb=dark
    info=d.add_table(rows=1,cols=2)
    info.autofit=False;info.columns[0].width=Cm(8.4);info.columns[1].width=Cm(8.4)
    e=doc['emetteur'];c=doc['destinataire']
    ep=[e['raison_sociale'],e['adresse_ligne1'],e['code_postal']+' '+e['commune'],'SIRET : '+e['siret']]
    cp=[c['raison_sociale'],c['adresse_ligne1'],c['code_postal']+' '+c['commune']]
    if c.get('pays') and c['pays']!='France':cp.append(c['pays'])
    if c.get('siret'):cp.append('SIRET : '+c['siret'])
    celltext(info.cell(0,0),'EMETTEUR\n'+'\n'.join(ep),False)
    celltext(info.cell(0,1),'DESTINATAIRE\n'+'\n'.join(cp),False)
    d.add_paragraph()
    facts=d.add_table(rows=2,cols=3)
    facts.autofit=False
    for col,w in zip(facts.columns,[6.0,5.4,5.4]):col.width=Cm(w)
    for i,label in enumerate(('NUMERO','DATE D EMISSION','ECHEANCE')):
        celltext(facts.cell(0,i),label,True)
    for i,val in enumerate((doc['numero'],_date_fr(doc['date_emission']),_date_fr(doc['date_echeance']))):
        celltext(facts.cell(1,i),val,True)
    line('Période des prestations : %s au %s' % (_date_fr(doc['periode_debut']),_date_fr(doc['periode_fin'])),size=9)
    line('Référence du bordereau : %s' % str(doc.get('IDbordereau')))
    d.add_paragraph()

    tab=d.add_table(rows=1,cols=4);tab.autofit=False;tab.alignment=WD_TABLE_ALIGNMENT.CENTER
    widths=[2.4,8.1,2.5,3.8]
    for col,w in zip(tab.columns,widths):col.width=Cm(w)
    for i,t in enumerate(('DATE','INTERVENTION','UNITE','MONTANT')):
        celltext(tab.rows[0].cells[i],t,True)
    trPr=tab.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');repeat.set(qn('w:val'),'true');trPr.append(repeat)
    for item in doc['lignes']:
        cells=tab.add_row().cells
        qty='1 séance' if item['unite']=='seance' else '%d min' % item['minutes_reelles']
        desc=_s(item['libelle'])+'\n'+_s(item['categorie'])
        for i,v in enumerate((_date_fr(item['date_reelle']),desc,qty,_format_eur(_euro(item['montant'])))):
            celltext(cells[i],v)
    d.add_paragraph()
    p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    r=p.add_run('TOTAL A REGLER     '+_format_eur(total));r.bold=True;r.font.size=Pt(13);r.font.color.rgb=dark
    for label,field in (('Conditions de paiement','conditions_paiement'),
                        ('Pénalités de retard','penalites_retard'),
                        ('Indemnité de recouvrement','indemnite_recouvrement'),
                        ('Mention fiscale fournie par l’association','mention_fiscale')):
        val=_s(e.get(field))
        if not val:continue
        p=d.add_paragraph();p.paragraph_format.space_after=Pt(1)
        b=p.add_run(label+' : ');b.bold=True;b.font.size=Pt(8.5)
        t=p.add_run(val);t.font.size=Pt(8.5)
    out=BytesIO();d.save(out)
    result=out.getvalue()
    with ZipFile(BytesIO(result)) as z:
        if 'word/document.xml' not in z.namelist():
            raise FactureIntegrite('Export Word incomplet')
    return result
