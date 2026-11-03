-- LOT D6 : PROPOSITION MySQL 5.7 NON EXECUTEE, NON QUALIFIEE.
-- InnoDB et transactions sont obligatoires. Les CHECK MySQL 5.7 sont inoperants.
-- Aucun schema historique de facturation familiale n'est modifie.
SELECT IDbordereau FROM partenaires_bordereaux LIMIT 0;
CREATE TABLE partenaires_factures_sequence (
 singleton INT PRIMARY KEY,
 exercice SMALLINT NOT NULL,
 dernier_numero INT NOT NULL,
 derniere_date DATE NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO partenaires_factures_sequence VALUES (1,0,0,NULL);

CREATE TABLE partenaires_factures_officielles (
 IDfacture_partenaire INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDbordereau INT UNSIGNED NOT NULL,
 IDpartenaire INT UNSIGNED NOT NULL,
 numero VARCHAR(40) NOT NULL,
 exercice SMALLINT NOT NULL,
 ordre INT NOT NULL,
 date_emission DATE NOT NULL,
 date_echeance DATE NOT NULL,
 date_prestation DATE NOT NULL,
 periode_debut DATE NOT NULL,
 periode_fin DATE NOT NULL,
 total DECIMAL(12,2) NOT NULL,
 empreinte_bordereau CHAR(64) NOT NULL,
 donnees_json LONGTEXT NOT NULL,
 empreinte_document CHAR(64) NOT NULL,
 etat VARCHAR(20) NOT NULL,
 cree_le DATETIME NOT NULL,
 cree_par VARCHAR(100) NOT NULL,
 UNIQUE KEY uq_part_facture_numero (numero),
 UNIQUE KEY uq_part_facture_exercice (exercice,ordre),
 UNIQUE KEY uq_part_facture_lot (IDbordereau),
 KEY idx_part_facture_structure (IDpartenaire,date_emission),
 CONSTRAINT fk_part_facture_lot FOREIGN KEY (IDbordereau) REFERENCES partenaires_bordereaux(IDbordereau),
 CONSTRAINT fk_part_facture_structure FOREIGN KEY (IDpartenaire) REFERENCES partenaires_structures(IDpartenaire)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE partenaires_factures_evenements (
 IDevenement INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDfacture_partenaire INT UNSIGNED NOT NULL,
 action VARCHAR(30) NOT NULL,
 date_action DATETIME NOT NULL,
 acteur VARCHAR(100) NOT NULL,
 KEY idx_part_fact_evenements (IDfacture_partenaire,IDevenement),
 CONSTRAINT fk_part_fact_evt FOREIGN KEY (IDfacture_partenaire) REFERENCES partenaires_factures_officielles(IDfacture_partenaire)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
