# -*- coding: utf-8 -*-
"""Crée un fichier Noethys local FICTIF « Recette » (DATA, PHOTOS, DOCUMENTS)
selon la séquence de MainFrame.Nouveau (Noethys.py), puis un profil
Portable de test qui l'ouvre au démarrage. Aucune donnée réelle.

Usage (depuis la racine du dépôt, avec l'environnement Python du projet) :
    python tests/recette_creer_fichier_fictif.py . <copie extraite>/Noethys/Portable
où <copie extraite>/Noethys provient de l'archive portable à recetter.
Code d'identification de l'administrateur fictif : recette2026.
Voir docs/recette/RECETTE_CANDIDAT_2026-10-08.md."""
import datetime
import json
import os
import random
import sys

DEPOT, PORTABLE = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(DEPOT, "tests"))
sys.path.insert(0, os.path.join(DEPOT, "noethys"))
import _garde_reseau  # noqa: E402  aucune connexion réseau
os.chdir(os.path.join(DEPOT, "noethys"))
import wx  # noqa: E402
APP = wx.App(False)
import GestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
import Noethys  # noqa: E402

DATA = os.path.join(PORTABLE, "Data")
os.makedirs(DATA, exist_ok=True)
for rep in ("Temp", "Updates", "Sync", "Lang", "Extensions"):
    os.makedirs(os.path.join(PORTABLE, rep), exist_ok=True)
NOM = "Recette"
chemins = {s: os.path.join(DATA, "%s_%s.dat" % (NOM, s)) for s in ("DATA", "PHOTOS", "DOCUMENTS")}
for chemin in chemins.values():
    assert not os.path.exists(chemin), "fichier fictif déjà présent : %s" % chemin

# 1. Tables, valeurs par défaut, photos, documents, index (MainFrame.Nouveau)
db = GestionDB.DB(nomFichier=chemins["DATA"], suffixe=None, modeCreation=True)
for table in Tables.DB_DATA:
    db.CreationTable(nomTable=table, dicoDB=Tables.DB_DATA)
db.Importation_valeurs_defaut()
db.Close()
db = GestionDB.DB(nomFichier=chemins["PHOTOS"], suffixe=None, modeCreation=True); db.CreationTables(Tables.DB_PHOTOS); db.Close()
db = GestionDB.DB(nomFichier=chemins["DOCUMENTS"], suffixe=None, modeCreation=True); db.CreationTables(Tables.DB_DOCUMENTS); db.Close()
for s in ("DATA", "PHOTOS"):
    db = GestionDB.DB(nomFichier=chemins[s], suffixe=None); db.CreationTousIndex(); db.Close()

# 2. Informations du fichier et administrateur sans mot de passe
db = GestionDB.DB(nomFichier=chemins["DATA"], suffixe=None)
IDfichier = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
for nom, valeur in (("date_creation", str(datetime.date.today())), ("version", Noethys.VERSION_APPLICATION), ("IDfichier", IDfichier)):
    db.ReqInsert("parametres", [("categorie", "fichier"), ("nom", nom), ("parametre", valeur)])
import hashlib  # noqa: E402
db.ReqInsert("utilisateurs", [("sexe", "M"), ("nom", "RECETTE"), ("prenom", "Admin"), ("mdp", ""),
                              ("mdpcrypt", hashlib.sha256("recette2026".encode("utf-8")).hexdigest()),
                              ("profil", "administrateur"), ("actif", 1), ("image", "Automatique")])

# 3. Données fictives
req = [
    "INSERT INTO organisateur (IDorganisateur, nom, rue, cp, ville) VALUES (1, 'Association de recette', '1 rue des Tests', '35000', 'Rennes');",
    # Famille de personnes physiques : parent + deux enfants (dont « Arthur » fictif)
    "INSERT INTO familles (IDfamille, IDcompte_payeur) VALUES (1, 1);",
    "INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (1, 1);",
    "INSERT INTO individus (IDindividu, IDcivilite, nom, prenom, date_naiss, rue_resid, cp_resid, ville_resid) VALUES (1, 3, 'FICTIF', 'Lea', '1985-03-03', '12 rue du Moulin', '35000', 'Rennes');",
    "INSERT INTO individus (IDindividu, IDcivilite, nom, prenom, date_naiss, adresse_auto) VALUES (2, 4, 'FICTIF', 'Arthur', '2015-05-05', 1);",
    "INSERT INTO individus (IDindividu, IDcivilite, nom, prenom, date_naiss, adresse_auto) VALUES (3, 5, 'FICTIF', 'Lina', '2017-07-07', 1);",
    "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, IDcategorie, titulaire) VALUES (1, 1, 1, 1, 1);",
    "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, IDcategorie, titulaire) VALUES (2, 2, 1, 2, 0);",
    "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, IDcategorie, titulaire) VALUES (3, 3, 1, 2, 0);",
    "INSERT INTO payeurs (IDpayeur, IDcompte_payeur, nom) VALUES (1, 1, 'FICTIF Lea');",
    # Association : structure (personne morale) titulaire, deux sections
    "INSERT INTO familles (IDfamille, IDcompte_payeur) VALUES (2, 2);",
    "INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (2, 2);",
    "INSERT INTO individus (IDindividu, IDcivilite, nom, prenom) VALUES (10, 7, 'CLUB FICTIF', '');",
    "INSERT INTO individus (IDindividu, IDcivilite, nom, prenom) VALUES (11, 7, 'CLUB FICTIF - SECTION A', '');",
    "INSERT INTO individus (IDindividu, IDcivilite, nom, prenom) VALUES (12, 7, 'CLUB FICTIF - SECTION B', '');",
    "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, IDcategorie, titulaire) VALUES (10, 10, 2, 1, 1);",
    "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, IDcategorie, titulaire) VALUES (11, 11, 2, 2, 0);",
    "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, IDcategorie, titulaire) VALUES (12, 12, 2, 2, 0);",
    "INSERT INTO payeurs (IDpayeur, IDcompte_payeur, nom) VALUES (2, 2, 'CLUB FICTIF');",
    # Activité, unité, ouvertures, inscriptions
    "INSERT INTO activites (IDactivite, nom, abrege, date_debut, date_fin) VALUES (1, 'Accueil de recette', 'ACC', '2026-01-01', '2027-12-31');",
    "INSERT INTO groupes (IDgroupe, IDactivite, nom, ordre) VALUES (1, 1, 'Groupe unique', 1);",
    "INSERT INTO unites (IDunite, IDactivite, nom, abrege, type, ordre) VALUES (1, 1, 'Journée', 'J', 'Unitaire', 1);",
    "INSERT INTO categories_tarifs (IDcategorie_tarif, IDactivite, nom) VALUES (1, 1, 'Tarif unique');",
    # Adhésion annuelle glissante (type individuel par défaut)
    "INSERT INTO types_cotisations (IDtype_cotisation, nom, type, carte, defaut) VALUES (1, 'Adhésion annuelle', 'individu', 0, 1);",
    "INSERT INTO unites_cotisations (IDunite_cotisation, IDtype_cotisation, nom, montant, defaut, duree, label_prestation) VALUES (1, 1, '2026-2027', 7.5, 1, 'j0-m0-a1', 'Adhésion annuelle - 2026-2027');",
    "INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES (1, 1);",
    # Prestation et règlement non ventilé (devis)
    "INSERT INTO prestations (IDprestation, IDcompte_payeur, date, categorie, label, montant, montant_initial, IDfamille, IDindividu, IDactivite) VALUES (1, 1, '2026-10-05', 'consommation', 'Séance de recette', 12.5, 12.5, 1, 2, 1);",
    "INSERT INTO reglements (IDreglement, IDcompte_payeur, date, IDmode, montant, IDpayeur) VALUES (1, 1, '2026-10-06', 1, 50.0, 1);",
]
for i, (individu, famille) in enumerate(((2, 1), (3, 1), (11, 2), (12, 2)), 1):
    req.append("INSERT INTO inscriptions (IDinscription, IDindividu, IDfamille, IDactivite, IDgroupe, IDcategorie_tarif, IDcompte_payeur, date_inscription, statut) VALUES (%d, %d, %d, 1, 1, 1, %d, '2026-09-01', 'ok');" % (i, individu, famille, famille))
for i, jour in enumerate(range(5, 31), 1):
    req.append("INSERT INTO ouvertures (IDouverture, IDactivite, IDunite, IDgroupe, date) VALUES (%d, 1, 1, 1, '2026-10-%02d');" % (i, jour))
for r in req:
    assert db.ExecuterReq(r), r
db.Commit()
db.Close()

# 4. Profil Portable de test : ouvre « Recette » au démarrage, sans annonce
config = {"nomFichier": NOM, "derniersFichiers": [NOM], "nbre_derniers_fichiers": 10}
json.dump(config, open(os.path.join(PORTABLE, "Config.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("fichier fictif créé :", sorted(os.listdir(DATA)), "| tentatives réseau :", len(_garde_reseau.TENTATIVES))
sys.stdout.flush()
os._exit(0)
