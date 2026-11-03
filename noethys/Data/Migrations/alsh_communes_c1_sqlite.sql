-- Lot ALSH-C1 - Migration PROPOSEE uniquement, ne pas executer sur MAD/production.
-- Les informations de domicile sont saisies par les personnes habilitees.
-- Pas de factures, prestations ou familles modifiees.
CREATE TABLE alsh_communes_domiciles (
 IDdomicile INTEGER PRIMARY KEY AUTOINCREMENT,
 IDindividu INTEGER NOT NULL REFERENCES individus(IDindividu),
 date_debut TEXT NOT NULL,
 date_fin TEXT,
 rue TEXT NOT NULL,
 complement TEXT NOT NULL DEFAULT '',
 code_postal TEXT NOT NULL,
 ville TEXT NOT NULL,
 code_insee TEXT NOT NULL,
 pays TEXT NOT NULL DEFAULT 'France',
 justificatif TEXT NOT NULL,
 UNIQUE(IDindividu, date_debut)
);
CREATE INDEX alsh_communes_domiciles_dates ON alsh_communes_domiciles(IDindividu,date_debut,date_fin);
CREATE TABLE alsh_communes_domiciles_audit (
 IDaudit INTEGER PRIMARY KEY AUTOINCREMENT,
 IDdomicile INTEGER NOT NULL REFERENCES alsh_communes_domiciles(IDdomicile),
 acteur TEXT NOT NULL,
 action TEXT NOT NULL,
 donnees_json TEXT NOT NULL,
 date_action TEXT NOT NULL
);
CREATE TABLE alsh_communes_exports (
 IDexport INTEGER PRIMARY KEY AUTOINCREMENT,
 date_export TEXT NOT NULL,
 acteur TEXT NOT NULL,
 code_insee TEXT NOT NULL,
 periode_debut TEXT NOT NULL,
 periode_fin TEXT NOT NULL,
 nombre_lignes INTEGER NOT NULL
);
