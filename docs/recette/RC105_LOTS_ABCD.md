# Noethys-SL RC10.5 — jalons constructifs A / B / C / D

Date de cadrage : 03/11/2026. Branche de consolidation : `wx`.
**Statut : candidats de développement ; aucune release RC10.5 publiée.**
Version publique prévue : `0.1.0-rc.10.5`. Version interne historique :
`1.3.4.4` conservée ; aucune migration de base.

Ce dossier ne remplace pas la recette fonctionnelle du Connecthys
d'origine ni la restauration MySQL du poste de travail PMSL.

## Contrat de sortie commun

Un lot est au stade **TESTABLE** lorsque son code, ses tests synthétiques
et ses instructions de recette existent. Il est **QUALIFIÉ** seulement
lorsque les tests Windows sur le SHA exact sont PASS et la validation
fonctionnelle en environnement isole est documentée. Le statut **LIVRABLE**
de RC10.5 exige les quatre lots qualifiés et les gates #437/#438/#439/#441
levés explicitement. Un simple `compileall`, des tests source ou un ZIP
généré ne suffisent pas.

| Lot | Première fonctionnalité exploitable | Contrôle automatique | Blocage avant livraison |
| --- | --- | --- | --- |
| A — fiabilité | `scripts/auditer_sauvegarde_rc105.py` : audit en lecture seule d'une archive `.nod` non chiffrée, catégories réellement présentes (DATA / PHOTOS / DOCUMENTS), vérification CRC et manifeste SQL V1. Verdict PASS / LEGACY / FAIL, périmètre indiqué séparément ; **aucun accès MySQL** | `tests.test_rc105_lot_a_archive`, `tests.test_rc105_lot_a_publication`, `tests.test_rc105_lot_a_restauration_trio` | Restauration DATA et DOCUMENTS sur serveur MySQL isolé, comparaison des données ; PHOTOS facultatif, test de fermeture et PID sur poste Windows (issues #437/#438) |
| B — documents et envois | Refus d'expédier un reçu PDF absent, vide ou tronqué, depuis l'édition famille et la saisie de règlement ; PDF temporaire non valide purgé | `tests.test_rc105_lot_b_recus_pdf`, `tests.test_noethys_sl_recus_envoi` | Reçu réel signé/généré, serveur SMTP/Mailjet de recette, refus, acceptation partielle, interruption et absence de double envoi |
| C — ALSH | Fiche famille unifiée ALSH/Club ados à deux pages ; nouvelle sortie PDF publiée de manière atomique, ancienne fiche préservée si erreur ; au-delà de 4 enfants, refus explicite au lieu d'omission | `tests.test_rc105_lot_c_famille_pdf`, `tests.test_noethys_sl_accueil_familles`, `tests.test_noethys_sl_accueil_familles_impression` | Contrôle visuel des 2 pages A4, sites La Guerche / Moutiers / Bais / Club ados, CAFPRO non coché avant signature, PAI/autorisations et repas |
| D — sécurité et stabilité | Modes opt-in SSH, SHA256 de `models.py` et `config.py` atomique ; ancien Connecthys inchangé par défaut. Correction de la course du ping wx provoquant `float - NoneType` pendant l'export | `tests.test_rc105_lot_d_ping_concurrence`, `tests.test_audit_reseau_connecthys`, `tests.test_connecthys_ssh_pinning_rc105`, `tests.test_connecthys_models_pinning_rc105`, `tests.test_connecthys_config_privacy_rc105`, `tests.test_connecthys_config_atomic_rc105` | Synchro montante + descendante contre un Connecthys historique isolé ; pas de fuite de jetons ; clé hôte validée indépendamment ; installation/fermeture Windows vérifiées |

## Lot A — utilisation immédiate et limites

La commande ci-dessous ne fait qu'ouvrir le ZIP Noethys non chiffré. Elle ne
l'extrait pas et n'exécute aucune requête. À utiliser **sur une copie locale**
d'une archive, jamais pour écraser une sauvegarde :

```powershell
# ENVIRONNEMENT : 5700X ou i5-10400 / Windows PowerShell 5.1
# Lecture seule ; aucun serveur, aucune installation ni telechargement
Set-Location -LiteralPath $HOME
# Dans un clone source Noethys-SL ou avec le script et son module source :
python scripts/auditer_sauvegarde_rc105.py "C:\chemin\copie_archive.nod"
```

Code de retour : `0 = PASS` (intégrité des SQL présents, **pas une preuve de
restauration**) ; `2 = LEGACY` (anciens dumps sans manifeste, prudence) ;
`1 = FAIL` (corruption ou structure invalide). Le rapport contient
`perimetre_complet` et `categories_absentes` : une archive partielle voulue
reste contrôlable, sans fausse déclaration de couverture de données. Le format crypté `.noc`
ne peut pas être vérifié directement ; déchiffrer **une copie** dans un
bac à sable maîtrisé, sans afficher le mot de passe en ligne de commande.
Ne jamais considérer cette vérification comme une sauvegarde suffisante.
**Aucun nouveau contrôle du lot A ne doit interdire une sauvegarde partielle
choisie, modifier la procédure de sauvegarde existante ou empêcher la lecture
d'une archive historique.** Pour clore #437, la preuve attendue porte sur DATA et DOCUMENTS :
PHOTOS est strictement facultatif, également dans la recette et les
critères de validation. Le logiciel n'impose pas l'export de PHOTOS. La restauration sur serveur MySQL jetable peut
porter sur une archive partielle et signale alors le périmètre effectivement
testé.

## Lot B — engagement de non-faux-succès

Un reçu n'est pas marqué « envoyé » quand sa création échoue ou quand
le PDF généré manque du marqueur final. Les contrôles PDF sont seulement
des contrôles **physiques minimaux**, sans validation de signature ni
garantie du contenu financier. Vérifier l'acceptation réelle par chaque
destinataire dans les journaux du fournisseur avant toute relance après
une erreur de réseau.

## Lot C — fiche commune et limites explicites

Une famille peut mêler un enfant ALSH et un ado, ou combiner un ALSH et
le Club ados pour un même jeune, sans nouvelle inscription implicite.
Le PDF familial préserve un tableau de quatre lignes et ne requalifie
pas des consentements médicaux/photo ou CAFPRO non signés. Une fratrie
de cinq enfants ne peut pas être imprimée silencieusement en n'en
montrant que quatre : édition à étendre dans un lot ultérieur selon
un modèle papier adapté, sans signer des données omises.

## Lot D — invariant Connecthys d'origine

Tous les champs `ssh_host_key_sha256`, `models_sha256`,
`ssh_config_prive`, `ssh_config_atomique` restent vides/faux par
défaut. Le protocole historique, les URL, identifiants, formats SV2 et
les commandes restent conservés. Les nouvelles vérifications ont
des limites : SHA256 et refus d'imports relatifs ne sont pas un sandbox,
SFTP posix-rename peut ne pas être supporté par l'hébergeur, et 0600
peut empêcher WSGI de lire la config. **Ne pas activer ces options en
production avant vérification et test de retour arrière.**

## Qualification des quatre lots sur le SHA final

Le workflow `.github/workflows/noethys-sl-rc105-windows.yml` exécute
les contrôles A/B/C avant les tests Connecthys D et les contrats complets.
La CI rapide `wx` inclut les mêmes tests pour détecter une régression.
La construction doit être lancée en candidat uniquement
(`publier=false`). Un SHA final PASS à la CI ne suffit pas pour déclarer
les étapes terrain vérifiées.

**Barrière absolue :** aucune mutation de la base PMSL, aucune activation
des options du portail réel, aucune migration, aucune suppression de
sauvegarde. Les tests utilisent des bases et fichiers purement fictifs.
Les incidents #437 (backup restaurable) et #438 (fermeture du processus)
restent ouverts jusqu'à preuve hors CI.
