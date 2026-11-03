# Lot D6 — Facturation partenaires, association loi 1901, sans TVA

**3 novembre 2026. Statut : prototype de registre de factures partenaires, qualifie sur SQLite fictif uniquement. Aucune activation en production, aucune facture transmise.**

## 1. Decision de perimetre

L'association PMSL a indique qu'elle n'a pas de TVA a calculer, deduire, reverser ou gerer. Le moteur D6 retient un **montant unique en euros a regler**, sans taux, montant, ventilation HT/TVA/TTC ou ecritures de TVA. Il enregistre le statut `Association loi 1901` dans l'instantane emetteur. Le seul texte fiscal affichable provient de `mention_fiscale` renseignee explicitement par l'association ; **aucun article de loi n'est selectionne automatiquement**. En particulier, l'article 293 B du CGI ne doit pas etre attribue par defaut a toutes les associations.

La forme loi 1901 ne suffit pas, a elle seule, pour demontrer le non-assujettissement. A valider avec l'association/comptable avant la mise en service. Selon la DGFiP (fiche associations, FAQ publiee en 2026), les associations effectivement non assujetties ne sont pas soumises aux obligations d'emission/reception de la reforme de facturation electronique ; les associations assujetties suivent un autre regime. Le logiciel ne conclut pas de cette seule declaration a une qualification juridique certaine.

Sources officielles : https://www.impots.gouv.fr/foire-aux-questions-japprofondis-la-facturation-electronique ; https://entreprendre.service-public.gouv.fr/vosdroits/F31808 ; https://www.impots.gouv.fr/professionnel/questions/je-nemets-pas-de-facture-ou-je-facture-sans-tva-suis-je-concerne-par-la

## 2. Circuit D5 -> D6

1. **Source** : un bordereau D5 `valide`, lui-meme base sur des interventions D3-D4 realisees et retenues comme facturables a partir des conventions D2 signees. Un bordereau deja declare comme facture externe ne peut pas etre converti en facture D6.
2. **Complements** : raison sociale, adresse postale, code postal et commune du client sont lus dans D1 ; en l'absence de ces mentions, la facture est refusee. Profil emetteur explicite : raison sociale, adresse, SIRET, mention fiscale validee, conditions de paiement et conditions de retard. Aucune donnee de l'association n'est inventee dans les sources ni dans la base.
3. **Preparation** en lecture seule : montant exact D5, dates, references de conventions, details des interventions, empreintes de source et instantanes de l'emetteur et du destinataire. Calcul de l'empreinte SHA-256 de l'apercu pour proteger la validation d'un changement tardif du client ou du bordereau.
4. **Enregistrement atomique** : nouvelle lecture et controle de l'apercu dans une transaction, verrou du compteur de numerotation, numero `PMSL-AAAA-000001`, insertion d'un seul document fige par bordereau et evenement. Les numeros annuels sont croissants, sans trou du a un echec dans cette transaction. Les changements de date retroactifs apres l'enregistrement de factures sont refuses. Deux validations concurrentes sur la meme base SQLite aboutissent a **une seule facture et un seul numero**.
5. **Lecture et export modele** : empreinte du document stocke et index compares ; source D5 verifiee sur demande. `modele_noedoc()` renvoie des donnees structurees pour une integration future dans Word/Noedoc ; ne genere pas de fichier ou de facture electronique, n'envoie aucun courriel et ne declenche aucun encaissement.
6. **Anti-double D5** : une reference de facture externe D5 est refusee si le bordereau est deja numerote dans D6. Anciennes bases D5 sans table D6 conservees compatibles.

Le registre emploie l'etat `enregistree` (numero alloue et contenu fige), **pas** `transmise`, ni `payee`. La presentation d'un contenu numerote ne constitue pas une preuve d'envoi ou de reception.

## 3. Nouvelles tables et fichiers

- `noethys/Utils/UTILS_Partenaires_D6.py` : prepare, enregistre, lit et exporte les donnees d'une facture partenaire. Connexion DB-API fournie explicitement ; autorisation refusee par defaut.
- `noethys/Data/Migrations/partenaires_d6_sqlite.sql` : sequence singleton transactionnelle, factures figees, evenements. `PRAGMA foreign_keys=ON` obligatoire par connexion. Script non rejouable ; aucun ALTER historique.
- `noethys/Data/Migrations/partenaires_d6_mysql57.sql` : DDL InnoDB propose avec FKs `INT UNSIGNED` et verrou de compteur `SELECT ... FOR UPDATE` ; **non execute sur MySQL 5.7** ; les CHECK n'y sont pas garantis.
- `tests/test_partenaires_d6.py` : controles de TVA absente, source, permissions, anti-doublon, sequence, dates, lecture figee, reference externe, changement d'apercu, rollback et concurrence.
- `noethys/Utils/UTILS_Partenaires_D5.py` : correction ciblee pour neutraliser une ancienne mention provisoire de TVA dans l'export CSV et interdire les references externes concurrentes d'une facture D6.

Aucune ecriture dans `familles`, `comptes_payeurs`, `prestations`, `factures`, `compta_tiers`, `reglements` ou `ventilation`. **Un tiers partenaire n'est pas transforme en famille.** Aucun compte bancaire, numero SIRET reel ou identite de salarie n'est inclus dans les tests.

## 4. Qualification

Depuis le repertoire du kit D6 :

```
python3 -m unittest discover -s tests -p 'test_partenaires_d*.py' -q
python3 -m compileall -q noethys/Utils/UTILS_Partenaires_D*.py tests/test_partenaires_d*.py
```

**162 PASS, 0 FAIL, 0 SKIP** : D1 18, D2 49, D3-D4 43, D5 30 et D6 22. Python 3.13.5, SQLite en memoire et copie jetable pour la concurrence. Sur deux connexions, exactement une validation reussit et le compteur se retrouve a 1 ; le rollback d'une insertion de journal echouee restitue le compteur a 0. Le rejeu du DDL SQLite echoue comme prevu. `PRAGMA foreign_key_check` renvoie une liste vide, les tables historiques factices restent inchangees. Aucun champ technique de taxe dans le schema D6.

## 5. STOP-GATE production

**Pas de mise en service.** Sont encore absents/non qualifies : migrations MySQL 5.7 sur sauvegarde, integration dans Noethys wx/Qt, comptes et ACL applicatives, verrouillage de modification SQL externe, edition PDF/Word validee avec mentions legales selon le regime reel, envoi et conservation probante, numerotation synchronisee avec les eventuelles factures deja emises dans d'autres outils (risque de collision), gestion d'avoirs et de rectifications, suivi des reglements, factures deja emises en dehors de D6, audit du SIRET de l'emetteur et validation fiscale. Le prefixe `PMSL` est provisoire et le moteur suppose une serie de numerotation dediee ; ne pas l'activer sans verifier l'existence d'une serie anterieure.

**Suite conseillee :** recette sur copie MySQL, qualification de l'edition documentaire/mentions obligatoires, adaptation interface, puis validation humaine du scenario d'emission et de correction avant tout deploiement.
