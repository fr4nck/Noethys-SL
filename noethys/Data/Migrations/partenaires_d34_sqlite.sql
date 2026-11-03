-- Lot D3-D4. EXECUTION MANUELLE SUR UNE BASE SQLITE FICTIVE UNIQUEMENT.
-- Prerequis : migrations D1 et D2 deja appliquees ; PRAGMA foreign_keys=ON
-- obligatoire sur CHAQUE connexion. Pas de migration implicite ni de DROP.
SELECT IDversion FROM partenaires_conventions_versions LIMIT 0;

CREATE TABLE partenaires_programmations (
 IDprogrammation INTEGER PRIMARY KEY AUTOINCREMENT,
 IDversion INTEGER NOT NULL REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT,
 reference TEXT NOT NULL CHECK(length(trim(reference))>0),
 libelle TEXT NOT NULL CHECK(length(trim(libelle))>0),
 date_debut TEXT NOT NULL,
 date_fin TEXT NOT NULL CHECK(date_fin>=date_debut),
 etat TEXT NOT NULL CHECK(etat IN ('brouillon','validee')),
 empreinte_calendrier TEXT,
 valide_le TEXT,
 valide_par TEXT,
 cree_le TEXT NOT NULL,
 modifie_le TEXT NOT NULL,
 UNIQUE(IDversion,reference),
 CHECK((etat='brouillon' AND valide_le IS NULL AND valide_par IS NULL AND empreinte_calendrier IS NULL)
    OR (etat='validee' AND valide_le IS NOT NULL AND valide_par IS NOT NULL AND empreinte_calendrier IS NOT NULL))
);
CREATE INDEX idx_part_programmations_version ON partenaires_programmations(IDversion,etat);

CREATE TABLE partenaires_creneaux (
 IDcreneau INTEGER PRIMARY KEY AUTOINCREMENT,
 IDprogrammation INTEGER NOT NULL REFERENCES partenaires_programmations(IDprogrammation) ON DELETE RESTRICT,
 recurrence TEXT NOT NULL CHECK(recurrence IN ('hebdomadaire','ponctuel')),
 jour_semaine INTEGER CHECK(jour_semaine BETWEEN 0 AND 6 OR jour_semaine IS NULL),
 date_debut TEXT NOT NULL,
 date_fin TEXT NOT NULL CHECK(date_fin>=date_debut),
 heure_debut TEXT NOT NULL,
 heure_fin TEXT NOT NULL,
 groupe TEXT NOT NULL CHECK(length(trim(groupe))>0),
 activite TEXT NOT NULL CHECK(length(trim(activite))>0),
 lieu TEXT,
 intervenant TEXT,
 categorie_tarif TEXT NOT NULL CHECK(categorie_tarif IN ('adultes','enfants','scolaires','autre')),
 CHECK((recurrence='hebdomadaire' AND jour_semaine IS NOT NULL)
       OR (recurrence='ponctuel' AND jour_semaine IS NULL AND date_debut=date_fin))
);
CREATE INDEX idx_part_creneaux_programmation ON partenaires_creneaux(IDprogrammation);

CREATE TABLE partenaires_exclusions (
 IDexclusion INTEGER PRIMARY KEY AUTOINCREMENT,
 IDprogrammation INTEGER NOT NULL REFERENCES partenaires_programmations(IDprogrammation) ON DELETE RESTRICT,
 date_debut TEXT NOT NULL,
 date_fin TEXT NOT NULL CHECK(date_fin>=date_debut),
 categorie TEXT NOT NULL CHECK(categorie IN ('vacances','ferie','fermeture','autre')),
 motif TEXT NOT NULL CHECK(length(trim(motif))>0)
);
CREATE INDEX idx_part_exclusions_programmation ON partenaires_exclusions(IDprogrammation,date_debut,date_fin);

CREATE TABLE partenaires_exceptions (
 IDexception INTEGER PRIMARY KEY AUTOINCREMENT,
 IDcreneau INTEGER NOT NULL REFERENCES partenaires_creneaux(IDcreneau) ON DELETE RESTRICT,
 date_origine TEXT NOT NULL,
 nature TEXT NOT NULL CHECK(nature IN ('supprimer','deplacer')),
 date_remplacement TEXT,
 heure_debut TEXT,
 heure_fin TEXT,
 lieu TEXT,
 motif TEXT NOT NULL CHECK(length(trim(motif))>0),
 UNIQUE(IDcreneau,date_origine),
 CHECK((nature='supprimer' AND date_remplacement IS NULL AND heure_debut IS NULL AND heure_fin IS NULL)
    OR (nature='deplacer' AND date_remplacement IS NOT NULL AND heure_debut IS NOT NULL AND heure_fin IS NOT NULL))
);
CREATE INDEX idx_part_exceptions_creneau ON partenaires_exceptions(IDcreneau);

CREATE TABLE partenaires_interventions (
 IDintervention INTEGER PRIMARY KEY AUTOINCREMENT,
 IDprogrammation INTEGER NOT NULL REFERENCES partenaires_programmations(IDprogrammation) ON DELETE RESTRICT,
 IDversion INTEGER NOT NULL REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT,
 IDcreneau INTEGER NOT NULL REFERENCES partenaires_creneaux(IDcreneau) ON DELETE RESTRICT,
 date_origine TEXT NOT NULL,
 date_prevue TEXT NOT NULL,
 heure_debut_prevue TEXT NOT NULL,
 heure_fin_prevue TEXT NOT NULL,
 minutes_initiales INTEGER NOT NULL CHECK(minutes_initiales>0),
 minutes_prevues INTEGER NOT NULL CHECK(minutes_prevues>0),
 groupe TEXT NOT NULL,
 activite TEXT NOT NULL,
 lieu_prevu TEXT,
 intervenant_prevu TEXT,
 categorie_tarif TEXT NOT NULL,
 date_reelle TEXT,
 heure_debut_reelle TEXT,
 heure_fin_reelle TEXT,
 minutes_reelles INTEGER,
 lieu_reel TEXT,
 intervenant_reel TEXT,
 etat TEXT NOT NULL CHECK(etat IN ('prevue','reportee','realisee','annulee')),
 decision_facturation TEXT NOT NULL CHECK(decision_facturation IN ('a_arbitrer','eligible','non_facturable')),
 origine_annulation TEXT,
 justification_annulation INTEGER,
 motif TEXT,
 valide_par TEXT,
 valide_le TEXT,
 cree_le TEXT NOT NULL,
 modifie_le TEXT NOT NULL,
 UNIQUE(IDcreneau,date_origine),
 CHECK((etat<>'realisee' AND minutes_reelles IS NULL AND date_reelle IS NULL)
    OR (etat='realisee' AND minutes_reelles>0 AND date_reelle IS NOT NULL)),
 CHECK(decision_facturation<>'eligible' OR etat='realisee')
);
CREATE INDEX idx_part_interventions_planning ON partenaires_interventions(IDprogrammation,date_prevue);
CREATE INDEX idx_part_interventions_version ON partenaires_interventions(IDversion,etat,decision_facturation);

CREATE TABLE partenaires_interventions_historique (
 IDhistorique INTEGER PRIMARY KEY AUTOINCREMENT,
 IDintervention INTEGER NOT NULL REFERENCES partenaires_interventions(IDintervention) ON DELETE RESTRICT,
 action TEXT NOT NULL CHECK(action IN ('report','realisation','annulation','remplacement','decision')),
 ancien_etat TEXT,
 nouvel_etat TEXT,
 date_precedente TEXT,
 date_suivante TEXT,
 horaire_precedent TEXT,
 horaire_suivant TEXT,
 intervenant_precedent TEXT,
 intervenant_suivant TEXT,
 decision_precedente TEXT,
 decision_suivante TEXT,
 reference_ecrite TEXT,
 motif TEXT NOT NULL,
 acteur TEXT NOT NULL,
 date_action TEXT NOT NULL
);
CREATE INDEX idx_part_interventions_historique ON partenaires_interventions_historique(IDintervention,IDhistorique);

CREATE TABLE partenaires_plan_evenements (
 IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
 nature TEXT NOT NULL CHECK(nature IN ('programmation','creneau','exclusion','exception')),
 IDobjet INTEGER NOT NULL,
 action TEXT NOT NULL,
 acteur TEXT NOT NULL,
 champs TEXT NOT NULL DEFAULT '',
 date_action TEXT NOT NULL
);
CREATE INDEX idx_part_plan_evenements_objet ON partenaires_plan_evenements(nature,IDobjet,IDevenement);
