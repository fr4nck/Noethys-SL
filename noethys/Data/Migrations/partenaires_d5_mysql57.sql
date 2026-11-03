-- LOT D5: DDL PROPOSAL ONLY, NOT tested on MySQL 5.7.
-- Apply on a disposable restored copy after D1/D2/D34; DDL is not rollback-safe.
-- CHECK constraints are ignored in MySQL 5.7. No ALTER on historic tables.
SELECT IDintervention FROM partenaires_interventions LIMIT 0;
CREATE TABLE partenaires_bordereaux (
 IDbordereau INT UNSIGNED NOT NULL AUTO_INCREMENT,
 IDpartenaire INT UNSIGNED NOT NULL,
 IDconvention_partenaire INT UNSIGNED NOT NULL,
 reference VARCHAR(100) NOT NULL,
 date_debut DATE NOT NULL,
 date_fin DATE NOT NULL,
 etat VARCHAR(25) NOT NULL,
 empreinte CHAR(64) NULL,
 total DECIMAL(12,2) NULL,
 nombre_lignes INT NULL,
 valide_le DATETIME NULL,
 valide_par VARCHAR(100) NULL,
 cree_le DATETIME NOT NULL,
 PRIMARY KEY(IDbordereau),
 UNIQUE KEY uq_part_bordereau_reference(IDpartenaire,reference),
 KEY idx_part_bordereau_convention(IDconvention_partenaire,date_debut,date_fin),
 CONSTRAINT fk_d5_b_part FOREIGN KEY(IDpartenaire) REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
 CONSTRAINT fk_d5_b_conv FOREIGN KEY(IDconvention_partenaire) REFERENCES partenaires_conventions(IDconvention_partenaire) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_bordereaux_lignes (
 IDligne INT UNSIGNED NOT NULL AUTO_INCREMENT,
 IDbordereau INT UNSIGNED NOT NULL,
 IDintervention INT UNSIGNED NOT NULL,
 IDversion INT UNSIGNED NOT NULL,
 IDtarif_convention INT UNSIGNED NOT NULL,
 date_reelle DATE NOT NULL,
 minutes_reelles INT UNSIGNED NOT NULL,
 categorie VARCHAR(30) NOT NULL,
 libelle VARCHAR(120) NOT NULL,
 unite VARCHAR(20) NOT NULL,
 prix_unitaire DECIMAL(12,2) NOT NULL,
 montant DECIMAL(12,2) NOT NULL,
 empreinte_source CHAR(64) NOT NULL,
 PRIMARY KEY(IDligne),
 UNIQUE KEY uq_part_ligne_intervention(IDintervention),
 KEY idx_part_ligne_bordereau(IDbordereau,IDligne),
 CONSTRAINT fk_d5_l_bord FOREIGN KEY(IDbordereau) REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT,
 CONSTRAINT fk_d5_l_inter FOREIGN KEY(IDintervention) REFERENCES partenaires_interventions(IDintervention) ON DELETE RESTRICT,
 CONSTRAINT fk_d5_l_version FOREIGN KEY(IDversion) REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT,
 CONSTRAINT fk_d5_l_tarif FOREIGN KEY(IDtarif_convention) REFERENCES partenaires_conventions_tarifs(IDtarif_convention) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_bordereaux_references (
 IDreference INT UNSIGNED NOT NULL AUTO_INCREMENT,
 IDbordereau INT UNSIGNED NOT NULL,
 IDpartenaire INT UNSIGNED NOT NULL,
 nature VARCHAR(30) NOT NULL,
 reference_externe VARCHAR(150) NOT NULL,
 montant_declare DECIMAL(12,2) NOT NULL,
 empreinte_document CHAR(64) NOT NULL,
 declare_le DATETIME NOT NULL,
 declare_par VARCHAR(100) NOT NULL,
 PRIMARY KEY(IDreference),
 UNIQUE KEY uq_part_ref_bordereau(IDbordereau),
 UNIQUE KEY uq_part_ref_unique(IDpartenaire,nature,reference_externe),
 CONSTRAINT fk_d5_r_bord FOREIGN KEY(IDbordereau) REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT,
 CONSTRAINT fk_d5_r_part FOREIGN KEY(IDpartenaire) REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE partenaires_bordereaux_evenements (
 IDevenement INT UNSIGNED NOT NULL AUTO_INCREMENT,
 IDbordereau INT UNSIGNED NOT NULL,
 action VARCHAR(30) NOT NULL,
 acteur VARCHAR(100) NOT NULL,
 date_action DATETIME NOT NULL,
 informations VARCHAR(200) NOT NULL DEFAULT '',
 PRIMARY KEY(IDevenement),
 KEY idx_part_bord_evt(IDbordereau,IDevenement),
 CONSTRAINT fk_d5_e_bord FOREIGN KEY(IDbordereau) REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
