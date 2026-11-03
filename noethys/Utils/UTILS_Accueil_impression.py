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
AUTORISATIONS_ADOS = (
    ("photos_site_imprimes", u"Photos"),
    ("maquillage", u"Maquillage"),
    ("piscine_baignade", u"Baignade"),
    ("activites_physiques", u"Activités physiques"),
    ("transport_ados", u"Transport"),
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
    ados = data.get("modele") == "ados"
    from reportlab.lib.pagesizes import A4
    largeur, hauteur = A4
    x, w = 42, largeur - 84

    c.setLineWidth(1.5)
    c.rect(x + 92, hauteur - 87, w - 184, 45, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(largeur / 2, hauteur - 60, TITRE)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(largeur / 2, hauteur - 78,
                        u"FICHE ADOS" if ados else SOUS_TITRE)
    if not ados:
        _cell(c, x + 7, hauteur - 115, u"ALSH fréquenté :",
              data.get("alsh", ""), largeur=w - 24)
    _cell(c, x + 7, hauteur - (115 if ados else 134),
          u"Année :", data.get("annee", ""), largeur=w - 24)
    _cell(c, x + 7, hauteur - (136 if ados else 153),
          u"Classe fréquentée durant l'année scolaire :",
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

    _boite(c, x, top, w, 156, SECTIONS_P1[3])
    c.setFont("Helvetica-Bold", 7.5)
    for i, nom in enumerate((u"Nom", u"Prénom", u"Lien de parenté", u"N° téléphone")):
        c.drawCentredString(x + 63 + i * (w / 4), top - 39, nom)
    c.setLineWidth(0.4)
    c.line(x + 5, top - 43, x + w - 5, top - 43)
    for i in range(1, 4):
        cx = x + i * (w / 4)
        c.line(cx, top - 27, cx, top - 118)
    for y in (top - 58, top - 73, top - 88, top - 103, top - 118):
        c.line(x + 5, y, x + w - 5, y)
    accompagnants = list(data.get("accompagnants") or [])
    for i, personne in enumerate(accompagnants[:5]):
        valeurs = (
            personne.get("nom", ""), personne.get("prenom", ""),
            personne.get("lien", ""),
            personne.get("telephone_court") or personne.get("telephone", ""),
        )
        if i == 4 and len(accompagnants) > 5:
            valeurs = (valeurs[0], valeurs[1],
                       u"%s (+%d autres)" % (valeurs[2], len(accompagnants) - 5),
                       valeurs[3])
        for j, valeur in enumerate(valeurs):
            c.setFont("Helvetica", 7.3)
            c.drawString(
                x + 9 + j * (w / 4), top - 54 - i * 15,
                _tronc(valeur, "Helvetica", 7.3, w / 4 - 16))
    if ados:
        c.setFont("Helvetica-Oblique", 7.8)
        c.drawString(x + 10, top - 143,
            u"Je m'engage à communiquer tout changement de cette liste à la direction.")
    else:
        # Depart seul dans la fiche enfant ; sur la fiche ados, ce choix
        # figure dans les autorisations de la seconde page.
        c.setFont("Helvetica-Bold", 8.2)
        c.drawString(x + 10, top - 143,
                     u"Autorisé(e) à quitter l'ALSH seul(e) :")
        statut_depart = (data.get("autorisations") or {}).get(
            "depart_seul", "non_renseigne")
        if statut_depart in ("expire", "a_verifier"):
            c.setFont("Helvetica-Oblique", 8.2)
            c.drawString(x + 352, top - 143, u"À vérifier")
        else:
            _checkbox(c, x + 350, top - 151, statut_depart == "oui")
            c.setFont("Helvetica", 8.2)
            c.drawString(x + 364, top - 143, u"Oui")
            _checkbox(c, x + 410, top - 151, statut_depart == "non")
            c.drawString(x + 424, top - 143, u"Non")
    top -= 164

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
    ados = data.get("modele") == "ados"
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
    autorisations = AUTORISATIONS_ADOS if ados else AUTORISATIONS_PAPIER
    largeur_colonne = w / len(autorisations)
    _boite(c, x, top, w, 143 if ados else 100, SECTIONS_P2[1])
    table_y = top - 38
    for i, (code, libelle) in enumerate(autorisations):
        left = x + i * largeur_colonne
        center = left + largeur_colonne / 2
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(center, table_y,
             _tronc(libelle, "Helvetica-Bold", 7, largeur_colonne - 6))
        if i > 0:
            c.line(left, top - 25, left, top - 98)
        statut = (data.get("autorisations") or {}).get(code, u"non_renseigne")
        if ados:
            x_oui, x_non = left + 7, left + 51
            t_oui, t_non = left + 19, left + 63
        else:
            x_oui, x_non = left + 13, left + 68
            t_oui, t_non = left + 25, left + 80
        _checkbox(c, x_oui, top - 77, statut == "oui")
        _checkbox(c, x_non, top - 77, statut == "non")
        c.setFont("Helvetica", 7.8)
        c.drawString(t_oui, top - 75, u"oui")
        c.drawString(t_non, top - 75, u"non")
    c.line(x + 5, top - 52, x + w - 5, top - 52)

    if ados:
        c.setFont("Helvetica-Bold", 8.0)
        c.drawString(x + 9, top - 119,
            u"J'autorise mon enfant à repartir seul du Club ados à la fin des activités prévues :")
        depart = (data.get("autorisations") or {}).get(
            "depart_seul", "non_renseigne")
        if depart in ("expire", "a_verifier"):
            c.setFont("Helvetica-Oblique", 8.0)
            c.drawString(x + w - 78, top - 136, u"À vérifier")
        else:
            _checkbox(c, x + 347, top - 135, depart == "oui")
            _checkbox(c, x + 414, top - 135, depart == "non")
            c.setFont("Helvetica", 7.8)
            c.drawString(x + 359, top - 133, u"oui")
            c.drawString(x + 426, top - 133, u"non")

    y = top - (160 if ados else 119)
    _cell(c, x + 15, y, u"Je soussigné(e) :",
          data.get("signataire", ""), largeur=w - 30)
    c.setFont("Helvetica", 8.3)
    if ados:
        c.drawString(x + 15, y - 18,
            u"responsable légal, déclare exacts les renseignements de la présente fiche.")
        c.drawString(x + 15, y - 32,
            u"J'autorise les mesures d'urgence nécessaires : soins, hospitalisation ou chirurgie.")
    else:
        c.drawString(x + 15, y - 18,
            u"responsable légal de l'enfant, confirme les renseignements et autorisations ci-dessus.")
    marge_dates = 53 if ados else 40
    marge_signature = 72 if ados else 59
    _cell(c, x + 15, y - marge_dates, u"À :",
          data.get("ville_signature", ""), largeur=245)
    _cell(c, x + 255, y - marge_dates, u"Le :",
          data.get("date_signature", ""), largeur=220)
    c.drawString(x + 15, y - marge_signature, u"Signature du responsable légal :")
    c.setLineWidth(0.7)
    c.line(x + 185, y - marge_signature - 2, x + w - 10, y - marge_signature - 2)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 15, 48, u"PÊLE-MÊLE SPORTS ET LOISIRS")
    c.setFont("Helvetica", 8)
    c.drawString(x + 15, 35,
                 u"4 RUE DES DEUX GARES - 35130 LA GUERCHE DE BRETAGNE")
    c.drawString(x + 15, 22,
                 _tronc(u"%s - conserver la fiche signée originale" %
                        data.get("autorisation_modele", u"Fiche Enfant 2026-11"),
                        "Helvetica", 8, w - 20))


def GenererPDF(destination, donnees):
    """2 pages A4; aucune lecture BD, aucun email, destination choisie par l'operateur."""
    if not isinstance(donnees, dict):
        raise ValueError("Donnees de fiche invalides")
    if not isinstance(destination, str) or not destination.lower().endswith(".pdf"):
        raise ValueError("Chemin PDF invalide")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    c = canvas.Canvas(destination, pagesize=A4, pageCompression=1)
    c.setTitle(u"Fiche %s - Pêle-Mêle Sports et Loisirs" %
               (u"ados" if donnees.get("modele") == "ados" else u"enfant"))
    c.setAuthor(u"Pêle-Mêle Sports et Loisirs - Noethys-SL")
    _page1(c, donnees)
    c.showPage()
    _page2(c, donnees)
    c.showPage()
    c.save()
    return destination

def GenererPDFAdos(destination, donnees):
    """Fiche Club ados en 2 pages A4, sans créer de dossier séparé."""
    if not isinstance(donnees, dict):
        raise ValueError("Donnees de fiche invalides")
    parametres = dict(donnees)
    parametres["modele"] = "ados"
    parametres["autorisation_modele"] = u"Fiche Ados 2026-11"
    return GenererPDF(destination, parametres)
