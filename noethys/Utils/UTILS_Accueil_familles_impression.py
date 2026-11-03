# -*- coding: utf-8 -*-
"""Editions des deux fiches famille PMSL, d'apres les DOCX transmis.

Deux pages A4 par modèle, lecture déjà préparée par
UTILS_Accueil_familles. Aucun envoi, aucune écriture SQL, aucun consentement
CAFPRO déduit. Les engagements du formulaire restent à signer.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from xml.sax.saxutils import escape

SITES_ALSH = ("LA GUERCHE", "MOUTIERS", "BAIS")
MODEL_ALSH = "alsh"
MODEL_ADOS = "ados"

ENGAGEMENTS = (
    u"Autorise mon (mes) enfant(s) à participer à toutes les activités proposées par l'Accueil de Loisirs.",
    u"Autorise, en cas d'urgence, la direction de l'ALSH à faire pratiquer les interventions chirurgicales et à faire prescrire tout traitement nécessaire à l'état de santé de mes enfants.",
    u"M'engage à rembourser les honoraires médicaux et pharmaceutiques avancés par les organisateurs en raison des soins engagés.",
    u"Autorise l'association Pêle-Mêle à faire transporter mon (mes) enfant(s), pour les besoins des activités de l'Accueil de Loisirs : par des moyens de transport collectifs (bus, minibus, train ...).",
    u"Prends note que mon enfant est sous la responsabilité de la structure uniquement sur les heures de présence de l'enfant à l'Accueil de Loisirs.",
    u"Autorise la prise de photos et leur diffusion sur le site internet et la page Facebook de l'Accueil de Loisirs, et dans la presse locale et renonce à toute contrepartie financière.",
    u"Déclare avoir souscrit une police d'assurance en responsabilité civile pour mon enfant.",
    u"Certifie exacts les renseignements portés sur cette fiche.",
)


def _texte(valeur):
    return str(valeur or "").replace("\n", " ").strip()


def _tronc(texte, taille, largeur, font="Helvetica"):
    texte = _texte(texte)
    if stringWidth(texte, font, taille) <= largeur:
        return texte
    while texte and stringWidth(texte + "...", font, taille) > largeur:
        texte = texte[:-1]
    return texte + "..."


def _ligne(c, x, y, etiquette, valeur, largeur, taille=8.5):
    c.setFont("Helvetica-Bold", taille)
    c.drawString(x, y, etiquette)
    dx = stringWidth(etiquette, "Helvetica-Bold", taille) + 6
    c.setFont("Helvetica", taille)
    c.drawString(x + dx, y, _tronc(valeur, taille, max(0, largeur - dx)))


def _bande(c, x, y, w, titre):
    c.setFillColor(HexColor("#D1D1D1"))
    c.rect(x, y - 20, w, 20, stroke=0, fill=1)
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 7, y - 14, titre)


def _boite(c, x, haut, w, h, titre):
    c.setStrokeColor(HexColor("#505050"))
    c.setLineWidth(.7)
    c.rect(x, haut - h, w, h, fill=0, stroke=1)
    _bande(c, x + 4, haut - 4, w - 8, titre)


def _case(c, x, y, texte, coche=False, taille=8.2):
    c.setLineWidth(.6)
    c.rect(x, y - 1, 9, 9, fill=0, stroke=1)
    if coche:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 1, y - 1, "X")
    c.setFont("Helvetica", taille)
    c.drawString(x + 13, y, texte)


def _regime(c, x, y, w, donnees):
    c.setFont("Helvetica-Bold", 8.1)
    c.drawString(x, y, "Régime :")
    nom = _texte(donnees.get("regime")).casefold()
    vals = {"CAF": "caf" in nom, "MSA": "msa" in nom}
    for j, nom_case in enumerate(("CAF", "MSA", "Autre")):
        coche = vals.get(nom_case, False)
        if nom_case == "Autre":
            coche = bool(nom and not vals["CAF"] and not vals["MSA"])
        _case(c, x + 77 + j * 82, y, nom_case, coche)
    _ligne(c, x + 310, y, "N° allocataire :", donnees.get("num_allocataire"),
           w - 313, 7.7)


def _bloc_parent(c, x, haut, w, parent, ordre, hauteur):
    _boite(c, x, haut, w, hauteur, u"RESPONSABLE LÉGAL n°%d" % ordre)
    def l(dec, et, valeur="", largeur=None):
        _ligne(c, x + 11, haut - dec, et, valeur, largeur or (w - 22), 8.2)
    statut = _texte(parent.get("statut")).casefold()
    y = haut - 43
    c.setFont("Helvetica-Bold", 8.1)
    c.drawString(x + 11, y, u"Statut :")
    for j, t in enumerate(("Père", "Mère", "Tuteur", "Autre")):
        _case(c, x + 78 + j * 85, y, t,
              statut in (t.casefold(), t.casefold().replace("è", "e")))
    l(63, "Nom :", parent.get("nom"))
    _ligne(c, x + 270, haut - 63, "Prénom :", parent.get("prenom"), w - 285, 8.2)
    l(84, "Situation :", parent.get("situation") or "")
    l(111, "Adresse :", parent.get("adresse"))
    l(130, "CP / Commune :",
      " ".join(x for x in (parent.get("cp"), parent.get("ville")) if x))
    l(157, "Domicile :", parent.get("domicile"), largeur=230)
    _ligne(c, x + 260, haut - 157, "Portable :", parent.get("mobile"),
           w - 270, 8.2)
    l(181, "Adresse mail :", parent.get("mail"))
    l(204, "Employeur :", parent.get("employeur"), largeur=285)
    _ligne(c, x + 300, haut - 204, "Professionnel :",
           parent.get("travail_tel"), w - 310, 8.2)


def _page1(c, donnees, modele, site, annee):
    wpage, hpage = A4
    x, w = 35, wpage - 70
    titre = (u"Club ADOS PÊLE-MÊLE - FICHE FAMILLE" if modele == MODEL_ADOS
             else u"ACCUEIL DE LOISIRS PÊLE-MÊLE - FICHE FAMILLE")
    c.rect(x + 72, hpage - 74, w - 144, 35)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(wpage / 2, hpage - 61, titre)
    c.setFont("Helvetica-Bold", 8.7)
    c.drawString(x + 10, hpage - 113,
                 u"Club ADOS :" if modele == MODEL_ADOS else u"ALSH :")
    if modele == MODEL_ADOS:
        _case(c, x + 126, hpage - 113, "BAIS", True)
    else:
        for i, nom in enumerate(SITES_ALSH):
            _case(c, x + 90 + i * 137, hpage - 113, nom, nom == site)
    _ligne(c, x + 10, hpage - 137, "Année :", annee, largeur=w - 20)
    parents = list(donnees.get("responsables") or [])
    premier = parents[0] if parents else {}
    second = parents[1] if len(parents) > 1 else {}
    haut = hpage - 155
    if modele == MODEL_ADOS:
        _bloc_parent(c, x, haut, w, premier, 1, 315)
        _regime(c, x + 11, haut - 226, w - 22, donnees)
        # La case CAFPRO porte sur une autorisation à signer :
        # jamais cochée automatiquement depuis un statut administratif.
        _case(c, x + 12, haut - 252, "", False)
        c.setFont("Helvetica", 7.7)
        c.drawString(x + 30, haut - 250,
          u"J'autorise les salariés habilités de l'association Pêle-Mêle à consulter")
        c.drawString(x + 30, haut - 263,
          u"directement mon quotient familial sur CAFPRO, le site dédié aux professionnels,")
        c.drawString(x + 30, haut - 276,
          u"grâce à mon numéro CAF. Tant que mon enfant fréquente la structure et sauf")
        c.drawString(x + 30, haut - 289,
          u"indication de ma part, cette autorisation sera tacitement renouvelée chaque année.")
        second_haut = haut - 329
    else:
        _bloc_parent(c, x, haut, w, premier, 1, 220)
        c.rect(x, haut - 275, w, 46, fill=0, stroke=1)
        _regime(c, x + 11, haut - 245, w - 22, donnees)
        second_haut = haut - 287
    _bloc_parent(c, x, second_haut, w, second, 2, 218)
    if len(parents) > 2:
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(x + 10, second_haut - 232,
            u"Autres représentants enregistrés : à vérifier dans le dossier Noethys.")
    c.setFont("Helvetica-Oblique", 8)
    c.drawRightString(x + w, 40, "Tournez svp  >")


def _paragraphe(c, texte, x, haut, largeur, taille=8.6, interligne=12):
    style = ParagraphStyle("texte", fontName="Helvetica", fontSize=taille,
                           leading=interligne, spaceBefore=0, spaceAfter=0)
    paragraph = Paragraph(escape(texte), style)
    _, h = paragraph.wrap(largeur, 600)
    paragraph.drawOn(c, x, haut - h)
    return haut - h


def _page2(c, donnees, modele):
    wpage, hpage = A4
    x, w = 35, wpage - 70
    enfants = list(donnees.get("enfants") or [])
    top = hpage - 37
    titre = u"ADOS À INSCRIRE" if modele == MODEL_ADOS else u"ENFANTS À INSCRIRE"
    _boite(c, x, top, w, 165, titre)
    colonnes = (123, 84, 55, 88, 99, w - 449)
    titres = (u"NOM", u"Prénom", u"Sexe (G/F)",
              u"Date de naissance", u"École", u"Classe")
    pos = [x]
    for largeur in colonnes:
        pos.append(pos[-1] + largeur)
    c.setLineWidth(.45)
    for bord in pos[1:-1]:
        c.line(bord, top - 25, bord, top - 165)
    for yy in (top - 52, top - 80, top - 108, top - 136):
        c.line(x, yy, x + w, yy)
    for i, entete in enumerate(titres):
        c.setFont("Helvetica-Bold", 7.2)
        c.drawCentredString((pos[i] + pos[i+1]) / 2, top - 40,
             _tronc(entete, 7.2, colonnes[i] - 5, "Helvetica-Bold"))
    for n, enfant in enumerate(enfants[:4]):
        yy = top - 70 - n * 28
        for i, cle in enumerate(("nom", "prenom", "sexe", "date_naiss",
                                 "ecole", "classe")):
            c.setFont("Helvetica", 7.8)
            c.drawString(pos[i] + 4, yy,
              _tronc(enfant.get(cle), 7.8, colonnes[i] - 8))

    top -= 182
    _bande(c, x, top, w, "AUTORISATIONS")
    y = top - 34
    y = _paragraphe(c,
        u"Je soussigné(e) ................................................ déclare avoir pris connaissance "
        u"du règlement intérieur, du fonctionnement et des conditions financières "
        u"de l'Accueil de Loisirs Pêle-Mêle et :", x + 9, y, w - 18, 8.6, 12)
    y -= 18
    for engagement in ENGAGEMENTS:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 11, y - 10, u"•")
        y = _paragraphe(c, engagement, x + 28, y, w - 40, 8.2, 11.5) - 8
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x + 5, 104, u"PÊLE-MÊLE SPORTS ET LOISIRS")
    c.setFont("Helvetica", 7.6)
    c.drawString(x + 5, 90, u"4 RUE DES DEUX GARES - 35130 LA GUERCHE DE BRETAGNE")
    c.drawString(x + 5, 77, u"Tél. 02.99.96.35.74  |  La Guerche/Moutiers : 06.16.60.16.89")
    c.drawString(x + 5, 64, u"Bais : 06.19.38.02.88  |  sportsetloisirs@pelemele.org")
    c.setFont("Helvetica", 8.3)
    c.drawString(x + 290, 98, u"À .............................., le .........................")
    c.drawString(x + 290, 77, u"Signature précédée de « lu et approuvé »")


def GenererPDF(destination, donnees, modele="alsh", site="", annee="2026-2027"):
    """Deux pages A4, aucune base de données ni mail."""
    if not isinstance(destination, str) or not destination.lower().endswith(".pdf"):
        raise ValueError("Destination PDF invalide")
    if not isinstance(donnees, dict):
        raise ValueError("Données de famille invalides")
    if modele not in (MODEL_ALSH, MODEL_ADOS):
        raise ValueError("Modèle famille inconnu")
    if modele == MODEL_ALSH and site not in SITES_ALSH:
        raise ValueError("Sélectionnez un ALSH")
    if modele == MODEL_ADOS and site not in ("", "BAIS"):
        raise ValueError("Le formulaire Club ados est réservé à Bais")
    if not annee or len(str(annee).strip()) > 40:
        raise ValueError("Année invalide")
    enfants = list(donnees.get("enfants") or [])
    if not enfants:
        raise ValueError("Aucun enfant sélectionné pour cette édition")
    if len(enfants) > 4:
        raise ValueError("Le modèle papier comporte 4 lignes d'enfants maximum")
    fichier = canvas.Canvas(destination, pagesize=A4, pageCompression=1)
    fichier.setAuthor(u"Pêle-Mêle Sports et Loisirs / Noethys-SL")
    fichier.setTitle(u"Fiche famille Club ados" if modele == MODEL_ADOS
                     else u"Fiche famille ALSH")
    _page1(fichier, donnees, modele, site, str(annee).strip())
    fichier.showPage()
    _page2(fichier, donnees, modele)
    fichier.showPage()
    fichier.save()
    return destination
