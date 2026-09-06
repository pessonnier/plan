# Workflow de réalisation d'un projet informatique

Ce jeu de travail décrit le cycle de vie d'un projet informatique dans une
grande entreprise, depuis l'idée jusqu'au décommissionnement.

Le point d'entrée est `manifest.json`. Les données sont réparties par phase :

| Fichier | Périmètre |
|---|---|
| `00-referentiel.json` | Workflow, lignes d'eau, rôles et tables communes. |
| `01-cadrage-budgetisation.json` | Opportunité, cadrage et autorisation budgétaire. |
| `02-specifications-conception-marche.json` | Exigences, architecture et marché. |
| `03-realisation-qualification.json` | Réalisation, tests, recette et homologation. |
| `04-mise-en-production.json` | CAB, préproduction, déploiement et ouverture. |
| `05-maintenance.json` | Maintenance, évolutions, corrections et décision de fin de vie. |
| `06-decommissionnement.json` | Données, arrêt, retrait des actifs et clôture. |

`00-phases.json` contient le workflow directeur composé uniquement des six
phases. Les états de ce workflow pointent vers les pages de phase. Dans les
fichiers détaillés, les états terminaux pointent vers la phase suivante.

Les descriptions des états sont de courts fragments HTML. Les contrôles
bloquants sont représentés dans `Regle`; les responsabilités et conditions de
passage sont portées par `Transition`.

Les treize lignes d'eau attribuent un couloir distinct à chaque acteur :
sponsor, représentants métier, direction financière, chef de projet,
architecture, sécurité, protection des données, achats, réalisation, qualité,
CAB, exploitation et maintenance. Les transitions entre ces couloirs montrent
les sollicitations, validations et passages de relais. La page d'accueil du
site affiche le workflow complet en plus de la vue synthétique des phases.

Les pages `etats.html` et `transitions.html` servent d'exemples pour les liens
structurés. `Idee_projet`, `Enregistrer_opportunite` et `Valider_budget`
contiennent des destinations valides. `Budget_a_revoir` et `Refuser_budget`
pointent volontairement vers des pages d'état supprimées afin de vérifier le
signalement des destinations invalides.

Validation :

```powershell
py scripts/validate_workflow_data.py `
  data/workflows/projet-informatique/manifest.json
```

Génération Mermaid :

```powershell
py scripts/generate_mermaid.py `
  data/workflows/projet-informatique/manifest.json `
  --output projet-informatique.md
```

Page HTML unique :

```powershell
py scripts/generate_workflow_html.py `
  data/workflows/projet-informatique/manifest.json `
  --output build/projet-informatique.html
```

Site statique :

```powershell
py scripts/generate_workflow_site.py `
  data/workflows/catalog.json `
  --output build/site-workflows
```
