-- LOT D5: SQLite TEST ONLY. Apply manually on an isolated copy after D1, D2, D34.
-- No changes to familles, comptes_payeurs, prestations, factures or compta_tiers.
-- PRAGMA foreign_keys=ON is required on every connection. Replay must fail.
SELECT IDintervention FROM partenaires_interventions LIMIT 0;
CREATE TABLE partenaires_bordereaux (
 IDbordereau INTEGER PRIMARY KEY AUTOINCREMENT,
 IDpartenaire INTEGER NOT NULL REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
 IDconvention_partenaire INTEGER NOT NULL REFERENCES partenaires_conventions(IDconvention_partenaire) ON DELETE RESTRICT,
 reference TEXT NOT NULL COLLATE NOCASE CHECK(length(trim(reference))>0),
 date_debut TEXT NOT NULL,
 date_fin TEXT NOT NULL CHECK(date_fin>=date_debut),
 etat TEXT NOT NULL CHECK(etat IN ('brouillon','valide','reference_externe')),
 empreinte TEXT, total TEXT, nombre_lignes INTEGER,
 valide_le TEXT, valide_par TEXT,
 cree_le TEXT NOT NULL,
 UNIQUE(IDpartenaire,reference),
 CHECK ((etat='brouillon' AND empreinte IS NULL AND total IS NULL AND nombre_lignes IS NULL AND valide_le IS NULL AND valide_par IS NULL)
     OR (etat IN ('valide','reference_externe') AND empreinte IS NOT NULL AND total IS NOT NULL AND nombre_lignes>0 AND valide_le IS NOT NULL AND valide_par IS NOT NULL))
);
CREATE INDEX idx_part_bordereaux_convention ON partenaires_bordereaux(IDconvention_partenaire,date_debut,date_fin);

CREATE TABLE partenaires_bordereaux_lignes (
 IDligne INTEGER PRIMARY KEY AUTOINCREMENT,
 IDbordereau INTEGER NOT NULL REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT,
 IDintervention INTEGER NOT NULL UNIQUE REFERENCES partenaires_interventions(IDintervention) ON DELETE RESTRICT,
 IDversion INTEGER NOT NULL REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT,
 IDtarif_convention INTEGER NOT NULL REFERENCES partenaires_conventions_tarifs(IDtarif_convention) ON DELETE RESTRICT,
 date_reelle TEXT NOT NULL,
 minutes_reelles INTEGER NOT NULL CHECK(minutes_reelles>0),
 categorie TEXT NOT NULL,
 libelle TEXT NOT NULL,
 unite TEXT NOT NULL CHECK(unite IN ('heure','seance')),
 prix_unitaire TEXT NOT NULL,
 montant TEXT NOT NULL,
 empreinte_source TEXT NOT NULL
);
CREATE INDEX idx_part_bordereaux_lignes_lot ON partenaires_bordereaux_lignes(IDbordereau,IDligne);

CREATE TABLE partenaires_bordereaux_references (
 IDreference INTEGER PRIMARY KEY AUTOINCREMENT,
 IDbordereau INTEGER NOT NULL UNIQUE REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT,
 IDpartenaire INTEGER NOT NULL REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
 nature TEXT NOT NULL CHECK(nature='facture_externe'),
 reference_externe TEXT NOT NULL COLLATE NOCASE CHECK(length(trim(reference_externe))>0),
 montant_declare TEXT NOT NULL,
 empreinte_document TEXT NOT NULL,
 declare_le TEXT NOT NULL,
 declare_par TEXT NOT NULL,
 UNIQUE(IDpartenaire,nature,reference_externe)
);

CREATE TABLE partenaires_bordereaux_evenements (
 IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
 IDbordereau INTEGER NOT NULL REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT,
 action TEXT NOT NULL CHECK(action IN ('creation','validation','declaration_document')),
 acteur TEXT NOT NULL,
 date_action TEXT NOT NULL,
 informations TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_part_bordereaux_evenements_lot ON partenaires_bordereaux_evenements(IDbordereau,IDevenement);
