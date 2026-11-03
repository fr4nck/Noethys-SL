# Noethys-SL Qt — C19c : précontrôle avant facturation

Date : 3 novembre 2026. Ticket [#440](https://github.com/fr4nck/Noethys-SL/issues/440). Branche \`qt\`.

**Statut : code et tests préparés pour la qualification CI, pas de diffusion.**

## But

Compléter le parcours opérateur C19b avec un **contrôle avant facturation** ciblé sur UNE consommation de l'inscription sélectionnée, plutôt que d'ajouter un catalogue sans action.

Dans la rubrique Consommations, uniquement après le parcours exact *Famille → Inscription → Consommations* sur la **fixture fictive C13**, un panneau « Contrôle avant facturation — démonstration » propose un contrôle explicite par clic.

L'écran affiche sans recalcul :
- ID exact de la consommation, de l'inscription, de l'individu et de la famille ;
- état de consommation relu en base ;
- ID de la prestation associée, **montant brut enregistré** (\`12.005\` reste \`12.005\`, aucun arrondi en centimes) ;
- ID de facture éventuellement rattachée à **la prestation** — pas automatiquement à la consommation ;
- nombre de consommations faisant référence à cette même prestation : ce nombre n'est **pas** un multiplicateur de prix ;
- nombre de ventilations de règlements liées à la prestation ;
- alertes pour prestation absente, état différent de présent, compte payeur d'une autre famille, facture absente ou externe, ventilation et prestation partagée.

**Ce contrôle ne dit pas si une famille doit être facturée** et ne calcule ni montant dû, ni tarif, ni solde, ni prix par séance. Les règles wx historiques, les droits, les périodes de gestion et la logique tarifaire restent hors périmètre.

## Barrières exactes

- \`noethys_qt/c19b_operational_guard.py\` vérifie le chemin éphémère et les marqueurs fictifs C8 + C13 ; garde réévalué à **chaque clic**.
- Le SQL ouvre la source uniquement avec \`SQLite mode=ro\` + \`PRAGMA query_only=ON\` ; pas d'accès MySQL ni au profil utilisateur.
- Le résultat exige l'égalité stricte des trois identifiants famille/inscription/individu, avec le contexte de la consommation sélectionnée.
- Si la prestation ou l'état a changé depuis l'affichage, le contrôle est refusé et réclame l'actualisation.
- Une prestation partagée (notamment 28 consommations de la fixture) déclenche un avertissement explicite, et son montant brut n'est jamais additionné par consommation.
- \`BillingObservation.executable\` ne peut pas devenir vrai.
- L'interface Qt normale ne crée **pas** ce panneau : dans \`NoethysQtWindow\`, la construction n'a lieu que lorsque \`operational_route_enabled\` est autorisé par la garde fictive.

## Couverture attendue

- \`tests_qt/test_c19c_billing_preflight_core.py\` : 11 tests des clés exactes, du montant brut, de la prestation partagée, des factures inexistantes, des mutations entre lecture et clic, de la confidentialité du périmètre et des refus de données non fictives.
- \`tests_qt/test_c19c_billing_preflight_qt.py\` : 4 tests de parcours dans la coque native, sortie et remise à zéro, réaffectation de famille, désactivation hors contexte.
- Suite Qt passée de 491 à **506 tests minimum**, sans suppression de tests préexistants.
- Workflow Windows ciblé \`.github/workflows/qt-c19b-regression.yml\` complété : les 15 tests précédents + les 15 nouveaux ; la CI Qt complète demeure obligatoire.

La suite de **491/491 tests** C19b, validée au run [41674780537](https://github.com/fr4nck/Noethys-SL/actions/runs/41674780537), est un point de départ historique et ne qualifie pas C19c.

## STOP-GATE

Aucune autorisation de facturation, aucune mise en production, aucune consultation de dossier réel, aucune restauration ni modification de la base PMSL. La sauvegarde i5-10400 [#437](https://github.com/fr4nck/Noethys-SL/issues/437) reste volontairement différée.

Pour lever la barrière : qualification Windows du SHA exact, contrôle des 506 tests, puis inventaire et tests des droits et transactions de la version wx sur moteur isolé. Même une CI verte ne saurait à elle seule autoriser la facturation réelle.
