# -*- coding: utf-8 -*-
"""AFAS V2 -- périodes d'accueil et statuts des consommations.

Le mode d'accueil d'une date est déduit du calendrier des vacances déjà
saisi dans Noethys (table `vacances`), selon la définition des conventions
(art. 1.1) : périscolaire = semaines d'école hors samedis sans école et
dimanches ; extrascolaire = vacances scolaires et samedis sans école ;
dimanche = séjours uniquement. Une date dont l'année scolaire n'a pas de
calendrier saisi n'est jamais classée par défaut : elle est inconnue.

Le cœur (Calendrier, ModeDate, statuts) n'importe ni wx ni GestionDB ;
seul ChargerCalendrier lit la base.
"""
import datetime

from Utils import UTILS_AFAS2_Conventions as Conventions

PERISCOLAIRE = Conventions.PERISCOLAIRE
EXTRASCOLAIRE = Conventions.EXTRASCOLAIRE
DIMANCHE = "dimanche"
INCONNU = "inconnu"

STATUTS = (
    ("reservation", "Pointage en attente"),
    ("present", "Présent"),
    ("absentj", "Absence justifiée"),
    ("absenti", "Absence injustifiée"),
)
CODES_STATUTS = tuple(code for code, libelle in STATUTS)
LIBELLES_STATUTS = dict(STATUTS)
# États techniques Noethys hors consommation réelle (liste d'attente, place refusée).
STATUTS_TECHNIQUES_EXCLUS = ("attente", "refus")

ETATS_REALISE_DEFAUT = ("present",)
ETATS_FACTURE_DEFAUT = ("present", "absentj", "absenti")


class CalendrierIncomplet(ValueError):
    """Aucune période de vacances saisie pour l'année scolaire concernée."""


def ValiderEtats(etats, nom):
    """Liste de codes de statuts admis, non vide et sans doublon."""
    if not isinstance(etats, (list, tuple)) or not etats:
        raise ValueError("%s : au moins un statut doit être retenu" % nom)
    if len(set(etats)) != len(etats):
        raise ValueError("%s : statut en double" % nom)
    inconnus = [e for e in etats if e not in CODES_STATUTS]
    if inconnus:
        raise ValueError("%s : statut inconnu ou non admissible %r" % (nom, inconnus))
    return list(etats)


def ClasserStatut(etat):
    """'admis' (un des quatre statuts), 'technique' (attente/refus) ou 'inconnu'."""
    if etat in CODES_STATUTS:
        return "admis"
    if etat in STATUTS_TECHNIQUES_EXCLUS:
        return "technique"
    return "inconnu"


def _date(valeur):
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    return datetime.date.fromisoformat(str(valeur)[:10])


def AnneeScolaire(date):
    """Année de rentrée de l'année scolaire contenant `date` (été rattaché à l'année qui s'achève)."""
    return date.year if date.month >= 9 else date.year - 1


class Calendrier(object):
    """Périodes de vacances scolaires saisies dans Noethys."""

    def __init__(self, periodes):
        self.periodes = []
        for periode in periodes:
            nom, debut, fin = periode
            debut, fin = _date(debut), _date(fin)
            if fin < debut:
                raise ValueError("Période de vacances incohérente : %s (%s > %s)" % (nom, debut, fin))
            self.periodes.append((debut, fin, nom))
        self.periodes.sort()

    def EstVacances(self, date):
        return any(debut <= date <= fin for debut, fin, nom in self.periodes)

    def _intersecte(self, debut, fin):
        return any(d <= fin and f >= debut for d, f, nom in self.periodes)

    def AnneeScolaireCouverte(self, date):
        """Le calendrier de l'année scolaire de `date` est saisi : au moins une
        période de vacances pendant l'année scolaire (octobre à juin) et la
        période d'été qui la clôt (juillet-août)."""
        annee = AnneeScolaire(date)
        return (self._intersecte(datetime.date(annee, 10, 1), datetime.date(annee + 1, 6, 30))
                and self._intersecte(datetime.date(annee + 1, 7, 1), datetime.date(annee + 1, 8, 31)))

    def Vacances(self, date):
        for debut, fin, nom in self.periodes:
            if debut <= date <= fin:
                return nom
        return None


def ModeDate(date, calendrier, samedis_avec_ecole=False):
    """Mode d'accueil d'une date : PERISCOLAIRE, EXTRASCOLAIRE, DIMANCHE ou INCONNU.

    DIMANCHE n'est admissible qu'en extrascolaire pour un séjour qualifié ;
    INCONNU signale un calendrier de vacances absent pour l'année scolaire."""
    date = _date(date)
    if not calendrier.AnneeScolaireCouverte(date):
        return INCONNU
    if date.weekday() == 6:
        return DIMANCHE
    if calendrier.EstVacances(date):
        return EXTRASCOLAIRE
    if date.weekday() == 5 and not samedis_avec_ecole:
        return EXTRASCOLAIRE
    return PERISCOLAIRE


def DetailPeriodes(date_debut, date_fin, calendrier, samedis_avec_ecole=False):
    """Liste chronologique de segments (debut, fin, mode, vacances) pour contrôle utilisateur."""
    segments = []
    jour = _date(date_debut)
    fin = _date(date_fin)
    while jour <= fin:
        cle = (ModeDate(jour, calendrier, samedis_avec_ecole), calendrier.Vacances(jour))
        if segments and segments[-1][2:] == cle and segments[-1][1] + datetime.timedelta(days=1) == jour:
            segments[-1] = (segments[-1][0], jour) + cle
        else:
            segments.append((jour, jour) + cle)
        jour += datetime.timedelta(days=1)
    return segments


def ChargerCalendrier(date_debut, date_fin):
    """Calendrier des vacances lu dans Noethys, élargi d'un an de part et
    d'autre pour couvrir les années scolaires à cheval."""
    import GestionDB
    debut = _date(date_debut) - datetime.timedelta(days=366)
    fin = _date(date_fin) + datetime.timedelta(days=366)
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("SELECT nom, date_debut, date_fin FROM vacances WHERE date_fin>='%s' AND date_debut<='%s';"
                       % (debut, fin))
        lignes = DB.ResultatReq()
    finally:
        DB.Close()
    return Calendrier([(nom, d, f) for nom, d, f in lignes])
