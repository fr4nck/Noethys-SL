# STATS-RESTORE — lot initial de restauration (09/11/2026)

## État vérifié
- Audit statique sur les sources, aucune exécution de l'application Windows ou base de production.
- HEAD au prévol : main 07d672a2, wx bcc8a450, qt b6bc25ba.
- Commits : main a64cfa02 + 768fc03d + 7c102dc2 ; qt 0102723c + bb6cb702 ; wx c775c3a6 + b7cfa5e0.
- Fast-forward sans force, sans branche supplémentaire, aucun tag, migration, binaire ou release.

## Correctifs candidats, non qualifiés
1. Âges : classement entier 0–9, 10–19, etc., 0 distinct de l'inconnu, et tri compatible None. Test tests/test_stats_restore_ages.py.
2. VFS : nom d'image UUID distinct par objet pour prévenir la collision entre dialogues ; mise à jour du même objet conserve son propre nom. Test tests/test_stats_restore_vfs.py.
3. QF : partition exclusive des plages tarifaires imbriquées et réactivation de la branche « Inscrits ». Test tests/test_stats_restore_quotients.py.
Les trois changements de moteur ont été propagés à main, wx, qt sans écraser les adaptations wx.

## Limites restantes / STOP-GATE
- Les trois fichiers de tests existent dans GitHub, mais n'ont pas été exécutés sur les sources du dépôt dans cette intervention.
- Contrôles Python isolés réussis sur l'arithmétique des découpages QF et âges ; ils ne remplacent aucune recette SQL ni GUI.
- **QF historiques :** sélection du QF selon la période toujours non déterministe ; aucune règle métier inventée. Les 244 familles déduites de la capture restent conditionnelles.
- **VFS :** durée de vie et libération des ressources des anciens dialogues/aperçus pas encore assurées. Ne pas annoncer absence de fuite mémoire.
- **UI :** SQL individuel et rendus de graphiques peuvent toujours bloquer wx ; impression et réseau des distances restent synchrones ; issue #432 ouverte.
- Dernière CI étudiée #42599928647 sur ancien SHA : 2 FAIL / 2 248 ; aucune CI du candidat actuel exécutée.
- Suite : tests de régression ciblés puis CI Windows rapide, 11 pages, stress VFS natif, SQL synthétique, modèle QF historique, impression, HWND et non-régression Connecthys/factures.
- Aucun GO pour publication RC ; absence de test ne doit pas être assimilée à PASS.
