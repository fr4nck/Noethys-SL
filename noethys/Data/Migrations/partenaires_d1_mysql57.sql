-- Lot D1 - MySQL 5.7/InnoDB, EXECUTION MANUELLE SUR COPIE JETABLE.
-- MySQL DDL est auto-commit : sauvegarde et restauration avant toute utilisation.
-- Pas de IF NOT EXISTS : une reprise partielle doit etre examinee, pas ignoree.
CREATE TABLE partenaires_structures (
    IDpartenaire INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    categorie VARCHAR(20) NOT NULL,
    raison_sociale VARCHAR(255) NOT NULL,
    nom_usage VARCHAR(255) NULL,
    siret VARCHAR(14) NULL,
    adresse_ligne1 VARCHAR(255) NULL,
    code_postal VARCHAR(12) NULL,
    commune VARCHAR(120) NULL,
    pays VARCHAR(80) NULL,
    email_general VARCHAR(254) NULL,
    telephone_general VARCHAR(40) NULL,
    observations TEXT NULL,
    statut VARCHAR(12) NOT NULL,
    cree_le DATETIME NOT NULL,
    modifie_le DATETIME NOT NULL,
    KEY idx_partenaires_structures_nom (raison_sociale(120)),
    KEY idx_partenaires_structures_categorie (categorie, statut)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_contacts (
    IDcontact_partenaire INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    IDpartenaire INT UNSIGNED NOT NULL,
    nom VARCHAR(120) NOT NULL,
    prenom VARCHAR(120) NULL,
    fonction VARCHAR(160) NULL,
    email VARCHAR(254) NULL,
    telephone VARCHAR(40) NULL,
    principal TINYINT UNSIGNED NULL,
    statut VARCHAR(12) NOT NULL,
    cree_le DATETIME NOT NULL,
    modifie_le DATETIME NOT NULL,
    UNIQUE KEY uq_partenaires_contacts_principal (IDpartenaire, principal),
    KEY idx_partenaires_contacts_parent (IDpartenaire, statut),
    CONSTRAINT fk_partenaires_contacts_structure FOREIGN KEY (IDpartenaire)
        REFERENCES partenaires_structures (IDpartenaire) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_liens_noethys (
    IDlien INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    IDpartenaire INT UNSIGNED NOT NULL,
    type_reference VARCHAR(20) NOT NULL,
    IDreference INT UNSIGNED NOT NULL,
    actif TINYINT UNSIGNED NULL,
    date_debut DATETIME NOT NULL,
    date_fin DATETIME NULL,
    UNIQUE KEY uq_partenaires_liens_reference_active (type_reference, IDreference, actif),
    UNIQUE KEY uq_partenaires_liens_partenaire_actif (IDpartenaire, type_reference, actif),
    KEY idx_partenaires_liens_parent (IDpartenaire, actif),
    CONSTRAINT fk_partenaires_liens_structure FOREIGN KEY (IDpartenaire)
        REFERENCES partenaires_structures (IDpartenaire) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_evenements (
    IDevenement INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nature VARCHAR(20) NOT NULL,
    IDobjet INT UNSIGNED NOT NULL,
    action VARCHAR(30) NOT NULL,
    acteur VARCHAR(100) NOT NULL,
    champs TEXT NOT NULL,
    date_action DATETIME NOT NULL,
    KEY idx_partenaires_evenements_objet (nature, IDobjet, IDevenement)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
