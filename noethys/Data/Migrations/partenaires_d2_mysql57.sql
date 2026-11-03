-- Lot D2 : MySQL 5.7, DDL NON TESTE sur serveur, pas d'execution automatique.
-- A executer manuellement sur copie jetable avec sauvegarde et retour arriere verifies.
-- MySQL 5.7 execute les CREATE TABLE avec commit implicite : pas de rollback DDL.
CREATE TABLE partenaires_conventions (
  IDconvention_partenaire INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  IDpartenaire INT UNSIGNED NOT NULL,
  reference VARCHAR(100) NOT NULL,
  libelle VARCHAR(255) NOT NULL,
  type_convention VARCHAR(20) NOT NULL,
  date_debut DATE NOT NULL,
  date_fin DATE NOT NULL,
  etat VARCHAR(12) NOT NULL,
  cree_le DATETIME NOT NULL,
  modifie_le DATETIME NOT NULL,
  UNIQUE KEY uq_partenaires_conventions_reference (IDpartenaire, reference),
  KEY idx_partenaires_conventions_structure (IDpartenaire, etat),
  CONSTRAINT fk_partenaires_conventions_structure FOREIGN KEY (IDpartenaire)
    REFERENCES partenaires_structures (IDpartenaire) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_conventions_versions (
  IDversion INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  IDconvention_partenaire INT UNSIGNED NOT NULL,
  numero_version INT UNSIGNED NOT NULL,
  nature VARCHAR(12) NOT NULL,
  statut VARCHAR(12) NOT NULL,
  brouillon_marker TINYINT UNSIGNED NULL,
  date_effet DATE NOT NULL,
  clauses MEDIUMTEXT NOT NULL,
  support_modele VARCHAR(10) NOT NULL,
  reference_modele VARCHAR(200) NOT NULL,
  mode_facturation VARCHAR(12) NOT NULL,
  date_signature DATE NULL,
  signataire VARCHAR(200) NULL,
  empreinte_document_signe CHAR(64) NULL,
  partenaire_snapshot MEDIUMTEXT NULL,
  empreinte_contenu CHAR(64) NULL,
  cree_le DATETIME NOT NULL,
  modifie_le DATETIME NOT NULL,
  UNIQUE KEY uq_partenaires_conventions_numero (IDconvention_partenaire, numero_version),
  UNIQUE KEY uq_partenaires_conventions_brouillon (IDconvention_partenaire, brouillon_marker),
  KEY idx_partenaires_conventions_versions_etat (IDconvention_partenaire, statut, date_effet),
  CONSTRAINT fk_partenaires_conventions_versions_convention FOREIGN KEY (IDconvention_partenaire)
    REFERENCES partenaires_conventions (IDconvention_partenaire) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_conventions_tarifs (
  IDtarif_convention INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  IDversion INT UNSIGNED NOT NULL,
  categorie VARCHAR(20) NOT NULL,
  libelle VARCHAR(120) NOT NULL,
  unite VARCHAR(12) NOT NULL,
  montant DECIMAL(12,2) NOT NULL,
  date_debut DATE NOT NULL,
  date_fin DATE NOT NULL,
  KEY idx_partenaires_conventions_tarifs_version (IDversion, categorie),
  CONSTRAINT fk_partenaires_conventions_tarifs_version FOREIGN KEY (IDversion)
    REFERENCES partenaires_conventions_versions (IDversion) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_conventions_evenements (
  IDevenement INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nature VARCHAR(20) NOT NULL,
  IDobjet INT UNSIGNED NOT NULL,
  action VARCHAR(30) NOT NULL,
  acteur VARCHAR(100) NOT NULL,
  champs VARCHAR(255) NOT NULL DEFAULT '',
  date_action DATETIME NOT NULL,
  KEY idx_partenaires_conventions_evenements_objet (nature, IDobjet, IDevenement)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
