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

## Proposition pour le rail 2 : suivi réel de la distribution

Ce suivi n'est pas implémenté au rail 1, car il demande une infrastructure entrante.

- **Option A, webhook Mailjet.** Elle demande un point d'entrée HTTPS joignable depuis Internet. Noethys est une application de bureau ; Connecthys pourrait jouer ce rôle, mais cela suppose une **évolution de Connecthys**. Un stockage des événements par `MessageID` et un rapprochement au `syncdown` sont aussi nécessaires.
- **Option B, interrogation à la demande.** `GET /v3/REST/message/{MessageID}` (ou l'API des statistiques), avec les identifiants désormais conservés. Un bouton « Vérifier la remise » dans l'historique suffirait. Il n'y a aucune infrastructure entrante, mais il faut des appels API supplémentaires et un quota à prévoir.
- **Prérequis acquis au rail 1** : `MessageID` et `MessageUUID` sont conservés (`message.mailjet_ids`) et le `MessageID` est écrit dans l'historique.
