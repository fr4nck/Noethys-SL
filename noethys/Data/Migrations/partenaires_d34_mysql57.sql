-- Lot D3-D4 : MySQL 5.7/InnoDB. SCRIPT PROPOSE, NON EXECUTE.
-- Manuellement sur copie jetable APRES D1 et D2 ; MySQL DDL auto-commit.
-- CHECK constraints de SQLite absentes / IGNOREES par MySQL 5.7 : validation Python requise.
-- Ne pas executer sur production, aucune migration implicite.

CREATE TABLE partenaires_programmations (
 IDprogrammation INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDversion INT UNSIGNED NOT NULL,
 reference VARCHAR(100) NOT NULL,
 libelle VARCHAR(255) NOT NULL,
 date_debut DATE NOT NULL,
 date_fin DATE NOT NULL,
 etat VARCHAR(12) NOT NULL,
 empreinte_calendrier CHAR(64) NULL,
 valide_le DATETIME NULL,
 valide_par VARCHAR(100) NULL,
 cree_le DATETIME NOT NULL,
 modifie_le DATETIME NOT NULL,
 UNIQUE KEY uq_part_programmations_reference (IDversion, reference),
 KEY idx_part_programmations_version (IDversion,etat),
 CONSTRAINT fk_part_programmations_version FOREIGN KEY (IDversion)
  REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_creneaux (
 IDcreneau INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDprogrammation INT UNSIGNED NOT NULL,
 recurrence VARCHAR(14) NOT NULL,
 jour_semaine TINYINT UNSIGNED NULL,
 date_debut DATE NOT NULL,
 date_fin DATE NOT NULL,
 heure_debut CHAR(5) NOT NULL,
 heure_fin CHAR(5) NOT NULL,
 groupe VARCHAR(120) NOT NULL,
 activite VARCHAR(160) NOT NULL,
 lieu VARCHAR(200) NULL,
 intervenant VARCHAR(160) NULL,
 categorie_tarif VARCHAR(20) NOT NULL,
 KEY idx_part_creneaux_programmation (IDprogrammation),
 CONSTRAINT fk_part_creneaux_programmation FOREIGN KEY (IDprogrammation)
  REFERENCES partenaires_programmations(IDprogrammation) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_exclusions (
 IDexclusion INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDprogrammation INT UNSIGNED NOT NULL,
 date_debut DATE NOT NULL,
 date_fin DATE NOT NULL,
 categorie VARCHAR(12) NOT NULL,
 motif VARCHAR(500) NOT NULL,
 KEY idx_part_exclusions_programmation (IDprogrammation,date_debut,date_fin),
 CONSTRAINT fk_part_exclusions_programmation FOREIGN KEY (IDprogrammation)
  REFERENCES partenaires_programmations(IDprogrammation) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_exceptions (
 IDexception INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDcreneau INT UNSIGNED NOT NULL,
 date_origine DATE NOT NULL,
 nature VARCHAR(12) NOT NULL,
 date_remplacement DATE NULL,
 heure_debut CHAR(5) NULL,
 heure_fin CHAR(5) NULL,
 lieu VARCHAR(200) NULL,
 motif VARCHAR(500) NOT NULL,
 UNIQUE KEY uq_part_exceptions_occurrence (IDcreneau,date_origine),
 KEY idx_part_exceptions_creneau (IDcreneau),
 CONSTRAINT fk_part_exceptions_creneau FOREIGN KEY (IDcreneau)
  REFERENCES partenaires_creneaux(IDcreneau) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_interventions (
 IDintervention INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDprogrammation INT UNSIGNED NOT NULL,
 IDversion INT UNSIGNED NOT NULL,
 IDcreneau INT UNSIGNED NOT NULL,
 date_origine DATE NOT NULL,
 date_prevue DATE NOT NULL,
 heure_debut_prevue CHAR(5) NOT NULL,
 heure_fin_prevue CHAR(5) NOT NULL,
 minutes_initiales INT UNSIGNED NOT NULL,
 minutes_prevues INT UNSIGNED NOT NULL,
 groupe VARCHAR(120) NOT NULL,
 activite VARCHAR(160) NOT NULL,
 lieu_prevu VARCHAR(200) NULL,
 intervenant_prevu VARCHAR(160) NULL,
 categorie_tarif VARCHAR(20) NOT NULL,
 date_reelle DATE NULL,
 heure_debut_reelle CHAR(5) NULL,
 heure_fin_reelle CHAR(5) NULL,
 minutes_reelles INT UNSIGNED NULL,
 lieu_reel VARCHAR(200) NULL,
 intervenant_reel VARCHAR(160) NULL,
 etat VARCHAR(12) NOT NULL,
 decision_facturation VARCHAR(20) NOT NULL,
 origine_annulation VARCHAR(20) NULL,
 justification_annulation TINYINT UNSIGNED NULL,
 motif VARCHAR(500) NULL,
 valide_par VARCHAR(100) NULL,
 valide_le DATETIME NULL,
 cree_le DATETIME NOT NULL,
 modifie_le DATETIME NOT NULL,
 UNIQUE KEY uq_part_interventions_occurrence (IDcreneau,date_origine),
 KEY idx_part_interventions_planning (IDprogrammation,date_prevue),
 KEY idx_part_interventions_version (IDversion,etat,decision_facturation),
 CONSTRAINT fk_part_interventions_programmation FOREIGN KEY (IDprogrammation)
  REFERENCES partenaires_programmations(IDprogrammation) ON DELETE RESTRICT,
 CONSTRAINT fk_part_interventions_version FOREIGN KEY (IDversion)
  REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT,
 CONSTRAINT fk_part_interventions_creneau FOREIGN KEY (IDcreneau)
  REFERENCES partenaires_creneaux(IDcreneau) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_interventions_historique (
 IDhistorique INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDintervention INT UNSIGNED NOT NULL,
 action VARCHAR(15) NOT NULL,
 ancien_etat VARCHAR(12) NULL,
 nouvel_etat VARCHAR(12) NULL,
 date_precedente DATE NULL,
 date_suivante DATE NULL,
 horaire_precedent VARCHAR(11) NULL,
 horaire_suivant VARCHAR(11) NULL,
 intervenant_precedent VARCHAR(160) NULL,
 intervenant_suivant VARCHAR(160) NULL,
 decision_precedente VARCHAR(20) NULL,
 decision_suivante VARCHAR(20) NULL,
 reference_ecrite VARCHAR(200) NULL,
 motif VARCHAR(500) NOT NULL,
 acteur VARCHAR(100) NOT NULL,
 date_action DATETIME NOT NULL,
 KEY idx_part_interventions_historique (IDintervention,IDhistorique),
 CONSTRAINT fk_part_interventions_historique_intervention FOREIGN KEY (IDintervention)
  REFERENCES partenaires_interventions(IDintervention) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_plan_evenements (
 IDevenement INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 nature VARCHAR(20) NOT NULL,
 IDobjet INT UNSIGNED NOT NULL,
 action VARCHAR(30) NOT NULL,
 acteur VARCHAR(100) NOT NULL,
 champs VARCHAR(255) NOT NULL DEFAULT '',
 date_action DATETIME NOT NULL,
 KEY idx_part_plan_evenements_objet (nature,IDobjet,IDevenement)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
