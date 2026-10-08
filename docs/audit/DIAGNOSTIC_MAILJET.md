# Emails Mailjet : accepté, distribué, échoué

## Ce que Noethys sait réellement

| État | Signification | Ce que Noethys affiche ou enregistre (rail 1) |
|---|---|---|
| **Accepté par Mailjet** (succès de soumission) | L'API Send v3.1 a répondu `Status: "success"` : Mailjet a pris le message en charge. | « L'Email a été accepté par Mailjet pour envoi. Noethys ne vérifie pas sa remise effective au destinataire. » |
| | | Historique : « Envoi de l'Email '…' (accepté par Mailjet, MessageID n) ». |
| **Échec** | Mailjet a refusé le message (HTTP 4xx ou 5xx, `Status: "error"`), ou la requête n'a pas abouti. | Motif Mailjet affiché (`ErrorMessage`, code, champ concerné, statut HTTP), sans clé ni secret. Le message figure « En échec » dans le compte rendu du lot. |
| **Non tenté** | Le lot a été arrêté avant ce message. | Rubrique « Non tentés (envoi arrêté) » du compte rendu. |
| **Résultat incertain** | Délai dépassé ou connexion coupée après l'envoi de la requête : Mailjet a pu accepter le message ou non. | Compté comme un **échec** dans ce lot. Le bouton « Réessayer » peut donc créer un doublon (voir le rail 2). |
| **Distribué, rejeté, bloqué, classé spam, ouvert** | Événements produits **après** l'acceptation. | **Inconnus de Noethys** : aucun événement Mailjet n'est consommé. |

**Sources de la documentation Mailjet consultée** (`dev.mailjet.com`, guides « Send API v3.1 » et « Webhooks ») :
- Chaque destinataire d'un message accepté reçoit un `MessageUUID`, un `MessageID` et un `MessageHref`. Le `MessageID` sert à retrouver le message.
- Les événements de suivi (`sent`, `open`, `click`, `bounce`, `spam`, `blocked`, `unsub`) sont transmis par webhook (`/eventcallbackurl`).
- La page Send API ne définit pas plus précisément `success`. Noethys le traite donc **strictement comme une acceptation**, jamais comme une distribution.

## Si Mailjet a accepté le message mais que le parent ne l'a pas reçu

1. **Retrouver le message dans l'historique Mailjet** : rechercher l'adresse du parent ou le `MessageID` inscrit dans l'historique de la famille dans Noethys (catégorie Emails).
2. **Lire son statut dans Mailjet** : envoyé, ouvert, rejeté (*bounce*), bloqué (*blocked*), spam, désinscrit.
3. **Bloqué** : vérifier dans Mailjet que l'**expéditeur et son domaine sont validés**. Vérifier aussi si l'adresse figure sur la **liste d'exclusion**, par exemple après un ancien rejet ou une plainte.
4. **SPF, DKIM et DMARC** du domaine expéditeur : tous trois doivent être valides. Gmail, Yahoo et Outlook pénalisent les envois en nombre non authentifiés.
5. **Rejet (*bounce*)** : adresse erronée ou boîte pleine. Corriger la fiche de la famille.
6. **Spam** : demander au parent de vérifier ses indésirables et de marquer l'expéditeur comme fiable.
7. **Quota du forfait Mailjet** : vérifier qu'il n'était pas dépassé le jour de l'envoi.

Ces réglages se font **dans Mailjet et dans le DNS du domaine**, pas dans Noethys. Ce document ne contient aucun secret ; ne jamais y coller de clé API.

## Avant même Mailjet : la famille était-elle dans le lot ?

Depuis le rail 1, une famille configurée pour l'envoi par email ne peut plus disparaître du lot sans être signalée. L'avertissement affiché avant l'envoi indique le motif :
- « destinataire configuré introuvable » ;
- « destinataire configuré n'est plus rattaché à la famille » ;
- « adresse email vide » ;
- « document PDF non généré ».

Les rappels prennent désormais en compte les adresses libres. Avant correction, ils les ignoraient toujours.

## Orientation rail 2 : suivi réel de la distribution (comparaison sur papier, rien d'implémenté)

Objectif : savoir si un message **accepté** par Mailjet a été **distribué, rejeté, bloqué ou classé en spam**. Contrainte prioritaire : **ne rien modifier côté Connecthys**.

### Ce qui est établi

- **Documenté par Mailjet** (guides « Send API v3.1 » et « Webhooks », et liste des endpoints « Messages ») :
  - la réponse d'envoi donne, par destinataire, `MessageUUID`, `MessageID` et `MessageHref` ;
  - les événements de suivi (`sent`, `open`, `click`, `bounce`, `spam`, `blocked`, `unsub`) sont envoyés par **webhook** vers une URL configurée (`/eventcallbackurl` ou préférences du compte) ; l'URL doit répondre HTTP 200, sinon Mailjet **réessaie toutes les 30 s pendant 24 h** ;
  - existent des endpoints de lecture `GET /v3/REST/message/{ID}`, `/messagehistory/{ID}` et `/messageinformation/{ID}`.
- **Vu dans le code** : la bibliothèque `mailjet-rest` reconnaît les champs d'envoi `CustomID` et `EventPayload`, qui permettent de rattacher un événement à un identifiant propre à Noethys.
- **Déjà acquis par le rail 1** : le `MessageID` est conservé (`message.mailjet_ids`) et écrit dans l'historique de la famille, sous forme de texte.
- **Non confirmé, à lire avant toute décision** (les pages de référence détaillées n'étaient pas accessibles lors de l'étude) : le schéma exact des réponses, les valeurs de statut, la durée de conservation des données, les quotas et limites d'appel, et la disponibilité de ces ressources pour une clé d'API ordinaire.

### Comparaison

| Critère | **A. Webhook via Connecthys** | **B. Interrogation ponctuelle de l'API Mailjet** |
|---|---|---|
| Principe | Mailjet appelle une URL publique ; les événements sont stockés, puis relayés à Noethys. | Noethys interroge Mailjet avec le `MessageID` déjà conservé. |
| **Modification de Connecthys** | **Oui** : nouvelle route publique, stockage des événements, nouveau canal vers Noethys. Cela ajoute un échange au protocole de synchronisation. | **Aucune** |
| Infrastructure entrante | Requise : point d'entrée HTTPS joignable depuis Internet, authentification, CSRF à écarter pour cette route. Noethys, application de bureau, ne peut pas la porter. | Aucune : uniquement des appels HTTPS **sortants** vers Mailjet, comme pour l'envoi. |
| Compatibilité Connecthys | **Risque élevé** : un serveur amont mis à jour par `/update` écraserait la route ajoutée ; sur le fork PMSL, évolution à coordonner. | **Sans risque** |
| Fraîcheur | Événements poussés, proches du temps réel. | À la demande : état au moment de l'interrogation (une distribution ou un rejet peut prendre du temps). |
| Fiabilité | Réessais Mailjet pendant 24 h, mais perte possible si le portail est indisponible plus longtemps ; il faut dédoublonner. | Simple et idempotent : relire l'état autant de fois que nécessaire. |
| Coût de mise en œuvre | Élevé : serveur, protocole, migration, tests croisés Noethys/Connecthys. | Modéré : un second client Mailjet en lecture, un bouton « Vérifier la remise », un affichage. |
| Données à stocker | Événements par message. | Le `MessageID` de façon **structurée** : il n'existe aujourd'hui que dans le texte de l'historique ; stocker un identifiant exploitable peut exiger un petit changement de schéma, à décider au rail 2. |
| Points à lever avant de choisir | Quotas et authentification du webhook ; relais jusqu'à Noethys. | Schéma des réponses, quotas, rétention, droits de la clé d'API. |

### Recommandation

**Étudier d'abord l'option B.** Elle respecte la contrainte de compatibilité Connecthys, ne demande aucune infrastructure entrante et réutilise le `MessageID` déjà conservé. Une première version pourrait n'interroger Mailjet que sur action de l'utilisateur, avec les états « accepté, remise non vérifiée », « distribué », « rejeté », « bloqué », « spam », « inconnu ».

L'option A ne se justifie que si un suivi quasi temps réel devient indispensable **et** qu'une évolution conjointe de Connecthys est acceptée. Une option C hybride (B d'abord, A plus tard) reste possible, car B pose le stockage structuré du `MessageID` dont A aurait aussi besoin.

**Ni A ni B n'est implémentée dans ce lot.**
