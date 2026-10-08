# -*- coding: utf-8 -*-
"""Fixture d'une base Noethys SQLite temporaire pour les tests.

Construit un sous-ensemble du schema reel (via GestionDB.CreationTable +
Data.DATA_Tables, le schema canonique) et y insere des donnees
synthetiques et anonymisees, structurellement proches d'un cas reel de
convention d'encadrement sportif mais sans aucune donnee personnelle ou
associative reelle.

N'importe jamais depuis le dossier "references" (sauvegarde de recette
reelle, hors depot, jamais utilisee par les tests).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import _garde_reseau  # noqa: E402,F401  (aucune connexion à une base réseau)
import GestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

_DB_ORIGINALE = GestionDB.DB


class _DBRedirigeeVersFichierTest(_DB_ORIGINALE):
    """ GestionDB.DB() sans argument se resout normalement via un fichier
    de configuration sur disque ou une fenetre wx active (aucun des deux
    n'existe en test). Cette sous-classe redirige uniquement les appels
    "par defaut" (aucun nomFichier explicite) vers la base de test, sans
    toucher au comportement des appels qui precisent deja un fichier
    (ex. GestionDB.DB(suffixe="PHOTOS")). """

    chemin_test = None

    def __init__(self, suffixe="DATA", nomFichier="", modeCreation=False, IDconnexion=None, pooling=True):
        if nomFichier == "" and _DBRedirigeeVersFichierTest.chemin_test:
            nomFichier = _DBRedirigeeVersFichierTest.chemin_test
            suffixe = None
        _DB_ORIGINALE.__init__(
            self, suffixe=suffixe, nomFichier=nomFichier,
            modeCreation=modeCreation, IDconnexion=IDconnexion, pooling=pooling,
        )


class RedirectionGestionDB:
    """ Contexte : le temps du bloc, GestionDB.DB() (sans argument) ouvre
    la base de test donnee au lieu de la base par defaut de Noethys.
    Utilise uniquement pour exercer le vrai moteur Noedoc (qui appelle
    toujours GestionDB.DB() en interne, sans parametre injectable) contre
    une base de test isolee, jamais contre une vraie base. """

    def __init__(self, chemin):
        self.chemin = chemin

    def __enter__(self):
        _DBRedirigeeVersFichierTest.chemin_test = self.chemin
        GestionDB.DB = _DBRedirigeeVersFichierTest
        return self

    def __exit__(self, *exc_info):
        GestionDB.DB = _DB_ORIGINALE
        _DBRedirigeeVersFichierTest.chemin_test = None


TABLES_REQUISES = (
    "organisateur", "familles", "individus", "rattachements",
    "activites", "groupes", "unites", "consommations", "prestations",
    "agrements", "documents_modeles", "documents_objets",
    # Tables interrogees sans condition par UTILS_Infos_individus.Informations
    # (representant/famille) et par GetNomsChampsPossibles/GetQuestions
    # (questionnaires) : vides ici, juste pour eviter les erreurs
    # "no such table" bruyantes dans les tests.
    "secteurs", "caisses", "regimes", "liens", "parametres",
    "medecins", "categories_travail",
    "questionnaire_categories", "questionnaire_questions", "questionnaire_choix",
)


class BaseTest:
    """Cree une base SQLite temporaire, la detruit a la fermeture."""

    def __init__(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="noethys-test-db-")
        self.chemin = str(Path(self._tmpdir.name) / "test.dat")
        self.db = GestionDB.DB(nomFichier=self.chemin, suffixe=None, modeCreation=True)
        for nom_table in TABLES_REQUISES:
            self.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)
        self.db.Commit()

    def inserer(self, table, colonnes, lignes):
        placeholders = ", ".join(colonnes)
        for ligne in lignes:
            valeurs = ", ".join(_sql_valeur(v) for v in ligne)
            self.db.ExecuterReq(
                "INSERT INTO %s (%s) VALUES (%s);" % (table, placeholders, valeurs)
            )
        self.db.Commit()

    def fermer(self):
        self.db.Close()
        self._tmpdir.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.fermer()


def _sql_valeur(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    texte = str(v).replace("'", "''")
    return "'%s'" % texte


def creer_base_association_simple():
    """Structure anonymisee proche d'Atout Sports : deux creneaux hebdo recurrents."""
    base = BaseTest()

    base.inserer(
        "organisateur",
        ["IDorganisateur", "nom", "rue", "cp", "ville", "tel", "mail"],
        [(1, "Association Test Loisirs", "1 rue des Tests", "00000", "Testville", "00.00.00.00.00", "test@example.org")],
    )
    base.inserer("familles", ["IDfamille"], [(1,)])
    base.inserer(
        "individus",
        ["IDindividu", "nom", "prenom", "IDcivilite"],
        [
            (1, "STRUCTURE SPORTIVE TEST", "", 3),
            (2, "STRUCTURE SPORTIVE TEST", "Groupe A enfants", 3),
            (3, "STRUCTURE SPORTIVE TEST", "Groupe B adultes", 3),
            (4, "DUPUIS", "Jean", 1),
        ],
    )
    base.inserer(
        "rattachements",
        ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"],
        [
            (1, 1, 1, 1, 1),
            (2, 1, 2, 2, 0),
            (3, 1, 3, 2, 0),
            (4, 1, 4, 1, 0),
        ],
    )
    base.inserer(
        "activites",
        ["IDactivite", "nom"],
        [(10, "Encadrement sportif enfants"), (11, "Encadrement sportif adultes")],
    )
    base.inserer(
        "groupes",
        ["IDgroupe", "IDactivite", "nom"],
        [(20, 10, "Enfants"), (21, 11, "Adultes")],
    )
    base.inserer(
        "unites",
        ["IDunite", "IDactivite", "nom", "ordre", "type"],
        [(30, 10, "Enfant", 1, "Horaire"), (31, 11, "Adulte", 1, "Horaire")],
    )

    lignes_conso = []
    lignes_prestation = []
    IDprestation = 100
    IDconso = 1000
    # Groupe A enfants : mercredi 17h30-19h00, 24 euros/h -> 36.00 la seance
    for jour in ("2026-09-02", "2026-09-09", "2026-09-16"):
        lignes_prestation.append((IDprestation, "Encadrement sportif enfants", 36.00))
        lignes_conso.append((IDconso, 2, 10, jour, 30, "17:30", "19:00", "reservation", 20, IDprestation))
        IDprestation += 1
        IDconso += 1
    # Groupe B adultes : lundi 19h30-20h30, 36.50 euros/h -> 36.50 la seance
    for jour in ("2026-09-07", "2026-09-14", "2026-09-21"):
        lignes_prestation.append((IDprestation, "Encadrement sportif adultes", 36.50))
        lignes_conso.append((IDconso, 3, 11, jour, 31, "19:30", "20:30", "reservation", 21, IDprestation))
        IDprestation += 1
        IDconso += 1

    base.inserer(
        "prestations",
        ["IDprestation", "label", "montant"],
        lignes_prestation,
    )
    base.inserer(
        "consommations",
        ["IDconso", "IDindividu", "IDactivite", "date", "IDunite", "heure_debut", "heure_fin", "etat", "IDgroupe", "IDprestation"],
        lignes_conso,
    )
    return base


def _dates_hebdomadaires(premiere_date, nombre, pas_jours=7):
    d = premiere_date
    dates = []
    for _i in range(nombre):
        dates.append(d.isoformat())
        d = d + __import__("datetime").timedelta(days=pas_jours)
    return dates


def creer_base_ecole_simple():
    """ Structure fictive proche d'une convention scolaire longue (type
    "La Providence") : une famille "ecole", trois cycles (individus
    distincts) avec plusieurs periodes chacun, dont au moins un vrai
    trou de vacances (deux blocs separes de plusieurs mois sur le meme
    creneau) et une exception ponctuelle d'horaire. Aucun nom, aucune
    donnee reelle : tout est fictif. """
    import datetime

    base = BaseTest()

    base.inserer(
        "organisateur",
        ["IDorganisateur", "nom", "rue", "cp", "ville", "tel", "mail"],
        [(1, "Association Test Loisirs", "1 rue des Tests", "00000", "Testville", "00.00.00.00.00", "test@example.org")],
    )
    base.inserer("familles", ["IDfamille"], [(2,)])
    base.inserer(
        "individus",
        ["IDindividu", "nom", "prenom", "IDcivilite"],
        [
            (10, "ECOLE FICTIVE TEST", "", 3),
            (11, "MARTIN", "Alice", 1),  # représentant réellement nommé
            (20, "CE2-CM1-CM2", "CYCLE FICTIF 3", 3),
            (21, "CP-CE1-CE2", "CYCLE FICTIF 2", 3),
            (22, "PS-MS-GS", "CYCLE FICTIF 1", 3),
        ],
    )
    base.inserer(
        "rattachements",
        ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"],
        [
            (10, 2, 10, 1, 1),
            (11, 2, 11, 1, 0),
            (20, 2, 20, 2, 0),
            (21, 2, 21, 2, 0),
            (22, 2, 22, 2, 0),
        ],
    )
    base.inserer(
        "activites", ["IDactivite", "nom"],
        [(30, "Encadrement sportif scolaires")],
    )
    base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(40, 30, "Scolaires")])
    base.inserer("unites", ["IDunite", "IDactivite", "nom", "ordre", "type"], [(50, 30, "Scolaires", 1, "Horaire")])

    lignes_conso = []
    lignes_prestation = []
    IDprestation = 200
    IDconso = 2000

    def _ajoute(IDindividu, dates, heure_debut, heure_fin, montant):
        nonlocal IDprestation, IDconso
        for jour in dates:
            lignes_prestation.append((IDprestation, "Encadrement sportif scolaires", montant))
            lignes_conso.append((IDconso, IDindividu, 30, jour, 50, heure_debut, heure_fin, "reservation", 40, IDprestation))
            IDprestation += 1
            IDconso += 1

    # Cycle 3 : une seule période continue, 6 séances hebdomadaires, 2h chacune.
    _ajoute(20, _dates_hebdomadaires(datetime.date(2026, 10, 8), 6), "09:00", "11:00", 40.0)

    # Cycle 2 : deux périodes séparées par les vacances (vrai trou de 7 mois),
    # même jour/horaire dans les deux blocs.
    _ajoute(21, _dates_hebdomadaires(datetime.date(2026, 9, 10), 4), "09:00", "12:00", 60.0)
    _ajoute(21, _dates_hebdomadaires(datetime.date(2027, 5, 20), 4), "09:00", "12:00", 60.0)

    # Cycle 1 : jeudi 2h + vendredi 1h en alternance (durées différentes),
    # plus une exception ponctuelle d'horaire l'après-midi.
    _ajoute(22, _dates_hebdomadaires(datetime.date(2026, 11, 26), 4, pas_jours=7), "09:00", "11:00", 40.0)
    _ajoute(22, _dates_hebdomadaires(datetime.date(2026, 11, 27), 4, pas_jours=7), "10:00", "11:00", 20.0)
    _ajoute(22, [datetime.date(2027, 1, 14).isoformat()], "13:15", "16:15", 60.0)  # exception d'horaire

    base.inserer(
        "prestations", ["IDprestation", "label", "montant"], lignes_prestation,
    )
    base.inserer(
        "consommations",
        ["IDconso", "IDindividu", "IDactivite", "date", "IDunite", "heure_debut", "heure_fin", "etat", "IDgroupe", "IDprestation"],
        lignes_conso,
    )
    return base


def creer_base_tarif_ambigu_simple():
    """ Structure fictive minimale ou une meme activite presente deux
    montants differents pour une meme duree de seance : DetecterTarifs()
    doit alors refuser de proposer un taux automatique (mode="manuel"),
    et {CONVENTION_TARIF_HORAIRE} doit rester vide tant qu'aucun
    override n'est fourni. """
    base = BaseTest()
    base.inserer(
        "organisateur",
        ["IDorganisateur", "nom", "rue", "cp", "ville", "tel", "mail"],
        [(1, "Association Test Loisirs", "1 rue des Tests", "00000", "Testville", "00.00.00.00.00", "test@example.org")],
    )
    base.inserer("familles", ["IDfamille"], [(1,)])
    base.inserer(
        "individus",
        ["IDindividu", "nom", "prenom", "IDcivilite"],
        [(1, "STRUCTURE TEST", "", 3), (2, "STRUCTURE TEST", "Groupe ambigu", 3)],
    )
    base.inserer(
        "rattachements",
        ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"],
        [(1, 1, 1, 1, 1), (2, 1, 2, 2, 0)],
    )
    base.inserer("activites", ["IDactivite", "nom"], [(10, "Activite ambigue")])
    base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(20, 10, "Groupe")])
    base.inserer("unites", ["IDunite", "IDactivite", "nom", "ordre", "type"], [(30, 10, "Unite", 1, "Horaire")])
    base.inserer(
        "prestations",
        ["IDprestation", "label", "montant"],
        [(100, "Tarif A", 30.00), (101, "Tarif B", 50.00)],
    )
    base.inserer(
        "consommations",
        ["IDconso", "IDindividu", "IDactivite", "date", "IDunite", "heure_debut", "heure_fin", "etat", "IDgroupe", "IDprestation"],
        [
            # Deux seances de meme duree (1h), montants differents : la
            # meme activite ne peut donc pas avoir de taux horaire unique.
            (1000, 2, 10, "2026-09-01", 30, "10:00", "11:00", "reservation", 20, 100),
            (1001, 2, 10, "2026-09-08", 30, "10:00", "11:00", "reservation", 20, 101),
        ],
    )
    return base


_DEFAUTS_OBJET = {
    "nbreMax": None, "obligatoire": 0, "points": None, "image": None,
    "typeImage": None, "verrouillageX": 0, "verrouillageY": 0,
    "Xmodifiable": 1, "Ymodifiable": 1, "largeurModifiable": 1,
    "hauteurModifiable": 1, "largeurMin": 1, "largeurMax": 10000,
    "hauteurMin": 1, "hauteurMax": 10000, "verrouillageLargeur": 0,
    "verrouillageHauteur": 0, "verrouillageProportions": 0,
    "interditModifProportions": 0, "couleurTrait": None, "styleTrait": "Transparent",
    "epaissTrait": 1.0, "coulRemplis": None, "styleRemplis": "Transparent",
    "couleurTexte": "(0, 0, 0)", "couleurFond": None, "padding": 0.0,
    "interligne": 1.0, "taillePolice": 9, "nomPolice": "", "familyPolice": 74,
    "stylePolice": 90, "weightPolice": 90, "soulignePolice": 0,
    "alignement": "left", "largeurTexte": None, "norme": None,
    "afficheNumero": None, "IDdonnee": None, "champ": None, "texte": None,
}


def inserer_modele_document(base, nom, categorie, objets):
    """ Insere un modele documents_modeles/documents_objets synthetique,
    en suivant exactement le meme schema que
    Utils.UTILS_Export_documents.Importer() (mais sans dependre de la
    connexion par defaut de GestionDB : on ecrit directement sur la base
    de test injectee). Contenu entierement fictif : aucun texte, nom ou
    donnee reelle de PMSL/Atout Sports/La Providence.
    """
    IDmodele = base.db.ReqInsert("documents_modeles", [
        ("nom", nom), ("categorie", categorie), ("supprimable", 1),
        ("largeur", 210), ("hauteur", 297), ("observations", ""),
        ("IDfond", None), ("defaut", 0),
    ])
    for objet in objets:
        valeurs = dict(_DEFAUTS_OBJET)
        valeurs.update(objet)
        valeurs["IDmodele"] = IDmodele
        base.db.ReqInsert("documents_objets", list(valeurs.items()))
    base.db.Commit()
    return IDmodele


def inserer_modele_convention_fictif(base):
    """ Modele de convention fictif : cadre principal + deux blocs de
    texte utilisant la syntaxe reelle {CHAMP}/[[SI ...]], mais avec un
    contenu entierement invente pour les tests (aucun article, aucune
    identite PMSL). """
    objets = [
        {
            "nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
            "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250,
        },
        {
            "nom": "Titre", "categorie": "bloc_texte", "ordre": 1,
            "x": 20, "y": 270, "largeur": 170,
            "texte": "CONVENTION DE TEST {CONVENTION_SAISON}",
        },
        {
            "nom": "Corps", "categorie": "bloc_texte", "ordre": 2,
            "x": 13, "y": 20, "largeur": 182,
            "texte": (
                "ENTRE : {ORGANISATEUR_NOM}\n"
                "ET : {FAMILLE_NOM}\n\n"
                "ARTICLE FICTIF 1 : ENGAGEMENT\n"
                "Ceci est un article de test.[[SI {CONVENTION_REPRESENTANT_NOM_COMPLET}<>-> Representant : {CONVENTION_REPRESENTANT_NOM_COMPLET}.]]\n\n"
                "ARTICLE FICTIF 2 : PLANNING\n"
                "{CONVENTION_PLANNING_DETAIL}\n\n"
                "Volume total : {CONVENTION_PLANNING_TOTAL_HEURES}"
            ),
        },
    ]
    return inserer_modele_document(base, "Convention de test", "convention", objets)


def inserer_modele_convention_scolaire_fictif(base):
    """ Deuxieme modele de recette, de taille comparable a une vraie
    convention scolaire longue (type "La Providence") : en-tete, parties,
    6 articles fictifs, tarif, signatures -- avec le detail de planning
    scolaire dynamique insere dans l'article 2. Aucun nom, lieu, date ou
    discipline reel : tout le texte editorial est invente pour la
    recette. Le detail de planning genere par
    UTILS_Convention_champs.GetResumePlanning() est la seule partie
    dynamique. """
    corps = (
        "CONVENTION DE TEST {CONVENTION_SAISON}\n\n"
        "ENTRE :\n"
        "{ORGANISATEUR_NOM}\n"
        "{ORGANISATEUR_RUE}\n"
        "{ORGANISATEUR_CP} {ORGANISATEUR_VILLE}\n\n"
        "ET :\n"
        "{FAMILLE_NOM}\n"
        "[[SI {CONVENTION_REPRESENTANT_NOM_COMPLET}<>->Représenté(e) par {CONVENTION_REPRESENTANT_NOM_COMPLET}.]]\n\n"
        "Il a été convenu ce qui suit :\n\n"

        "ARTICLE FICTIF 1 : ENGAGEMENT\n"
        "Ceci est un texte d'engagement fictif de test, suffisamment long pour occuper "
        "plusieurs lignes dans le cadre principal du document, comme un vrai article de "
        "convention le ferait dans un cas réel. Aucune donnée réelle n'apparaît ici. "
        "La structure organisatrice met à disposition de l'établissement fictif un "
        "intervenant pour accompagner l'équipe pédagogique dans la mise en place des "
        "séances prévues au présent document de test, selon les modalités décrites "
        "dans les articles suivants, pour la durée de la période convenue entre les "
        "deux parties signataires de ce document fictif de recette.\n\n"

        "ARTICLE FICTIF 2 : PLANNING\n"
        "Un calendrier prévisionnel est joint à la présente convention à titre indicatif. "
        "Il appartient à l'établissement nommé ci-dessus de le vérifier et de le signer. "
        "Le détail ci-dessous est calculé automatiquement depuis les données "
        "d'inscription réellement enregistrées, groupe par groupe :\n\n"
        "{CONVENTION_PLANNING_DETAIL}\n\n"
        "Nombre total de séances : {CONVENTION_PLANNING_NBRE_SEANCES}\n"
        "Volume horaire total : {CONVENTION_PLANNING_TOTAL_HEURES}\n\n"

        "ARTICLE FICTIF 3 : ABSENCE ET ANNULATION\n"
        "Texte fictif de test décrivant les modalités d'absence et d'annulation, "
        "reproduisant la longueur habituelle de ce type d'article dans un document réel, "
        "pour vérifier que la pagination se comporte correctement sur un contenu réaliste "
        "plutôt que sur un texte artificiellement court. Pour des raisons de formation, "
        "l'intervenant fictif peut être amené à s'absenter ; dans ce cas et pour toute "
        "autre absence prévisible, l'établissement fictif sera prévenu au moins quinze "
        "jours à l'avance et, dans la mesure du possible, il sera procédé à son "
        "remplacement par un autre intervenant fictif de la structure organisatrice.\n"
        "Si, pour des raisons qui devront être précisées, l'établissement devait annuler "
        "une séance de test, le secrétariat fictif devra en être prévenu au moins une "
        "semaine à l'avance, par tout moyen écrit convenu entre les parties. À défaut "
        "d'un tel préavis, la séance de test annulée pourra être comptabilisée comme "
        "réalisée dans le décompte prévisionnel fictif figurant à l'article précédent, "
        "sauf accord contraire formalisé entre les deux parties signataires du présent "
        "document de recette.\n\n"

        "ARTICLE FICTIF 4 : RESPONSABILITÉS\n"
        "Texte fictif de test décrivant les responsabilités respectives des parties, "
        "à nouveau de longueur comparable à un article réel, afin que le test de "
        "pagination reste représentatif d'un document complet plutôt que d'un "
        "extrait artificiellement réduit à quelques mots. La structure organisatrice "
        "fictive gère les intervenants mis à disposition des établissements partenaires "
        "fictifs du territoire de test ; ces intervenants restent placés sous la "
        "responsabilité de la structure organisatrice fictive en sa qualité d'employeur "
        "et déclinent toute responsabilité en dehors de leurs heures d'encadrement "
        "prévues au planning ci-dessus.\n"
        "La structure organisatrice fictive assure la protection morale et physique des "
        "participants fictifs au sein des activités que son personnel de test anime, "
        "dans le respect de la législation du travail et des textes applicables à "
        "l'encadrement d'enfants et d'adolescents. En sa qualité d'employeur fictif, "
        "elle déclare et verse les cotisations sociales de son personnel de test aux "
        "organismes habilités, et son action professionnelle de test est régie par la "
        "convention collective fictive applicable à ce secteur d'activité de recette.\n\n"

        "ARTICLE FICTIF 5 : LITIGES\n"
        "Texte fictif de test décrivant le règlement des litiges éventuels entre les "
        "parties signataires de la présente convention de test. Tout litige relatif à "
        "l'exécution du présent document fictif doit être porté à la connaissance du "
        "responsable de l'établissement fictif et de la direction de la structure "
        "organisatrice fictive ; à défaut de règlement amiable entre les parties, le "
        "litige de test sera porté devant la juridiction fictivement compétente.\n\n"

        "ARTICLE FICTIF 6 : FACTURATION\n"
        "Le tarif horaire applicable pour la présente convention de test est de "
        "[[SI {CONVENTION_TARIF_HORAIRE}<>->{CONVENTION_TARIF_HORAIRE} par heure encadrée.]]"
        "[[SI {CONVENTION_TARIF_HORAIRE}=->à préciser manuellement (aucun taux horaire "
        "unique n'a pu être déterminé automatiquement).]]\n\n"

        "Fait en deux exemplaires, le .............................\n\n"
        "Pour la structure adhérente\t\tPour {ORGANISATEUR_NOM}\n"
        "Signature\t\t\t\tSignature"
    )
    objets = [
        # Cadre principal volontairement moins haut que la page complète
        # (140 mm sur 297 mm) : dans un vrai modèle, l'espace au-dessus
        # est occupé par un en-tête/logo, comme le montrent les documents
        # réels de référence -- ce n'est pas un artifice pour forcer la
        # pagination, c'est une mise en page réaliste.
        {
            "nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
            "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 140,
        },
        {
            "nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
            "x": 13, "y": 20, "largeur": 182, "texte": corps,
        },
    ]
    return inserer_modele_document(base, "Convention scolaire de test", "convention", objets)
