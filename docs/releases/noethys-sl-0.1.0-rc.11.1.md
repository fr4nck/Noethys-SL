# Noethys SL 0.1.0 RC11.1 — candidat Windows wx

**Statut : candidat à construire et qualifier. Aucune publication automatique.** Branche `wx` uniquement pour l'installateur Windows. Version de compatibilité Noethys **1.3.4.4 inchangée**, aucune migration SQL.

## Correctifs depuis RC11

- **Facturation (#426)** : émission d'un lot de factures et rattachement des prestations dans une transaction unique ; vérification des prestations déjà facturées et de leur payeur, numéro attribué sous verrou MySQL/SQLite, rollback sur erreur, arrêt en cas de résultat de commit incertain. **Ne pas mélanger des postes anciens et nouveaux lors des émissions** : le verrou MySQL est coopératif et ne protège pas les versions antérieures qui ne l'utilisent pas.
- **Restauration (#437)** : plus de shell ni d'attente indéfinie du client mysql ; invocation en arguments structurés, SQL lu directement en stdin binaire, délai total borné, arrêt/attente du processus, diagnostic expurgé, prise en charge d'un gros document MySQL par `--max-allowed-packet=1G` côté client. Les contrôles d'intégrité, marqueur terminal et postconditions sont conservés. **Un import SQL DDL interrompu peut avoir laissé la base de destination partiellement modifiée.**
- **AFAS V2** : la documentation distingue clairement le module RC11 de sa recette sur données PMSL qui n'est toujours pas achevée. Aucun chiffre CAF n'est validé par le seul fait de produire une RC11.1.

## Régressions et preuves avant création du candidat

| Contrôle | Dernier résultat sur sources correctives |
|---|---|
| Windows `main` | [#43851962294](https://github.com/fr4nck/Noethys-SL/actions/runs/43851962294) : 1 333 tests, 0 FAIL, 16 SKIP |
| Windows `wx` | [#43851971407](https://github.com/fr4nck/Noethys-SL/actions/runs/43851971407) : 2 387 tests, 0 FAIL, 56 SKIP |
| Restauration MySQL 5.7.44 `main` | [#43851962244](https://github.com/fr4nck/Noethys-SL/actions/runs/43851962244) : PASS DATA + DOCUMENTS + BLOB >24 Mio |
| Restauration MySQL 5.7.44 `wx` | [#43851971612](https://github.com/fr4nck/Noethys-SL/actions/runs/43851971612) : PASS DATA + DOCUMENTS + BLOB >24 Mio |
| Facturation MySQL 5.7.44 `wx` | [#43844307488](https://github.com/fr4nck/Noethys-SL/actions/runs/43844307488) : 7 PASS |

**Ces preuves sont sur des SHA précédents** : le workflow de construction RC11.1 doit requalifier les composants embarqués sur **son propre SHA** avant de conserver le moindre artefact.

## Barrières avant publication / déploiement

1. Build Windows exact SHA : code et tests, exe, Setup, ZIP portable, deux démarrages isolés, contrôles PDF et Connecthys, empreintes SHA-256, provenance, ressources et client MySQL embarqués.
2. Recette opérateur sur environnement de test, sans connexion à la base de production : sélection de facturation, doubles postes, quatre choix repas, Océane, focus/boîtes de dialogue et relance de sauvegarde.
3. **Sauvegarde complète PMSL réellement restaurée sur cible isolée encore à prouver** (#437) ; PHOTOS facultatif.
4. **Connecthys** : éviter toute duplication des réservations, factures ou messages dans le parcours de reprise (#435).
5. **Panier familial** : aucune exonération automatique 2C-3 qualifiée (#433), donc pas de promesse de « 0 € automatique ».
6. **AFAS** : résultats sur la base réelle à rapprocher et à valider avec les règles Caf, indépendamment de la disponibilité de ce candidat.

Les PR statistiques #444/#445 restent hors périmètre. Aucun tag, migration, transmission Caf, SMTP fournisseur ni modification des données PMSL n'est autorisé par le seul succès de la CI.

**RC11 déjà publiée et ses empreintes restent inchangées.**