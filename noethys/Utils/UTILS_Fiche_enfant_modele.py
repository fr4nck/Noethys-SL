# -*- coding: utf-8 -*-
"""Plan de restitution de la fiche enfant papier PMSL (juin 2026).

Ne cree pas de deuxieme dossier medical ni de questionnaire medical.
Le rendu reprend le document source ; chaque valeur vient des ecrans Noethys
existants, ou est laissee non renseignee sans invention.
Contrat de presentation pur, sans acces SQL ni ecriture.
"""
from types import MappingProxyType

TITRE = "ACCUEIL DE LOISIRS PÊLE-MÊLE — FICHE ENFANT"
SITES = ("LA GUERCHE (CP-CM2)", "MOUTIERS (PS-GS)", "BAIS")
SECTIONS = (
    ("identite", "IDENTITÉ", "identite"),
    ("responsables", "RESPONSABLES LÉGAUX", "liens"),
    ("accompagnants", "ACCOMPAGNANTS", "liens"),
    ("vaccinations", "VACCINATIONS", "medical"),
    ("medecin", "MÉDECIN TRAITANT", "medical"),
    ("sante", "MALADIES ET ALLERGIES", "medical"),
    ("autorisations", "AUTORISATIONS DIVERSES", None),
    ("declaration", "DÉCLARATION DU RESPONSABLE LÉGAL", None),
)
AUTORISATIONS_PAPIER = (
    ("photos_site_imprimes", "Photos (site internet : pelemele.org)"),
    ("maquillage", "Maquillage"),
    ("piscine_baignade", "Baignade"),
    ("activites_physiques", "Activités physiques"),
)
# Hors du formulaire papier historique : distinctions operationnelles
# optionnelles dans la fiche interne, jamais consentement implicite.
AUTORISATIONS_COMPLEMENTAIRES = (
    ("photos_prise", "Prise de vues"),
    ("photos_usage_interne", "Utilisation interne des photos"),
    ("photos_reseaux_sociaux", "Publication sur les réseaux sociaux"),
)
CHAMPS_EXISTANTS = MappingProxyType({
    "identite": "identite",
    "responsables": "liens",
    "accompagnants": "liens",
    "vaccinations": "medical",
    "medecin": "medical",
    "sante": "medical",
    "aeeh": "identite",
    "repas": "questionnaire",
})
SOURCES = MappingProxyType({
    "identite": ("individus",),
    "responsables": ("rattachements", "individus"),
    "accompagnants": ("liens", "individus"),
    "vaccinations": ("vaccins", "vaccins_obligatoires"),
    "medecin": ("individus", "medecins"),
    "sante": ("problemes_sante",),
    "aeeh": ("individus", "aeeh_periodes"),
    "repas": ("questionnaire_reponses", "questionnaire_choix"),
})


def PlanDeFiche():
    """Ordre original, rubriques existantes et cases d'autorisation papier."""
    return {
        "titre": TITRE,
        "sites": list(SITES),
        "sections": [{"code": code, "titre": titre, "onglet": onglet}
                     for code, titre, onglet in SECTIONS],
        "autorisations_papier": [
            {"code": code, "libelle": libelle, "etat": "non_renseigne"}
            for code, libelle in AUTORISATIONS_PAPIER
        ],
        "donnees_existantes": dict(CHAMPS_EXISTANTS),
        "portail_parents": False,
        "nouveau_dossier_medical": False,
    }


def ValiderConcordance(autorisations):
    """Ne pas assimiler 'non renseigné' a 'non' ou a 'oui'."""
    prevues = {code for code, _ in AUTORISATIONS_PAPIER}
    if not isinstance(autorisations, dict):
        raise ValueError("Les autorisations doivent etre un dictionnaire")
    if set(autorisations) != prevues:
        raise ValueError("Les quatre autorisations du formulaire sont requises")
    if any(valeur not in ("oui", "non", "non_renseigne", "expire", "a_verifier")
           for valeur in autorisations.values()):
        raise ValueError("Etat d'autorisation inconnu")
    return True
