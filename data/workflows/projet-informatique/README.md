# Workflow de réalisation d'un projet informatique

Ce jeu de travail décrit le cycle de vie d'un projet informatique dans une
grande entreprise, depuis l'idée jusqu'au décommissionnement.

Le point d'entrée est `manifest.json`. Les données sont réparties par phase :

| Fichier | Périmètre |
|---|---|
| `00-referentiel.json` | Workflow, rôles et tables communes. |
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
  data/workflows/projet-informatique/manifest.json `
  --output build/site-projet-informatique
```
