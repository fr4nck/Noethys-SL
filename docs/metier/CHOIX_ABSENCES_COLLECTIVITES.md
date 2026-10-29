# Noethys-SL - Choix des absences injustifiees dans la situation des communes

## Fonctionnement

Le module **Facturation > Situation des communes (ALSH)** distingue :

- les journees-enfants **presentes** (`present`), toujours en frequentation reelle ;
- les **absences injustifiees** (`absenti`), comptabilisees **sur choix explicite** de l'utilisateur ;
- les reservations `reservation` du futur, isolees dans les previsions ;
- les absences justifiees `absentj`, attentes `attente` et refus `refus`, non retenus.

Le choix se fait par **commune, annee et dossier** avec la case « Compter les absences
injustifiees », **decochee par defaut**. Les dossiers enregistres avant cette version
continuent a exclure ces absences. Le choix est enregistre dans le JSON local du dossier.

Lorsque l'option change apres un premier releve, le logiciel demande une confirmation
avant de supprimer les lignes mensuelles pour recalculer les journees. Les acomptes
communaux sont preserves. L'import automatique des consommations est en lecture seule,
et le parametre est transmis sans utiliser de controle wx dans un thread secondaire.

## Calcul

```
Participation = journees reellement presentes * tarif conventionnel
              + absences injustifiees retenues * tarif conventionnel [option]
              + journees futures reservees * tarif conventionnel
Solde indicatif = participation - acomptes communaux recus et affectes a N
```

Les deux formes de journees retenues sont **toujours distinguees** dans la synthese
Noethys et dans les exports PDF, CSV et Excel ; les absences facturees aux familles ne
sont jamais appelees "presences reelles". Les montants familiaux ne sont pas utilises.
Le moteur refuse qu'une meme journee-enfant soit comptee deux fois a partir d'etats
ou d'unites contradictoires. Les etats inconnus restent des erreurs explicites.

**Reserve contractuelle :** les conventions mises a disposition font reference aux
journees-enfants realisees. La facturation des absences injustifiees aux familles ne
prouve pas qu'elles peuvent etre financees par la commune. Un rapport qui inclut
`absenti` porte donc le statut **PROVISOIRE - ABSENCES A VALIDER**, meme si les autres
controles ont ete coches ; le solde certifie n'est pas emis. Une validation ecrite de
la commune/convention doit etre apportee avant la transmission comme solde definitif.

## Qualification

Tests de regression sur SQLite fictif, aucun acces ni modification de production :
choix par defaut et opt-in, exclusion `absentj`/`attente`/`refus`, `absenti` futur,
calculs et cache Excel, double comptage, integrite de la provenance, export PDF/CSV,
refus d'option incoherente ou d'un changement de perimetre sans reimport. Pas de
reconstruction d'executable Windows ni de test runtime wx dans cet environnement.