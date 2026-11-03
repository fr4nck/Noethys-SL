-- Lot ALSH-C1 - Migration MySQL 5.7 PROPOSEE, NON TESTEE sur un serveur.
-- Exiger backup, copie de recette et validation avant application.
CREATE TABLE alsh_communes_domiciles (
 IDdomicile INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDindividu INTEGER NOT NULL,
 date_debut DATE NOT NULL,
 date_fin DATE DEFAULT NULL,
 rue VARCHAR(255) NOT NULL,
 complement VARCHAR(150) NOT NULL DEFAULT '',
 code_postal VARCHAR(12) NOT NULL,
 ville VARCHAR(120) NOT NULL,
 code_insee VARCHAR(5) NOT NULL,
 pays VARCHAR(80) NOT NULL DEFAULT 'France',
 justificatif VARCHAR(255) NOT NULL,
 UNIQUE KEY alsh_communes_domiciles_debut (IDindividu, date_debut),
 KEY alsh_communes_domiciles_dates (IDindividu, date_debut, date_fin),
 CONSTRAINT alsh_c1_individu_fk FOREIGN KEY (IDindividu) REFERENCES individus(IDindividu)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE alsh_communes_domiciles_audit (
 IDaudit INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
 IDdomicile INTEGER NOT NULL,
 acteur VARCHAR(120) NOT NULL,
 action VARCHAR(30) NOT NULL,
 donnees_json TEXT NOT NULL,
 date_action DATETIME NOT NULL,
 CONSTRAINT alsh_c1_audit_fk FOREIGN KEY (IDdomicile) REFERENCES alsh_communes_domiciles(IDdomicile)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE alsh_communes_exports (
 IDexport INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
 date_export DATETIME NOT NULL,
 acteur VARCHAR(120) NOT NULL,
 code_insee VARCHAR(5) NOT NULL,
 periode_debut DATE NOT NULL,
 periode_fin DATE NOT NULL,
 nombre_lignes INTEGER NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
