# -*- coding: utf-8 -*-
"""#436 - Edition A4 de la fiche enfant selon la mise en page Pêle-Mêle.

Reprend l'ordre, les titres, la grille des 4 autorisations et les 2 pages
du document papier Fiche Enfant fourni. Aucune ecriture en base et aucun
envoi du document. Les informations medicales ne sont imprimees que si
l'appelant les fournit explicitement apres verification de ses droits.
"""
from datetime import date

TITRE = u"ACCUEIL DE LOISIRS PÊLE-MÊLE"
SOUS_TITRE = u"FICHE ENFANT"
AUTORISATIONS_PAPIER = (
    ("photos_site_imprimes", u"Photos (site internet : pelemele.org)"),
    ("maquillage", u"Maquillage"),
    ("piscine_baignade", u"Baignade"),
    ("activites_physiques", u"Activités physiques"),
)
SECTIONS_P1 = (
    u"IDENTITÉ", u"RESPONSABLE LÉGAL n°1",
    u"RESPONSABLE LÉGAL n°2", u"ACCOMPAGNANTS",
    u"VACCINATIONS", u"MÉDECIN TRAITANT",
)
SECTIONS_P2 = (u"MALADIES ET ALLERGIES", u"AUTORISATIONS DIVERSES")


def _safe(value):
    return str(value) if value is not None else ""


def _tronc(texte, font, taille, max_width):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    texte = _safe(texte).replace("\n", " ")
    if stringWidth(texte, font, taille) <= max_width:
        return texte
    while texte and stringWidth(texte + "...", font, taille) > max_width:
        texte = texte[:-1]
    return texte + "..."


def _cell(c, x, y, label, valeur, largeur=470, taille=8.6):
    c.setFont("Helvetica-Bold", taille)
    c.drawString(x, y, label)
    from reportlab.pdfbase.pdfmetrics import stringWidth
    shift = stringWidth(label, "Helvetica-Bold", taille) + 6
    c.setFont("Helvetica", taille)
    c.drawString(x + shift, y,
                 _tronc(valeur, "Helvetica", taille, max(0, largeur - shift)))


def _bande(c, x, y, largeur, titre):
    from reportlab.lib.colors import HexColor
    c.setFillColor(HexColor("#BDBDBD"))
    c.rect(x, y - 19, largeur, 19, stroke=0, fill=1)
    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 6, y - 13, titre)


def _boite(c, x, top, largeur, hauteur, titre):
    from reportlab.lib.colors import HexColor
    c.setStrokeColor(HexColor("#333333"))
    c.rect(x, top - hauteur, largeur, hauteur, stroke=1, fill=0)
    _bande(c, x + 5, top - 5, largeur - 10, titre)


def _checkbox(c, x, y, coche):
    c.setLineWidth(0.7)
    c.rect(x, y, 9, 9, stroke=1, fill=0)
    if coche:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 1, y - 0.5, "X")


def _roule(c, title, lignes, x, y, maxlignes=7, largeur=512):
    """Lignes compactes, sans contenu de sante en dehors du choix imprime."""
    c.setFont("Helvetica-Bold", 8.6)
    c.drawString(x, y, title)
    c.setFont("Helvetica", 8.1)
    for item in list(lignes)[:maxlignes]:
        y -= 14
        c.drawString(x + 8, y, _tronc(item, "Helvetica", 8.1, largeur - 8))
    if len(lignes) > maxlignes:
        c.drawString(x + 8, y - 14, u"Suite à consulter dans la fiche Noethys.")
        y -= 14
    return y


def _page1(c, data):
    from reportlab.lib.pagesizes import A4
    largeur, hauteur = A4
    x, w = 42, largeur - 84

    c.setLineWidth(1.5)
    c.rect(x + 92, hauteur - 87, w - 184, 45, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(largeur / 2, hauteur - 60, TITRE)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(largeur / 2, hauteur - 78, SOUS_TITRE)
    _cell(c, x + 7, hauteur - 115, u"ALSH fréquenté :", data.get("alsh", ""),
          largeur=w - 24)
    _cell(c, x + 7, hauteur - 134, u"Année :", data.get("annee", ""),
          largeur=w - 24)
    _cell(c, x + 7, hauteur - 153, u"Classe fréquentée durant l'année scolaire :",
          data.get("classe", ""), largeur=w - 24)

    top = hauteur - 165
    _boite(c, x, top, w, 75, SECTIONS_P1[0])
    _cell(c, x + 10, top - 34, u"Sexe :", data.get("sexe", ""), largeur=w - 20)
    _cell(c, x + 10, top - 51, u"Nom :", data.get("nom", ""), largeur=250)
    _cell(c, x + 265, top - 51, u"Prénom :", data.get("prenom", ""), largeur=235)
    _cell(c, x + 10, top - 67, u"Date de naissance :",
          data.get("date_naiss", ""), largeur=245)
    _cell(c, x + 265, top - 67, u"Ville de naissance :",
          data.get("ville_naiss", ""), largeur=235)

    parents = list(data.get("responsables") or [])
    top -= 83
    for index in range(2):
        p = parents[index] if len(parents) > index else {}
        _boite(c, x, top, w, 72, SECTIONS_P1[index + 1])
        _cell(c, x + 10, top - 35, u"Nom et prénom :",
              p.get("identite", ""), largeur=w - 20)
        _cell(c, x + 10, top - 50, u"Adresse :",
              p.get("adresse", ""), largeur=w - 20)
        _cell(c, x + 10, top - 65, u"Téléphones :",
              p.get("telephone", ""), largeur=w - 20)
        top -= 79

    _boite(c, x, top, w, 92, SECTIONS_P1[3])
    c.setFont("Helvetica-Bold", 7.5)
    for i, nom in enumerate((u"Nom", u"Prénom", u"Lien de parenté", u"N° téléphone")):
        c.drawCentredString(x + 63 + i * (w / 4), top - 39, nom)
    c.setLineWidth(0.4)
    c.line(x + 5, top - 43, x + w - 5, top - 43)
    for i in range(1, 4):
        cx = x + i * (w / 4)
        c.line(cx, top - 27, cx, top - 90)
    for y in (top - 58, top - 73):
        c.line(x + 5, y, x + w - 5, y)
    top -= 100

    _boite(c, x, top, w, 54, SECTIONS_P1[4])
    _cell(c, x + 10, top - 38, u"Dernier DT Polio / vaccins :",
          data.get("vaccinations", u"Voir les vaccinations existantes dans Noethys"),
          largeur=w - 20)
    top -= 62
    _boite(c, x, top, w, 54, SECTIONS_P1[5])
    _cell(c, x + 10, top - 35, u"Médecin :",
          data.get("medecin", u"Voir l'onglet Médical existant"),
          largeur=w - 20)
    c.setFont("Helvetica-Oblique", 8)
    c.drawRightString(x + w - 8, 25, u"Tournez svp  >")


def _page2(c, data):
    from reportlab.lib.pagesizes import A4
    largeur, hauteur = A4
    x, w = 42, largeur - 84
    top = hauteur - 38
    _boite(c, x, top, w, 475, SECTIONS_P2[0])

    _cell(c, x + 10, top - 39,
          u"Traitement pendant l'accueil :",
          data.get("traitement", u"Voir l'onglet Médical existant"),
          largeur=w - 20, taille=8.4)
    c.setFont("Helvetica", 8)
    c.drawString(x + 10, top - 57,
        u"Ordonnance et justificatifs : conserver les documents dans les pièces médicales.")
    c.drawString(x + 10, top - 79,
        u"Maladies, vaccinations et consignes : consulter les informations Noethys existantes.")

    y = top - 98
    items = [
        (u"PAI (Projet d'Accueil Individualisé) :", data.get("pai", u"Voir la fiche médicale")),
        (u"AESH en milieu scolaire :", data.get("aesh", "")),
        (u"AEEH :", data.get("aeeh", "")),
        (u"Établissement médico-social :", data.get("medicosocial", "")),
        (u"Allergies :", data.get("allergies", u"Voir la fiche médicale")),
        (u"Régime alimentaire :", data.get("repas", u"Voir le questionnaire")),
    ]
    for label, valeur in items:
        _cell(c, x + 10, y, label, valeur, largeur=w - 20, taille=8.4)
        y -= 22

    y -= 4
    _roule(c, u"Difficultés de santé et précautions (données existantes, lecture contrôlée) :",
           list(data.get("medical", [])), x + 10, y, maxlignes=7, largeur=w - 20)

    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(x + 10, top - 370,
        u"La présente édition ne remplace pas les originaux ni les justificatifs médicaux.")
    c.drawString(x + 10, top - 386,
        u"Aucun nouvel état médical n'a été créé par l'édition.")

    top = top - 483
    _boite(c, x, top, w, 100, SECTIONS_P2[1])
    table_y = top - 38
    for i, (code, libelle) in enumerate(AUTORISATIONS_PAPIER):
        left = x + i * (w / 4)
        center = left + w / 8
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(center, table_y,
             _tronc(libelle, "Helvetica-Bold", 7, (w / 4) - 6))
        if i > 0:
            c.line(left, top - 25, left, top - 98)
        statut = (data.get("autorisations") or {}).get(code, u"non_renseigne")
        _checkbox(c, left + 13, top - 77, statut == "oui")
        _checkbox(c, left + 68, top - 77, statut == "non")
        c.setFont("Helvetica", 7.8)
        c.drawString(left + 25, top - 75, u"oui")
        c.drawString(left + 80, top - 75, u"non")
    c.line(x + 5, top - 52, x + w - 5, top - 52)

    y = top - 119
    _cell(c, x + 15, y, u"Je soussigné(e) :",
          data.get("signataire", ""), largeur=w - 30)
    c.setFont("Helvetica", 8.3)
    c.drawString(x + 15, y - 18,
        u"responsable légal de l'enfant, confirme les renseignements et autorisations ci-dessus.")
    _cell(c, x + 15, y - 40, u"À :",
          data.get("ville_signature", ""), largeur=245)
    _cell(c, x + 255, y - 40, u"Le :",
          data.get("date_signature", ""), largeur=220)
    c.drawString(x + 15, y - 59, u"Signature du responsable légal :")
    c.setLineWidth(0.7)
    c.line(x + 185, y - 61, x + w - 10, y - 61)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 15, 48, u"PÊLE-MÊLE SPORTS ET LOISIRS")
    c.setFont("Helvetica", 8)
    c.drawString(x + 15, 35,
                 u"4 RUE DES DEUX GARES - 35130 LA GUERCHE DE BRETAGNE")
    c.drawString(x + 15, 22,
                 u"Document de consultation Noethys - conserver la fiche signée originale")


def GenererPDF(destination, donnees):
    """2 pages A4; aucune lecture BD, aucun email, destination choisie par l'operateur."""
    if not isinstance(donnees, dict):
        raise ValueError("Donnees de fiche invalides")
    if not isinstance(destination, str) or not destination.lower().endswith(".pdf"):
        raise ValueError("Chemin PDF invalide")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    c = canvas.Canvas(destination, pagesize=A4, pageCompression=1)
    c.setTitle(u"Fiche enfant - Pêle-Mêle Sports et Loisirs")
    c.setAuthor(u"Pêle-Mêle Sports et Loisirs - Noethys-SL")
    _page1(c, donnees)
    c.showPage()
    _page2(c, donnees)
    c.showPage()
    c.save()
    return destination
