# -*- coding: utf-8 -*-
"""Inspection en lecture seule d'un paquet RC9 déjà construit.

Usage : python scripts/inspecter_paquet_rc9.py <dossier_artefact> [<dossier_diagnostics>]

<dossier_artefact> contient Noethys-SL-0.1.0-rc.9-Setup.exe et
Noethys-SL-0.1.0-rc.9-Windows-portable.zip (artefact du build) ;
<dossier_diagnostics> contient les journaux de démarrage du même build.

Contrôles, séparés dans le rapport :
1. tailles et SHA-256 des deux fichiers, comparés aux empreintes consignées ;
2. PRÉSENCE dans le binaire : les modules des derniers correctifs figurent
   dans l'archive PYZ embarquée dans Noethys.exe (extrait du ZIP portable),
   avec des marqueurs propres à la version construite (noms de fonctions et
   textes présents dans le code compilé) ;
3. CHARGEMENT au démarrage : modules effectivement importés par le binaire
   d'après les journaux de diagnostic du build (les écrans ouverts à la
   demande ne sont pas chargés au démarrage : NON PROUVÉ ici).
Le fonctionnement des parcours n'est PAS établi par ce script (recette).

Aucun programme du paquet n'est exécuté ; rien n'est modifié.
Nécessite PyInstaller 6.22.3 (version du build) pour lire l'archive.
"""
import hashlib
import os
import re
import sys
import tempfile
import zipfile

ATTENDUS = {
    "Noethys-SL-0.1.0-rc.9-Setup.exe": "4868cb4c8bc6be9da02e71941c5b36915a6a1cef56634996a954587a4883fddf",
    "Noethys-SL-0.1.0-rc.9-Windows-portable.zip": "93fd107ccfbd45371ab242eef9dd75b1ccfe68bda2ee0bbd3ceb9044d9a0d9c8",
}

# Correctif -> {module : marqueurs attendus dans le code compilé}
MARQUEURS = {
    "Types de cotisation": {
        "Dlg.DLG_Saisie_type_cotisation": ["_EcrireMode", "SignalerIssueIncertaine", "VerrouillerParametrageType",
                                           "_ModifieAilleurs"],
        "Utils.UTILS_Adhesions": ["VerrouillerParametrageType", "TABLES_PARAMETRAGE"],
    },
    "Suivi et reprise des confirmations Connecthys": {
        "Utils.UTILS_Emails_acceptes": ["EffacerConfirmationsCompletes", "Reserver", "SuiviIllisible", "LireSuivi"],
        "Utils.UTILS_Envoi_email": ["_EnvoiEmailFamilleSuivi", "interruption_envoi", "empreinte"],
        "Dlg.DLG_Saisie_portail_demande": ["EnregistrerDemande", "EffacerConfirmationsCompletes", "EmpreinteLigne"],
    },
    "Mailjet": {
        "Dlg.DLG_Mailer": ["listeIncertains", "envoi_complet", "_EnvoyerLotMailjetHorsUI"],
    },
    "Quotient familial": {
        "Dlg.DLG_Saisie_quotient": ["01/01/2999", "ValiderEtEnregistrer"],
        "Dlg.DLG_Saisie_piece": ["SaisirQuotient", u"La validité illimitée est acceptée"],
    },
    "Impression des dépôts": {
        "Ol.OL_Reglements_depots": ["GetPerimetreImpression", "_VueImpressionDepot", u"Vue filtrée", "Quittancier"],
    },
}


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def textes_du_code(code, acc=None):
    """Noms et constantes texte d'un objet code, récursivement."""
    acc = set() if acc is None else acc
    acc.update(code.co_names)
    acc.update(code.co_varnames)
    acc.add(code.co_name)
    for const in code.co_consts:
        if isinstance(const, str):
            acc.add(const)
        elif hasattr(const, "co_code"):
            textes_du_code(const, acc)
    return acc


def contient(textes, marqueur):
    return marqueur in textes or any(marqueur in t for t in textes if isinstance(t, str) and len(t) < 5000)


def main(dossier, diagnostics=None):
    resultats = []
    echec = False

    print("== 1. Tailles et SHA-256")
    for nom, attendu in ATTENDUS.items():
        chemin = os.path.join(dossier, nom)
        if not os.path.isfile(chemin):
            print("FAIL  %s : absent" % nom)
            echec = True
            continue
        reel = sha256(chemin)
        statut = "PASS" if reel == attendu else "FAIL"
        echec |= statut != "PASS"
        print("%s  %s : %d octets, SHA-256 %s (attendu %s)" % (statut, nom, os.path.getsize(chemin), reel, attendu))

    print("== 2. Présence dans le binaire (archive PYZ de Noethys.exe du ZIP portable)")
    from PyInstaller.archive.readers import CArchiveReader
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(os.path.join(dossier, "Noethys-SL-0.1.0-rc.9-Windows-portable.zip")) as z:
            z.extract("Noethys.exe", tmp)
        carchive = CArchiveReader(os.path.join(tmp, "Noethys.exe"))
        noms_pyz = [n for n in carchive.toc if n.endswith(".pyz")]
        if not noms_pyz:
            print("FAIL  aucune archive PYZ dans Noethys.exe")
            return 1
        pyz = carchive.open_embedded_archive(noms_pyz[0])
        print("Archive %s : %d modules" % (noms_pyz[0], len(pyz.toc)))
        for correctif, modules in MARQUEURS.items():
            for module, marqueurs in modules.items():
                if module not in pyz.toc:
                    print("FAIL  [%s] %s : module absent" % (correctif, module))
                    echec = True
                    continue
                textes = textes_du_code(pyz.extract(module))
                manquants = [m for m in marqueurs if not contient(textes, m)]
                statut = "PASS" if not manquants else "FAIL"
                echec |= bool(manquants)
                print("%s  [%s] %s : présent%s" % (statut, correctif, module,
                                                   "" if not manquants else ", marqueurs absents %s" % manquants))
                resultats.append(module)

    print("== 3. Chargement au démarrage (journaux de diagnostic du build)")
    if not diagnostics:
        print("NON EXÉCUTÉ : dossier de diagnostics non fourni")
    else:
        importes = set()
        for racine, _d, fichiers in os.walk(diagnostics):
            for fichier in fichiers:
                with open(os.path.join(racine, fichier), encoding="utf-8", errors="replace") as f:
                    for ligne in f:
                        m = re.search(r" IMPORT (\S+)", ligne)
                        if m:
                            importes.add(m.group(1))
        for module in resultats:
            if module in importes:
                print("CHARGÉ      %s (importé par le binaire au démarrage)" % module)
            else:
                print("NON PROUVÉ  %s (non importé au démarrage : chargé à l'ouverture de l'écran, voir recette)" % module)
    print("== Fonctionnement des parcours : non établi par cette inspection (recette).")
    return 1 if echec else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
