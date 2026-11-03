# -*- coding: utf-8 -*-
"""AFAS V2 -- outils de recette (aucune donnée réelle dans le dépôt).

    python tests/recette_afas2.py peupler <fichier Recette_DATA.dat> [--parametrer]
        Ajoute le jeu FICTIF de tests/afas2_base_fictive.py au fichier de
        recette créé par tests/recette_creer_fichier_fictif.py (recette
        visuelle Windows). --parametrer enregistre aussi le référentiel et
        les trois presets fictifs.

    python tests/recette_afas2.py extraire <source> <extrait.dat> --annee AAAA
        Extraction MINIMALE et pseudonymisée d'une copie de base Noethys
        (fichier SQLite, ou chaîne GestionDB MySQL d'une copie restaurée en
        local) : seules les tables et colonnes nécessaires au calcul AFAS sont
        copiées, de N-1 à N ; noms remplacés par des pseudonymes, libellés
        supprimés, montants réduits à leur signe. La source n'est lue qu'en
        SELECT ; l'extrait est un nouveau fichier SQLite.

    python tests/recette_afas2.py rapprocher <extrait.dat> --annee AAAA --phase reel
            --preset <nom du preset> --attendus <attendus.csv> --sortie <dossier>
        Calcule la déclaration sur l'extrait et la rapproche des chiffres de
        référence (attendus.csv : « indicateur;heures », par exemple les heures
        déclarées à la Caf pour cette année). Écrit le rapprochement par
        indicateur, la ventilation par mois et par site, et l'export de
        contrôle complet.
"""
import argparse
import csv
import datetime
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for chemin in (os.path.join(RACINE, "noethys"), os.path.join(RACINE, "tests")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

DELAI_REGULARISATIONS = datetime.timedelta(days=92)
CATEGORIES_PROFILS_COPIES = ("afas_v2_referentiel", "afas_v2_preset")


# --------------------------------------------------------------------------
# Lecture seule de la source
# --------------------------------------------------------------------------

class SourceLectureSeule(object):
    """Connexion GestionDB n'exécutant que des SELECT."""

    def __init__(self, nom):
        import GestionDB
        if "[RESEAU]" not in nom and not os.path.isfile(nom):
            raise SystemExit("Source introuvable : %s" % nom)
        self.db = GestionDB.DB(nomFichier=nom, suffixe=None)
        if getattr(self.db, "echec", 0):
            raise SystemExit("Source illisible : %s" % getattr(self.db, "erreur", ""))

    def lire(self, req):
        if not req.lstrip().upper().startswith("SELECT"):
            raise AssertionError("Lecture seule : %s" % req[:40])
        self.db.cursor.execute(req)
        return list(self.db.cursor.fetchall())

    def fermer(self):
        self.db.Close()


def _liste(valeurs):
    valeurs = sorted({int(v) for v in valeurs if v not in (None, "")})
    return ", ".join(str(v) for v in valeurs) if valeurs else "NULL"


def _signe(montant):
    if montant is None:
        return None
    return -1.0 if montant < 0 else (1.0 if montant > 0 else 0.0)


def Extraire(source, destination, annee):
    """Crée `destination` (nouveau fichier SQLite) avec le strict nécessaire au
    calcul AFAS des années annee-1 et annee. Retourne les effectifs copiés."""
    import GestionDB
    from Data import DATA_Tables as Tables
    if os.path.exists(destination):
        raise SystemExit("Le fichier d'extrait existe déjà : %s" % destination)
    debut = datetime.date(annee - 1, 1, 1)
    fin = datetime.date(annee, 12, 31)
    src = SourceLectureSeule(source)
    try:
        activites = src.lire("SELECT IDactivite, nom, abrege FROM activites;")
        groupes = src.lire("SELECT IDgroupe, IDactivite, nom, ordre FROM groupes;")
        unites = src.lire("SELECT IDunite, IDactivite, nom, abrege, type, heure_debut, heure_fin, ordre FROM unites;")
        ouvertures = src.lire("SELECT IDactivite, IDunite, IDgroupe, date FROM ouvertures WHERE date>='%s' AND date<='%s';"
                              % (debut, fin))
        vacances = src.lire("SELECT IDvacance, nom, annee, date_debut, date_fin FROM vacances;")
        consos = src.lire("""SELECT IDconso, IDindividu, IDactivite, date, IDunite, IDgroupe, heure_debut, heure_fin, etat,
            quantite, IDprestation FROM consommations WHERE date>='%s' AND date<='%s';""" % (debut, fin))
        individus = {c[1] for c in consos}
        prestations = src.lire("""SELECT IDprestation, IDindividu, IDfamille, IDactivite, IDfacture, montant, forfait,
            forfait_date_debut, date, categorie FROM prestations WHERE IDprestation IN (%s);""" % _liste(c[10] for c in consos))
        familles = {p[2] for p in prestations}
        regularisations = src.lire("""SELECT IDprestation, IDindividu, IDfamille, IDactivite, IDfacture, montant, forfait,
            forfait_date_debut, date, categorie FROM prestations WHERE montant < 0 AND date>='%s' AND date<='%s'
            AND (IDindividu IN (%s) OR IDfamille IN (%s));""" % (debut, fin + DELAI_REGULARISATIONS, _liste(individus),
                                                                 _liste(familles)))
        toutes = {p[0]: p for p in prestations + regularisations}
        factures = src.lire("SELECT IDfacture, numero, etat, date_edition FROM factures WHERE IDfacture IN (%s);"
                            % _liste(p[4] for p in toutes.values()))
        aeeh = src.lire("SELECT IDperiode, IDindividu, date_debut, date_fin FROM aeeh_periodes WHERE IDindividu IN (%s);"
                        % _liste(individus))
        profils = src.lire("SELECT IDprofil, label, categorie, defaut FROM profils WHERE categorie IN (%s);"
                           % ", ".join("'%s'" % c for c in CATEGORIES_PROFILS_COPIES))
        parametres = src.lire("SELECT IDprofil, nom, parametre, type_donnee FROM profils_parametres WHERE IDprofil IN (%s);"
                              % _liste(p[0] for p in profils))
    finally:
        src.fermer()

    db = GestionDB.DB(nomFichier=destination, suffixe=None, modeCreation=True)
    try:
        import afas2_base_fictive as F
        for table in F.TABLES:
            db.CreationTable(table, dicoDB=Tables.DB_DATA)

        def inserer(table, colonnes, lignes):
            db.Executermany("INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(colonnes), ", ".join("?" * len(colonnes))),
                            [tuple(l) for l in lignes], commit=False)
        inserer("activites", ["IDactivite", "nom", "abrege"], activites)
        inserer("groupes", ["IDgroupe", "IDactivite", "nom", "ordre"], groupes)
        inserer("unites", ["IDunite", "IDactivite", "nom", "abrege", "type", "heure_debut", "heure_fin", "ordre"], unites)
        inserer("ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"], ouvertures)
        inserer("vacances", ["IDvacance", "nom", "annee", "date_debut", "date_fin"], vacances)
        inserer("consommations", ["IDconso", "IDindividu", "IDactivite", "date", "IDunite", "IDgroupe", "heure_debut",
                                  "heure_fin", "etat", "quantite", "IDprestation"], consos)
        inserer("prestations", ["IDprestation", "IDindividu", "IDfamille", "IDactivite", "IDfacture", "montant", "forfait",
                                "forfait_date_debut", "date", "categorie", "label"],
                [p[:5] + (_signe(p[5]),) + p[6:] + ("",) for p in toutes.values()])
        inserer("factures", ["IDfacture", "numero", "etat", "date_edition"], [(f[0], f[0], f[2], f[3]) for f in factures])
        inserer("individus", ["IDindividu", "IDcivilite", "nom", "prenom"],
                [(i, 4, "ENFANT", "n° %d" % i) for i in sorted(i for i in individus if i is not None)])
        inserer("familles", ["IDfamille"], [(f,) for f in sorted(f for f in familles if f is not None)])
        inserer("aeeh_periodes", ["IDperiode", "IDindividu", "date_debut", "date_fin"], aeeh)
        inserer("profils", ["IDprofil", "label", "categorie", "defaut"], profils)
        inserer("profils_parametres", ["IDprofil", "nom", "parametre", "type_donnee"], parametres)
        db.Commit()
    finally:
        db.Close()
    return {"consommations": len(consos), "prestations": len(toutes), "individus": len(individus),
            "factures": len(factures), "ouvertures": len(ouvertures), "profils": len(profils)}


# --------------------------------------------------------------------------
# Rapprochement
# --------------------------------------------------------------------------

def LireAttendus(chemin):
    """attendus.csv : « indicateur;heures » (heures décimales, virgule admise)."""
    attendus = {}
    with open(chemin, encoding="utf-8-sig") as fichier:
        for ligne in csv.reader(fichier, delimiter=";"):
            if not ligne or ligne[0].strip().startswith("#") or ligne[0].strip() == "indicateur":
                continue
            attendus[ligne[0].strip()] = float(ligne[1].replace(",", ".").strip())
    return attendus


def Rapprocher(rapport, attendus):
    """Lignes (indicateur, libellé, calculé, attendu, écart, écart %) en heures décimales."""
    lignes = []
    for ligne in rapport["indicateurs"]:
        calcule = ligne["total"]
        if not isinstance(calcule, int):
            continue
        heures = calcule / 3600.0
        attendu = attendus.get(ligne["cle"])
        ecart = None if attendu is None else heures - attendu
        pourcentage = None if not attendu else 100.0 * ecart / attendu
        lignes.append((ligne["cle"], ligne["libelle"], round(heures, 2), attendu,
                       None if ecart is None else round(ecart, 2), None if pourcentage is None else round(pourcentage, 2)))
    return lignes


def Ventilation(rapport):
    """Heures réalisées et facturées par mois et par site (contrôle des écarts)."""
    sites = {}
    for ligne in rapport["lignes"]:
        sites.setdefault((str(ligne["date"]), ligne["IDindividu"]), ligne["site"])
    totaux = {}
    for jour in rapport["jours"]:
        cle = (str(jour["date"])[:7], sites.get((str(jour["date"]), jour["IDindividu"]), ""))
        valeur = totaux.setdefault(cle, [0, 0, 0])
        valeur[0] += jour["heures_realisees"] or 0
        valeur[1] += jour["heures_facturees"] or 0
        valeur[2] += 1
    return [(mois, site, round(r / 3600.0, 2), round(f / 3600.0, 2), n) for (mois, site), (r, f, n) in sorted(totaux.items())]


def _ecrire(chemin, entete, lignes):
    with open(chemin, "w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.writer(fichier, delimiter=";")
        writer.writerow(entete)
        for ligne in lignes:
            writer.writerow(["" if v is None else (("%.2f" % v).replace(".", ",") if isinstance(v, float) else v) for v in ligne])


def ExecuterRapprochement(extrait, annee, phase, nom_preset, attendus, sortie, date_reference=None):
    from _fixtures_noethys_db import RedirectionGestionDB
    from Utils import UTILS_AFAS2_Declaration as DECL
    from Utils import UTILS_AFAS2_Presets as P
    from Utils import UTILS_AFAS2_Referentiel as R
    os.makedirs(sortie, exist_ok=True)
    with RedirectionGestionDB(extrait):
        referentiel = R.ChargerReferentiel()
        choix = [ID for ID, nom in P.ListerPresets() if nom == nom_preset]
        if len(choix) != 1:
            raise SystemExit("Preset introuvable dans l'extrait : %s" % nom_preset)
        preset = P.ChargerPreset(choix[0])
        rapport = DECL.Executer(preset, referentiel, annee, phase, date_reference=date_reference)
    chemins = DECL.ExporterControle(sortie, rapport, "rapprochement_%d" % annee)
    chemins["rapprochement"] = os.path.join(sortie, "rapprochement_%d_indicateurs.csv" % annee)
    _ecrire(chemins["rapprochement"], ["Indicateur", "Libellé", "Calculé (h)", "Référence (h)", "Écart (h)", "Écart (%)"],
            Rapprocher(rapport, attendus))
    chemins["ventilation"] = os.path.join(sortie, "rapprochement_%d_mois_sites.csv" % annee)
    _ecrire(chemins["ventilation"], ["Mois", "Site", "Réalisé (h)", "Facturé (h)", "Jours-enfants"], Ventilation(rapport))
    return rapport, chemins


# --------------------------------------------------------------------------
# Recette visuelle : peuplement du fichier fictif
# --------------------------------------------------------------------------

def Peupler(fichier, parametrer=False):
    import GestionDB
    import afas2_base_fictive as F
    from _fixtures_noethys_db import RedirectionGestionDB
    from Utils import UTILS_AFAS2_Presets as P
    from Utils import UTILS_AFAS2_Referentiel as R
    if not os.path.isfile(fichier):
        raise SystemExit("Fichier de recette introuvable : %s" % fichier)
    db = GestionDB.DB(nomFichier=fichier, suffixe=None)
    try:
        db.cursor.execute("SELECT COUNT(*) FROM activites WHERE IDactivite=%d;" % F.ACTIVITE)
        if db.cursor.fetchall()[0][0]:
            raise SystemExit("Le jeu AFAS fictif est déjà présent dans ce fichier.")
        F.Peupler(db)
    finally:
        db.Close()
    if parametrer:
        with RedirectionGestionDB(fichier):
            R.EnregistrerReferentiel(F.Referentiel())
            for preset in F.Presets():
                P.EnregistrerPreset(preset)


def main(arguments=None):
    import _garde_reseau  # noqa: F401  (aucune connexion réseau hors serveur local déclaré)
    analyse = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commandes = analyse.add_subparsers(dest="commande", required=True)
    peupler = commandes.add_parser("peupler")
    peupler.add_argument("fichier")
    peupler.add_argument("--parametrer", action="store_true")
    extraire = commandes.add_parser("extraire")
    extraire.add_argument("source")
    extraire.add_argument("extrait")
    extraire.add_argument("--annee", type=int, required=True)
    rapprocher = commandes.add_parser("rapprocher")
    rapprocher.add_argument("extrait")
    rapprocher.add_argument("--annee", type=int, required=True)
    rapprocher.add_argument("--phase", default="reel")
    rapprocher.add_argument("--preset", required=True)
    rapprocher.add_argument("--attendus", required=True)
    rapprocher.add_argument("--sortie", required=True)
    args = analyse.parse_args(arguments)
    if args.commande == "peupler":
        Peupler(args.fichier, args.parametrer)
        print("Jeu AFAS fictif ajouté à %s" % args.fichier)
    elif args.commande == "extraire":
        print(Extraire(args.source, args.extrait, args.annee))
    else:
        rapport, chemins = ExecuterRapprochement(args.extrait, args.annee, args.phase, args.preset,
                                                 LireAttendus(args.attendus), args.sortie)
        print("Validable : %s" % ("oui" if rapport["validable"] else "non — " + " ; ".join(rapport["motifs_non_validable"])))
        for chemin in chemins.values():
            print(chemin)


if __name__ == "__main__":
    main()
