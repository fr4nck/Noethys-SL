# Noethys-SL - Fréquentation ALSH et participations des communes

**Lot 2 intégré à wx (sources, 29 octobre 2026)** - moteur, fenêtre Noethys-SL,
lecture SQL des présences en lecture seule, tests et éditions de synthèse.
Pas de migration de base, de facturation des familles ni de modification des présences.

## La règle métier (correction de la première proposition)

Ce module ne calcule **pas des prestations facturées**. Il calcule la **participation
financière conventionnelle** d'une commune à partir des journées-enfants des
habitants qui fréquentent l'ALSH :

`participation annuelle = somme(journées-enfants réellement effectuées × montant communal par journée)`

Pour l'estimation de fin d'année, ajouter séparément les **journées futures réservées**,
non certaines. Le **solde prévisionnel** correspond au total annuel estimé **moins les
acomptes de la commune affectés à cette année et réellement perçus**. Ne jamais
soustraire à nouveau les montants des familles, la CAF, la MSA ou la CTG : ces
financements ont servi à fixer les tarifs de la convention.

Aucune TVA et aucune notion de HT/TTC dans le calcul ou l'état produit.

### Tarifs relevés dans les conventions fournies

| Dispositif | Commune(s) | Période civile | Participation par journée-enfant |
|---|---|---|---:|
| ALSH Pêle-Mêle classique | Availles-sur-Seiche, Bais, Drouges, La Guerche-de-Bretagne, Moussé, Moutiers, Rannée, La Selle-Guerchaise, Visseiche | 2025-2026 | 11,54 € |
| ALSH Ados | Bais (convention fournie) | 2024-2026 | 19,55 € |

Les tarifs de ces documents sont préremplis, mais le drapeau
`tarif_confirme` vaut **false** : il faut vérifier la validité et la signature
pour la commune avant d'émettre un état comme vérifié, particulièrement pour
la convention Ados (exemplaire fourni ne suffisant pas à établir sa signature
par toutes les parties). Il ne faut pas étendre le tarif Ados aux autres communes.
L'année 2027 n'est pas couverte par ces conventions et ne reçoit pas de tarif
présumé.

La convention ALSH classique prévoit **trois acomptes en mars, juin et septembre**
représentant ensemble **75 % de la contribution N-1**, puis un solde après le
récapitulatif de fréquentation réelle de N. Le moteur soustrait uniquement les
acomptes **effectivement perçus** et imputés à N ; il ne considère pas les
acomptes théoriques comme encaissés.

## Périmètre et comptage

- Base : **année civile**, du 1er janvier au 31 décembre, même si les inscriptions
  couvrent deux années scolaires.
- Commune : **domicile de l'enfant** à justifier, **pas la commune du site d'accueil**.
- Compter les jours **présents** ; les réservations futures constituent un prévisionnel,
  jamais un réalisé. Ne pas transformer une réservation passée en présence.
- Un enfant / un jour / un accueil compte **au maximum une journée**. Repas et
  garderies ne sont pas des journées supplémentaires. Les doublons sont rejetés.
- Demi-journées : **aucune conversion implicite**. Le coefficient 0,5 est disponible
  uniquement lorsque la règle de convention a été confirmée explicitement.
- Deux accueils peuvent avoir **des tarifs différents**, notamment ALSH et Ados.
- Un état **nominatif annuel** est prévu à la phase suivante : les conventions
  demandent nom, prénom, date de naissance, domicile et jours par mois. Le PDF de
  ce lot reste une **synthèse non nominative** destinée à une situation intermédiaire.
- Les changements de domicile en cours d'année doivent être qualifiés avant
  toute édition définitive. La base historique ne doit pas être déduite de
  `ville_resid` courant sans vérification.

## Utilisation dans Noethys-SL wx

Le menu `Facturation -> Situation des communes (ALSH)` ouvre une seule fenêtre : commune, année, date d'arrêté, conventions,
fréquentation mensuelle (réel/prévisionnel), acomptes de commune, quatre contrôles
sur pièces, synthèse et exports PDF/CSV/Excel. Les lignes manuelles mensuelles permettent
un premier état sans importer des données nominatives.

**Connexion à Noethys-SL wx intégrée** : dans `Facturation → Situation des communes
(ALSH)`, le bouton « Charger les présences Noethys... » interroge `GestionDB`
en lecture seule, après sélection manuelle des unités qui correspondent à des
journées-enfants entières. Les adresses `adresse_auto` des enfants sont résolues
sur l'état **actuel** du fichier. Aucun extrait nominatif n'est conservé dans le
JSON ni dans l'état de synthèse. Les versements communaux restent saisis
séparément sur justification, sans déduction des paiements familiaux.

La sélection des unités n'est jamais devinée à partir de leur libellé. Les
absences et anciennes réservations ne constituent pas un réalisé. Les unités
non sélectionnées sont exclues et empêchent la certification si leur sélection
n'a pas été explicitement qualifiée exhaustive. Tout domicile non résolu est
écarté et signale un total potentiellement incomplet. Le changement d'adresse
en cours d'année ne peut pas être rétabli automatiquement par cette lecture.
Avant d'émettre un état définitif, vérifier les communes de domicile à la date
de fréquentation ainsi que les conventions effectivement signées.

Les valeurs du rapport d'exemple restent entièrement fictives.

L'utilitaire `consolider_export_consommations` est le noyau technique du futur
raccordement : il accepte les consommations Noethys et un mapping **explicite**
`IDactivite:IDunite` → convention, poids 0 / 0,5 / 1. Il rejette les unités
non qualifiées et les chevauchements, regroupe au plus une journée par enfant
et par jour, ignore les absences, filtre la commune de résidence. Il **ne lit
pas** `GestionDB` et il ne prétend pas régler le suivi historique des adresses.

### Structure JSON

```json
{
  "schema": "noethys-sl.frequentation-collectivites.v1",
  "commune": "Bais",
  "annee": 2026,
  "arrete": "2026-10-29",
  "emetteur": "PÊLE-MÊLE SPORTS ET LOISIRS",
  "conventions": [
    {
      "id": "ALSH-2025-2026",
      "accueil": "ALSH classique",
      "debut": "2025-01-01",
      "fin": "2026-12-31",
      "tarif_jour": "11.54",
      "tarif_confirme": false,
      "demi_journee_autorisee": false,
      "justificatif_tarif": "Convention ALSH 2025-2026"
    }
  ],
  "jours": [
    {
      "id": "RELEVE-01",
      "convention": "ALSH-2025-2026",
      "mois": 1,
      "nature": "realise",
      "nombre": "10",
      "justificatif": "Etat de frequentation janvier - a renseigner"
    }
  ],
  "acomptes": [
    {
      "id": "ACOMPTE-01",
      "convention": "ALSH-2025-2026",
      "date": "2026-03-10",
      "exercice": 2026,
      "montant": "100.00",
      "justificatif": "Virement mairie - a renseigner"
    }
  ],
  "controles": {
    "frequentation": false,
    "prevision": false,
    "domiciliation": false,
    "acomptes": false
  }
}
```

Le JSON ci-dessus est un **exemple schématique fictif**, pas un état de Bais.
Le moteur refuse les anciens dossiers « situation financière » du premier lot,
qui reposaient sur des montants de prestations.

Les totaux indicatifs sont calculés sur les lignes saisies, mais le **solde
vérifié** n'est disponible qu'une fois les conventions, les sources et les
quatre contrôles confirmés. Les mois non documentés ne sont pas assimilés à
zéro lorsque les contrôles ne sont pas validés. La date d'arrêté à l'intérieur
d'un mois suppose que le réel et le prévisionnel du mois ont été distingués
sur les relevés d'origine.

## Qualification

46 tests métier, lecture SQL sur base SQLite fictive et export XLSX,
complétés par 3 tests d'installation ciblée (49 PASS).
Aucun réseau ni base de production.
Exports PDF/CSV/Excel (.xlsx) vérifiés sur un jeu fictif ; le PDF tient sur une page et
porte un marquage explicite de fiction. La fenêtre wx a été compilée
syntaxiquement mais **non testée en runtime sur Windows 5700X**.

Le classeur Excel comporte quatre feuilles : Situation, Mensuel, Versements,
Controles. Il reprend les chiffres du moteur en valeurs numeriques, avec
formules et resultats mis en cache pour les totaux annuels. Une ligne
mensuelle inconnue reste NON CALCULABLE ; les versements ulterieurs a l'arrete
restent visibles mais exclus du total recu. Les sources des tarifs sont
renseignees dans les commentaires des cellules lorsqu'un dossier JSON est
fourni. La mise en forme definitive de l'Excel est reportee.

### Qualification restante et évolution

Le runtime graphique Windows n'a pas pu être exécuté dans cet environnement
sans wxPython. La version intégrée au code wx n'est pas encore un installateur
Windows ni une release. Après recette Windows sur copie isolée : propager
le moteur commun sur `main` puis les autres interfaces pertinentes selon
les règles du dépôt ; étudier le récapitulatif nominatif annuel exigé par
les conventions, en encadrant l'accès aux données personnelles et en vérifiant
les adresses historiques. Aucun acompte n'est considéré comme reçu sans pièce.