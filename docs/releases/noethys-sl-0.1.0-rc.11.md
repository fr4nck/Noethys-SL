# Noethys SL 0.1.0 RC11 — candidat Windows wx

**État : candidat de recette, pas de publication automatique.** Version interne Noethys 1.3.4.4 inchangée ; aucune migration SQL, aucune intervention sur les bases PMSL.

## Périmètre consolidé

- RC10.55 demeure la dernière publication officielle tant que RC11 n'a pas franchi les barrières de l'issue [#447](https://github.com/fr4nck/Noethys-SL/issues/447).
- La branche `wx` conserve les contrôles de facturation/cotisations (#426), les corrections de sauvegarde (#437), de l'interface/focus (#432) et de reprise Connecthys (#435).
- Les commandes Océane doivent bloquer un sous-total M/P « sans porc » ou « végétarien » qui diverge de la répartition validée (#430). Les variantes « sans viande », « végétarien » et « sans allergène » demeurent indépendantes et doivent être confirmées, sans inférence médicale.
- Le questionnaire individuel « Type de repas » comporte quatre réponses explicites, dont le repas apporté par la famille, qui conserve la présence au temps méridien sans créer de repas fournisseur.
- La séparation fournisseur / présence n'implique **pas** une exonération financière automatique : la création de prestation panier à 0 € et l'audit tarifaire 2C-3 (#433) demeurent inactifs. Aucun changement de facture existante ni de prestation d'accueil.

## Contrôles techniques du candidat

Le workflow `.github/workflows/noethys-sl-rc11-windows.yml` est un constructeur **sans job de publication ni droit d'écriture**. Il doit contrôler :

1. identité externe RC11, version interne historique et changelog ;
2. régressions Windows de facturation, adhésions, menus, régimes, paniers, interface et Connecthys ;
3. génération du vrai exécutable PyInstaller et vérification des modules embarqués ;
4. MySQL 5.7.44 local jetable : facturation/cotisations, rendu PDF isolé, sauvegarde/restauration ;
5. gros BLOB fictif >24 Mio : export DATA + DOCUMENTS, CRC de l'archive et restauration avec SHA-256 identique ;
6. démarrage isolé de l'exécutable, installation du Setup, contrôle PDF enfant puis deux démarrages du ZIP portable ;
7. empreintes SHA-256 des deux livrables et provenance du SHA Git de construction.

**Le résultat des workflows antérieurs ne se reporte pas automatiquement sur un nouveau SHA**. Un échec/timeout/skip critique interdit de considérer le candidat comme qualifié.

## Barrières de publication restant à satisfaire

- [ ] Tous les tests du workflow du SHA exact : PASS sans SKIP critique.
- [ ] Recette opérationnelle wx sur base fictive : sélection de cotisations et factures sans ajout indu, 4 choix repas, deux sites, âges, adultes, PDF et bordereau Océane.
- [ ] Sauvegarde/restauration `DATA + DOCUMENTS`, incluant BLOB, avec parcours Windows et destination réseau de recette ; aucune opération directe sur la base PMSL.
- [ ] Scénario réel Windows de maximisation/focus Connecthys/Mailer (#432), sans envoi réel.
- [ ] Reprise Connecthys avec décision humaine pour les situations ambiguës, sans duplication ni deuxième email.
- [ ] Validation du confinement du sous-lot panier financier 2C-3 ; audit des tarifs ALSH uniquement sur copie isolée si activation envisagée.
- [ ] Contrôle du `BUILD-INFO.txt`, des empreintes du Setup et du ZIP, validation explicite de la direction avant tag/release.

**Exclusions :** PR #444, PR #445, issue #446, AFAS V1, migrations SQL, données PMSL de production, SMTP fournisseur. PHOTOS est facultatif pour le contrôle #437.

## Résultats disponibles avant construction

- Le workflow MySQL régimes quatre choix [#43243320452](https://github.com/fr4nck/Noethys-SL/actions/runs/43243320452) a exécuté 14 tests avec 0 erreur et 0 SKIP sur un SHA précédent.
- La validation Windows du correctif Océane [#43222052557](https://github.com/fr4nck/Noethys-SL/actions/runs/43222052557) a été PASS sur un SHA précédent.
- Ces preuves doivent être complétées par le nouveau workflow RC11 et la recette réelle.

**Aucun tag ni release RC11 ne sont générés par le workflow candidat.**
