# Génération HTML et site statique

Le projet fournit deux générateurs HTML à partir d'un jeu de données validé :

- `scripts/generate_workflow_html.py` produit une page HTML unique ;
- `scripts/generate_workflow_site.py` produit un site statique navigable.

Le générateur de site accepte aussi un catalogue
`workflow-site-catalog-v1`, qui produit une page de choix et un sous-site par
workflow.

Les deux commandes acceptent un fichier de données complet ou un manifeste
`workflow-data-manifest-v1`. Elles valident systématiquement les données contre
`schema/workflow-model.json` avant de produire une sortie.

## Page HTML unique

La page unique contient, dans cet ordre :

1. le titre et la description du workflow ;
2. le diagramme Mermaid `flowchart` ;
3. les fiches des états, avec le contenu de `Etat/description` sous les
   diagrammes.

Le `stateDiagram-v2` n'est actuellement pas affiché dans les pages HTML.

Exemple :

```powershell
py scripts/generate_workflow_html.py `
  data/workflows/projet-informatique/manifest.json `
  --output build/projet-informatique.html
```

Pour un fichier de données non fragmenté, le schéma doit être indiqué :

```powershell
py scripts/generate_workflow_html.py examples/workflow-data.json `
  --schema schema/workflow-model.json `
  --output build/exemple.html
```

## Site statique navigable

Le site statique contient :

- `index.html`, avec la présentation, le diagramme et les cartes des phases ;
- `etats.html`, avec tous les états détaillés du workflow ;
- `phases/*.html`, avec le diagramme et les états de chaque phase ;
- `states/*.html`, avec la description, les transitions entrantes et
  sortantes, les rôles et les contrôles associés ;
- `assets/style.css` et `assets/app.js`.

La vue d'ensemble est produite depuis le workflow désigné par
`site.overview_workflow_id`. Les pages de phase et d'état utilisent
`site.detail_workflow_id`.

L'orientation des diagrammes vient de `Workflow.orientation`. Les workflows du
catalogue utilisent `LR` pour une lecture horizontale.

La navigation principale contient deux entrées :

- `Vue d'ensemble et phases` ;
- `Tous les états`.

La navigation latérale peut être masquée ou réaffichée avec le bouton `☰`.
Son infobulle et son libellé accessible indiquent l'action disponible. La
préférence est enregistrée dans `localStorage` sous la clé
`workflow-navigation-collapsed` et s'applique aux autres pages du site.

L'ancienne page `workflow.html` n'est plus générée et est supprimée du
répertoire de sortie lors d'une nouvelle génération.

Les liens définis dans `Etat` deviennent des liens Mermaid cliquables. Dans les
pages de phase, un état terminal peut ainsi conduire directement à la page de
la phase suivante.

Mermaid est initialisé avec `securityLevel: "loose"` car le mode `strict`
désactive les directives `click`. Cette option ne dispense pas des contrôles :
les cibles de liens sont validées par le modèle et les contenus HTML métier
restent filtrés avant insertion.

Exemple :

```powershell
py scripts/generate_workflow_site.py `
  data/workflows/catalog.json `
  --output build/site-workflows
```

Le catalogue contient des entrées de la forme :

```json
{
  "format": "workflow-site-catalog-v1",
  "workflows": [
    {
      "slug": "projet-informatique",
      "manifest": "projet-informatique/manifest.json",
      "label": "Projet informatique"
    }
  ]
}
```

Chaque workflow est généré dans `<slug>/`. Un lien « Choisir un workflow »
permet de revenir au catalogue depuis toutes les pages du sous-site.

Le site peut ensuite être publié par n'importe quel serveur de fichiers
statiques. L'ouverture directe de `index.html` permet également de parcourir
les pages. Le script local `assets/app.js` est chargé comme script classique,
puis effectue un import dynamique du moteur Mermaid. Cette organisation évite
le blocage courant des scripts locaux `type="module"` avec une URL `file://`.

## Rendu Mermaid

Par défaut, les pages chargent Mermaid depuis :

```text
https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs
```

L'URL peut être remplacée, notamment par une version hébergée en interne :

```powershell
py scripts/generate_workflow_site.py `
  data/workflows/projet-informatique/manifest.json `
  --output build/site `
  --mermaid-url https://intranet.example/mermaid/mermaid.esm.min.mjs
```

Si le module n'est pas disponible, la navigation et les descriptions restent
utilisables ; le code Mermaid est affiché comme texte.

Après un rendu réussi, l'élément racine HTML porte l'attribut :

```html
data-mermaid-rendered="true"
```

En cas d'échec de chargement ou de rendu, sa valeur est `false` et un message
est affiché au-dessus de chaque diagramme.

## Sécurité du contenu HTML

`Etat/description` et les contenus de type `html` ne sont jamais insérés
directement. Le générateur conserve uniquement les balises documentaires
suivantes :

```text
p, ul, ol, li, strong, em, b, i, code, pre, br, a
```

Les attributs événementiels, scripts et URL non sûres sont supprimés. Les
contenus de type `texte` ou `markdown` sont échappés et affichés comme texte ;
le générateur ne transforme pas le Markdown en HTML.

## Options communes

| Option | Description |
|---|---|
| `--schema` | Schéma à utiliser pour un fichier de données non fragmenté. |
| `--workflow-id` | Workflow à sélectionner si plusieurs workflows sont présents. |
| `--output` | Fichier HTML ou répertoire de site à produire. |
| `--mermaid-url` | URL du module Mermaid utilisé par le navigateur. |

## Tests obligatoires

Les tests vérifient notamment :

- la présence des diagrammes avant les descriptions dans la page unique ;
- le filtrage du HTML dangereux ;
- la création des pages d'état et de phase ;
- les liens de navigation ;
- la configuration de l'URL Mermaid.

Commande :

```powershell
py -m unittest discover -s tests -v
```
