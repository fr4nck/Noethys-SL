#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-12 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils.UTILS_Traduction import _
import six
import GestionDB
from Utils import UTILS_Json
import base64


def Exporter(IDmodele=None, fichier="", depuisFichierDefaut=False):
    """ Exportation d'un modèle de document """
    # Ouverture Base
    if depuisFichierDefaut == False :
        DB = GestionDB.DB()
    else :
        DB = GestionDB.DB(nomFichier=Chemins.GetStaticPath("Databases/Defaut.dat"), suffixe=None)

    # Récupération des infos sur le modèle
    req = """SELECT nom, categorie, largeur, hauteur, IDfond, defaut
    FROM documents_modeles
    WHERE IDmodele=%d
    ;""" % IDmodele
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    nom, categorie, largeur, hauteur, IDfond, defaut = listeDonnees[0]

    # Récupération des champs de la table des objets
    listeColonnes = DB.GetListeChamps2("documents_objets")
    listeChamps = []
    for nomChamp, typeChamp in listeColonnes :
        listeChamps.append(nomChamp)

    # Récupération des données à exporter
    req = """SELECT %s
    FROM documents_objets
    WHERE IDmodele=%d
    ;""" % (", ".join(listeChamps), IDmodele)
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()

    # Fermeture Base
    DB.Close()

    # Mémorisation des objets
    listeObjets = []
    for donnees in listeDonnees :
        dictObjet = {}
        index = 0
        for donnee in donnees :
            nomChamp = listeColonnes[index][0]
            typeChamp = listeColonnes[index][1]

            # Pour les champs BLOB
            if "BLOB" in typeChamp.upper() and donnee != None :
                buffer = six.BytesIO(donnee)
                donnee = buffer.read()

            if nomChamp == "image" and donnee != None:
                donnee = base64.b64encode(donnee)

            # Mémorisation
            if nomChamp not in ("IDmodele", "IDobjet") :
                dictObjet[nomChamp] = donnee

            index += 1
        listeObjets.append(dictObjet)

    # Mémorisation dans un dict
    data = {
        "nom": nom,
        "categorie": categorie,
        "largeur": largeur,
        "hauteur": hauteur,
        "IDfond": IDfond,
        "defaut": defaut,
        "objets": listeObjets,
    }

    # Enregistrement dans un fichier Json
    if fichier != "" :
        if six.PY2:
            fichier = fichier.encode("utf8")
        UTILS_Json.Ecrire(nom_fichier=fichier, data=data)

    return data


def InfosFichier(fichier=""):
    """ Récupère les infos principales sur un fichier """
    if six.PY2:
        fichier = fichier.encode("utf8")
    data = UTILS_Json.Lire(fichier)
    return data


def Importer(fichier="", dictDonnees={}, IDfond=None, defaut=0):
    """ Importation d'un modèle de document depuis un fichier JSON ou un DICTIONNAIRE """
    DB = GestionDB.DB()

    if fichier != "" :
        if six.PY2:
            fichier = fichier.encode("utf8")
        data = UTILS_Json.Lire(fichier)
    else :
        data = dictDonnees

    # Saisie dans la table documents_modeles
    listeDonnees = [
            ("nom", data["nom"]),
            ("categorie", data["categorie"]),
            ("supprimable", 1),
            ("largeur", data["largeur"]),
            ("hauteur", data["hauteur"]),
            ("observations", ""),
            ("IDfond", IDfond),
            ("defaut", defaut),
            ]
    IDmodele = DB.ReqInsert("documents_modeles", listeDonnees)

    # Saisie dans la table documents_objets
    listeObjets = data["objets"]
    for dictObjet in listeObjets :
        dictObjet["IDmodele"] = IDmodele

        # Réinitialisé à chaque objet : sans cela, un dictObjet sans clé
        # "image" (fichier .ndc importé/édité en dehors d'Exporter(), qui
        # inclut aujourd'hui systématiquement cette clé mais ne le
        # garantit pas pour tout fichier .ndc possible) soit lève
        # UnboundLocalError au premier objet sans image, soit réutilise à
        # tort le blob de l'objet précédent pour un objet qui n'en a pas.
        blob = None
        listeDonnees = []
        for champ, donnee in dictObjet.items() :
            if champ == "image" :
                try :
                    donnee = base64.b64decode(donnee)
                except:
                    pass
                blob = donnee
                donnee = None
            listeDonnees.append((champ, donnee))

        IDobjet = DB.ReqInsert("documents_objets", listeDonnees)

        if blob != None :
            DB.MAJimage(table="documents_objets", key="IDobjet", IDkey=IDobjet, blobImage=blob, nomChampBlob="image")

    DB.Close()
    return IDmodele


def ImporterModeleExempleIdempotent(fichier=""):
    """ Importe un modèle .ndc "exemple" fourni avec le produit (voir
    noethys/Static/ModelesConventionExemples/, docs/recette_conventions/README.md)
    de façon idempotente : n'importe JAMAIS un doublon.

    Si un modèle portant EXACTEMENT le même nom et la même catégorie que
    celui du fichier existe déjà, ne fait RIEN et renvoie son IDmodele
    existant tel quel -- ne modifie jamais son contenu, même s'il diffère
    du fichier (ce pourrait être une version que l'utilisateur a
    volontairement modifiée après un premier import). Sinon, importe
    normalement via Importer() et renvoie le nouvel IDmodele.

    Utilisée UNIQUEMENT pour les modèles d'exemple fournis avec le
    produit -- jamais pour le bouton "Importer" générique de l'écran
    Modèles de documents, qui doit continuer à toujours créer un nouveau
    modèle quel que soit son nom (un utilisateur import du contenu
    externe explicitement choisi, pas un modèle fourni par Noethys). """
    if six.PY2:
        fichier = fichier.encode("utf8")
    data = UTILS_Json.Lire(fichier)

    DB = GestionDB.DB()
    nomEchappe = data["nom"].replace("'", "''")
    categorieEchappee = data["categorie"].replace("'", "''")
    req = """SELECT IDmodele FROM documents_modeles
    WHERE nom='%s' AND categorie='%s';""" % (nomEchappe, categorieEchappee)
    DB.ExecuterReq(req)
    listeExistants = DB.ResultatReq()
    DB.Close()

    if len(listeExistants) > 0 :
        return listeExistants[0][0]

    return Importer(dictDonnees=data)




# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def DupliquerModele(IDmodele=None, nom="", categorie=None) :
    """ Dupliquer un modèle de doc """
    DB = GestionDB.DB()

    # Duplication du modèle
    conditions = "IDmodele=%d" % IDmodele
    dictModifications = {"nom" : nom}
    if categorie != None :
        dictModifications["categorie"] = categorie
    newIDmodele = DB.Dupliquer("documents_modeles", "IDmodele", conditions, dictModifications)

    # Duplication des objets
    conditions = "IDmodele=%d" % IDmodele
    dictModifications = {"IDmodele" : newIDmodele}
    newIDobjet = DB.Dupliquer("documents_objets", "IDobjet", conditions, dictModifications)

    DB.Close()



# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def ImporterDepuisFichierDefaut(IDmodele=None, nom=None, IDfond=1, defaut=0):
    """ Importer un modèle de document depuis le fichier defaut.dat """
    try :
        dictDonnees = Exporter(IDmodele=IDmodele, depuisFichierDefaut=True)
        if nom != None : dictDonnees["nom"] = nom
        Importer(dictDonnees=dictDonnees, IDfond=IDfond, defaut=defaut)
    except Exception as err :
        print("Erreur dans l'importation d'un modele depuis le fichier defaut :", err)
        return False



if __name__ == "__main__":
    # Avec un fichier
    Exporter(IDmodele=5, fichier="C:/Users/Test/Desktop/TestExport.ndc")
    # Importer(fichier="Tests/TestExport.ndc")

    # Avec un dictionnaire depuis le fichier defaut.dat
    # ImporterDepuisFichierDefaut(IDmodele=13, nom=None, IDfond=1, defaut=0)

    # Dupliquer un modèle
    # DupliquerModele(IDmodele=5, nom=_(u"Attestation fiscale par défaut 2"), categorie="attestation_fiscale")

    pass
