# -*- coding: utf-8 -*-
"""Installation explicite et idempotente du questionnaire Type de repas.

Aucune creation automatique a l'ouverture de Noethys. L'interface doit
obtenir un accord humain avant d'appeler PreparerQuestionnaire.
Ne touche ni aux reponses individuelles ni aux modeles de commande existants.
"""
import unicodedata

TITRE = u"Type de repas"
CATEGORIE = u"Alimentation"
REGIMES = (
    ("standard", u"Standard"),
    ("sans_porc", u"Sans porc"),
    ("vegetarien", u"Végétarien"),
    ("sans_repas_pmsl", u"Repas apporté par la famille (sans repas PMSL)"),
)
TITRES_COMPATIBLES = (u"Type de repas", u"Régime repas")
ALIASES = {
    "standard": (u"Standard", u"Repas standard"),
    "sans_porc": (u"Sans porc", u"Repas sans porc"),
    "vegetarien": (u"Végétarien", u"Repas végétarien"),
    "sans_repas_pmsl": (
        u"Repas apporté par la famille (sans repas PMSL)",
        u"Repas apporté par la famille",
        u"Panier apporté par la famille",
        u"Sans repas fourni par PMSL (repas apporté par la famille)",
    ),
}


class QuestionnaireRepasIncompatible(ValueError):
    """Conflit necessitant une decision de l'operateur, aucune ecriture."""


def _nom(valeur):
    texte = unicodedata.normalize("NFKD", str(valeur or "").strip())
    return "".join(c for c in texte if not unicodedata.combining(c)).casefold()


def _requete(base, sql, parametres=()):
    if base.isNetwork:
        sql = sql.replace("?", "%s")
    base.cursor.execute(sql, tuple(parametres))


def _lignes(base, sql, parametres=()):
    _requete(base, sql, parametres)
    return list(base.cursor.fetchall())


def _insere(base, table, colonnes, valeurs):
    # Tables et noms de colonnes sont tous des constantes internes.
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (
        table, ", ".join(colonnes), ", ".join("?" for _ in colonnes))
    _requete(base, sql, valeurs)
    if base.isNetwork:
        _requete(base, "SELECT LAST_INSERT_ID()")
        return int(base.cursor.fetchone()[0])
    return int(base.cursor.lastrowid)


def _inspection(base):
    """Observation seulement ; ne lit pas les reponses des familles."""
    questions = _lignes(base, """
        SELECT q.IDquestion, q.label, q.controle, q.visible, q.defaut,
               c.IDcategorie, c.visible
        FROM questionnaire_questions q
        JOIN questionnaire_categories c ON c.IDcategorie=q.IDcategorie
        WHERE c.type='individu'
        ORDER BY q.IDquestion
    """)
    candidats = [q for q in questions if _nom(q[1]) in
                 set(_nom(t) for t in TITRES_COMPATIBLES)]
    if not candidats:
        return {"etat": "absent", "question": None, "choix": {},
                "detail": u"Aucun questionnaire repas reconnu."}
    if len(candidats) != 1:
        return {"etat": "conflit", "question": None, "choix": {},
                "detail": u"Plusieurs questions repas existent : choisir manuellement."}
    IDquestion, titre, controle, visible_question, defaut, _categorie, visible_categorie = candidats[0]
    if (controle != "liste_deroulante" or not visible_question or
            not visible_categorie or defaut not in (None, "")):
        return {"etat": "conflit", "question": IDquestion, "choix": {},
                "detail": u"La question repas existante doit être visible, à choix unique et sans valeur par défaut."}

    lignes = _lignes(base, """
        SELECT IDchoix, label, visible FROM questionnaire_choix
        WHERE IDquestion=? ORDER BY ordre, IDchoix
    """, (IDquestion,))
    if len(lignes) != 4 or any(not visible for _id, _nom_choix, visible in lignes):
        return {"etat": "conflit", "question": IDquestion, "choix": {},
                "detail": u"La question repas existante n'a pas exactement quatre réponses visibles."}
    correspondances = {}
    for IDchoix, libelle, _visible in lignes:
        roles = [role for role, labels in ALIASES.items()
                 if _nom(libelle) in set(_nom(label) for label in labels)]
        if len(roles) != 1 or roles[0] in correspondances:
            return {"etat": "conflit", "question": IDquestion, "choix": {},
                    "detail": u"Les réponses du questionnaire repas sont ambiguës ou inconnues."}
        correspondances[roles[0]] = int(IDchoix)
    if set(correspondances) != set(role for role, _label in REGIMES):
        return {"etat": "conflit", "question": IDquestion, "choix": {},
                "detail": u"Les quatre régimes alimentaires ne sont pas représentés."}
    return {"etat": "pret", "question": int(IDquestion),
            "choix": correspondances,
            "detail": u"Questionnaire repas déjà conforme : aucun changement nécessaire."}


def ExaminerQuestionnaire(base=None):
    """Diagnostic sûr, en lecture seule, sans mutation de la base."""
    proprietaire = base is None
    if proprietaire:
        import GestionDB
        base = GestionDB.DB()
    try:
        return _inspection(base)
    finally:
        if proprietaire:
            base.Close()


def PreparerQuestionnaire(base=None):
    """Création explicite, une seule fois, dans une transaction.

    Un deuxième appel réutilise les IDs. Un homonyme incomplet n'est jamais
    complété ou modifié silencieusement. Les tables doivent déjà exister.
    """
    proprietaire = base is None
    if proprietaire:
        import GestionDB
        base = GestionDB.DB()
    verrou_mysql = False
    transaction = False
    try:
        if base.isNetwork:
            _requete(base, """
                SELECT GET_LOCK(CONCAT('noethys_repas_q_', LEFT(MD5(DATABASE()), 16)), 0)
            """)
            verrou_mysql = base.cursor.fetchone()[0] == 1
            if not verrou_mysql:
                raise QuestionnaireRepasIncompatible(
                    u"Un autre poste prépare le questionnaire repas. Réessayez ensuite.")
            _requete(base, "START TRANSACTION")
        else:
            _requete(base, "BEGIN IMMEDIATE")
        transaction = True
        diagnostic = _inspection(base)
        if diagnostic["etat"] == "conflit":
            raise QuestionnaireRepasIncompatible(diagnostic["detail"])
        if diagnostic["etat"] == "pret":
            base.connexion.commit()
            transaction = False
            return diagnostic

        categories = _lignes(base, """
            SELECT IDcategorie, label FROM questionnaire_categories
            WHERE type='individu'
        """)
        compatibles = [int(i) for i, nom in categories if _nom(nom) == _nom(CATEGORIE)]
        if len(compatibles) > 1:
            raise QuestionnaireRepasIncompatible(
                u"Plusieurs catégories Alimentation existent : arbitrage nécessaire.")
        if compatibles:
            IDcategorie = compatibles[0]
        else:
            ordre = _lignes(base, "SELECT MAX(ordre) FROM questionnaire_categories")[0][0]
            IDcategorie = _insere(base, "questionnaire_categories",
                ("ordre", "visible", "type", "couleur", "label"),
                (int(ordre or 0) + 1, 1, "individu", "(220, 238, 252)", CATEGORIE))
        ordre = _lignes(base,
            "SELECT MAX(ordre) FROM questionnaire_questions WHERE IDcategorie=?",
            (IDcategorie,))[0][0]
        IDquestion = _insere(base, "questionnaire_questions",
            ("IDcategorie", "ordre", "visible", "label", "controle", "defaut", "options"),
            (IDcategorie, int(ordre or 0) + 1, 1, TITRE, "liste_deroulante", None, ""))
        for ordre, (_role, label) in enumerate(REGIMES):
            _insere(base, "questionnaire_choix",
                ("IDquestion", "ordre", "visible", "label"),
                (IDquestion, ordre, 1, label))
        resultat = _inspection(base)
        if resultat["etat"] != "pret" or resultat["question"] != IDquestion:
            raise QuestionnaireRepasIncompatible(
                u"Contrôle après création non conforme : modifications annulées.")
        base.connexion.commit()
        transaction = False
        return resultat
    except Exception:
        if transaction:
            base.connexion.rollback()
        raise
    finally:
        if verrou_mysql:
            try:
                _requete(base, """
                    SELECT RELEASE_LOCK(CONCAT('noethys_repas_q_', LEFT(MD5(DATABASE()), 16)))
                """)
                base.cursor.fetchone()
            except Exception:
                pass
        if proprietaire:
            base.Close()
