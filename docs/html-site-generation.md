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
2. le diagramme de processus Mermaid (`swimlane-beta` avec lignes d'eau,
   sinon `flowchart`) ;
3. les fiches des états, avec leur texte canonique sous les diagrammes.

Le texte canonique vient de `Etat.contenu` et son format de
`Etat.type_contenu`. Pour les anciens documents seulement, `Etat.description`
est utilisé en repli lorsque `contenu` est absent.

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

- `index.html`, avec la présentation, le diagramme des phases, le workflow
  complet par acteur et les cartes des phases ;
- `editor.html`, dans un site de catalogue, avec l'éditeur JSON ;
- `etats.html`, répertoire contenant tous les états et leur texte ;
- `transitions.html`, page d'exemple répertoriant toutes les transitions,
  leurs extrémités et la validité de leur lien ;
- `phases/*.html`, avec le diagramme et les états de chaque phase ;
- `assets/style.css` et `assets/app.js` ;
- `assets/editor.js`, dans un site de catalogue.

La vue d'ensemble est produite depuis le workflow désigné par
`site.overview_workflow_id`. Les pages de phase et le répertoire des états
utilisent `site.detail_workflow_id`. Les pages individuelles `states/*.html`
ne sont plus générées et les anciennes pages sont supprimées du répertoire de
sortie.

L'orientation des diagrammes vient de `Workflow.orientation`. Les workflows du
catalogue utilisent `LR` pour une lecture horizontale. Lorsqu'un workflow
contient des lignes d'eau, chacune devient un couloir Mermaid natif
`swimlane-beta` de premier niveau. Le libellé affiche uniquement le nom de la
ligne d'eau, sans préfixer le participant auquel elle appartient.

Dans le workflow « Projet informatique », les treize rôles disposent chacun
d'une ligne d'eau dédiée. Les validations métier, qualité, sécurité, CAB et
DPO ne sont donc plus regroupées avec les équipes qui réalisent ou exploitent
la solution.

La navigation principale contient trois entrées :

- `Vue d'ensemble et phases` ;
- `Répertoire des états` ;
- `Répertoire des transitions`.

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

Les liens « Modifier dans l'éditeur » et « Éditer ce workflow » ajoutent le
paramètre `?workflow=<slug>`. L'éditeur lit ce paramètre, présélectionne le jeu
de données correspondant et fournit un bouton « Ouvrir le workflow » pour
revenir à la version publiée.

Un manifeste peut aussi déclarer une page de référence locale :

```json
{
  "site": {
    "reference_page": "guide.json"
  }
}
```

Le fichier contient un titre, une introduction et des sections avec des
exemples Mermaid. Le générateur produit alors `guide.html` et ajoute « Guide
visuel » à la navigation du sous-site. Un exemple marqué `"render": false`
présente uniquement sa syntaxe : c'est le format retenu pour les icônes et les
images qui exigeraient des ressources locales supplémentaires. Le workflow
`data/workflows/documentation/` constitue l'exemple complet.

## Code Mermaid affiché sous les diagrammes

Chaque diagramme du site est suivi d'un élément repliable « Afficher le code
Mermaid ». Le code reste donc consultable même après le remplacement du bloc
source par le SVG rendu. Cette présentation s'applique aux vues d'ensemble,
aux workflows complets et aux pages de phase.

## Thèmes indépendants et modes clair/sombre

Le catalogue commun et chaque sous-site de workflow génèrent leur propre page
`settings.html`. Chaque périmètre propose :

- les modes `system`, `light` et `dark` ;
- les paires Océan, Forêt, Aubergine et Graphite ;
- un retour aux valeurs Océan / automatique.

Le thème initial du portail commun est défini par `theme` à la racine du
catalogue. Le thème initial d'un workflow est défini par `site.theme` dans son
manifeste :

```json
{
  "theme": { "pair": "graphite", "mode": "system" },
  "workflows": []
}
```

```json
{
  "site": {
    "theme": { "pair": "forest", "mode": "dark" }
  }
}
```

Les préférences sont stockées dans `localStorage` sous des clés préfixées par
`workflow-site-theme:<périmètre>`. Le portail et chaque workflow disposent donc
de valeurs distinctes. Un bouton « Mode clair » ou « Mode sombre » est ajouté
dynamiquement dans l'en-tête de toutes les pages : il applique immédiatement le
mode demandé, sans serveur et sans régénération. La page de paramètres permet
en plus de sélectionner la paire de couleurs et le mode automatique.

Un petit script placé dans l'en-tête applique la préférence avant la feuille de
style ; le thème Mermaid clair ou sombre est ensuite choisi au moment du rendu.
Aucun thème ne télécharge de police, de CSS ou de script.

## Éditeur JSON du catalogue

La page `editor.html` embarque une copie fusionnée et validée de chaque
manifeste du catalogue. Elle ne modifie jamais les fichiers placés dans
`data/workflows`.

Pour chaque workflow, l'éditeur affiche le chemin du manifeste, la liste des
fragments lus et le chemin de la copie fusionnée exacte ayant servi à la
génération : `build/site-workflows/sources/<slug>.json` dans la sortie standard.

L'éditeur affiche le vocabulaire normatif défini dans
`docs/specifications.md`. Les libellés d'interface utilisent notamment
« texte de l'état », « format du texte », « destination du lien » et
« répertoire des états ».

Le bouton de disposition place le formulaire des transitions à droite de celui
des états ou en dessous. Le libellé du bouton indique l'action disponible. La
préférence est enregistrée dans `localStorage` sous la clé
`workflow-editor-transitions-below`. La mise en page responsive conserve
automatiquement l'empilement sur les écrans étroits.

L'utilisateur peut :

- choisir « Projet informatique », « Analyse statique de code » ou toute autre
  entrée future du catalogue ;
- choisir un état depuis la liste déroulante du champ identifiant, présentée
  sous la forme `<nom> — <identifiant>`, puis le modifier ou le supprimer ;
- sélectionner « Nouvel état… » et saisir un nouvel identifiant pour créer un
  état ;
- ouvrir `etats.html` dans un écran distinct pour consulter l'inventaire
  exhaustif ;
- saisir le texte de l'état en Markdown, HTML ou texte brut, Markdown
  étant le format proposé pour un nouvel état ;
- définir le lien structuré d'un état (`type_lien`, `cible_lien` et
  `libelle_lien`) ;
- choisir une transition existante depuis la liste déroulante du champ
  identifiant, présentée sous la forme `<libellé> — <identifiant>`, puis la
  modifier ou la supprimer ;
- saisir un nouvel identifiant de transition pour en créer une ;
- définir le lien structuré d'une transition (`type_lien`, `cible_lien` et
  `libelle_lien`) ;
- modifier directement le document JSON complet pour agir sur les rôles,
  règles, lignes d'eau, workflows et autres métadonnées ;
- appliquer le JSON brut aux formulaires, le copier ou l'enregistrer sous le
  nom `<slug>-modifie.json`. Lorsque l'API d'accès aux fichiers est disponible,
  le navigateur affiche un sélecteur permettant d'écrire à l'emplacement choisi ;
  sinon le fichier est placé dans les téléchargements. Firefox ne propose pas
  cette API : la page adapte le libellé en « Télécharger le JSON » et indique
  comment activer « Toujours demander où enregistrer les fichiers » dans les
  paramètres du navigateur.

Une section « Validité des liens des états et des transitions » recense :

- le lien structuré porté par chaque état ;
- le lien structuré porté par chaque transition ;
- les attributs `href` trouvés dans un texte HTML ;
- les liens trouvés avec la syntaxe Markdown dans le texte de l'état ou de la
  transition.

Le contrôle accepte les URL HTTP(S), les adresses `mailto:`, les ancres et les
pages internes de phase. Les anciennes destinations `states/*.html` sont
invalides puisque les pages individuelles d'état ne sont plus produites. Le
message distingue le cas où l'identifiant destinataire n'existe plus. Une URL
distante est jugée
sur sa syntaxe et son protocole ; l'éditeur statique ne teste pas sa
disponibilité réseau.

Le workflow « Projet informatique » contient volontairement, dans l'état
`Idee_projet`, une URL HTTP(S) valide, une destination vers l'état supprimé
`Etat_supprime` et un protocole interdit dans son texte Markdown. Son lien
structuré fournit aussi un exemple d'URL valide.
L'état `Budget_a_revoir` pointe volontairement vers une ancienne page d'état.
Les transitions `Enregistrer_opportunite` et `Valider_budget` fournissent des
liens valides, tandis que `Refuser_budget` pointe vers une page supprimée.
Les résultats sont visibles dans `etats.html`, `transitions.html` et dans le
rapport de l'éditeur.

Le formulaire conserve les champs avancés existants lorsqu'un état ou une
transition est modifié. L'identifiant d'un élément existant est sélectionné et
n'est pas ressaisi dans le formulaire. La suppression d'un état retire aussi
ses transitions et règles associées afin de maintenir un document cohérent.
La suppression explicite d'une transition retire également les règles qui la
référencent.

La validation côté navigateur contrôle la structure des tables, les
identifiants compatibles Mermaid, les doublons et les principales références
croisées. Une destination invalide est un avertissement visible qui ne bloque
ni l'application, ni la copie, ni l'enregistrement du JSON. Les boutons
d'export sont désactivés uniquement en cas d'erreur structurelle. Le fichier
enregistré est un jeu de données fusionné. La page statique ne modifie jamais
automatiquement les sources sous `data/workflows` ; l'utilisateur doit choisir
explicitement la destination. Le fichier peut
être validé avec `scripts/validate_workflow_data.py` en précisant
`--schema schema/workflow-model.json`.

Le site peut ensuite être publié par n'importe quel serveur de fichiers
statiques. L'ouverture directe de `index.html` permet également de parcourir
les pages. Le script local `assets/app.js` est chargé comme script classique,
puis charge `assets/mermaid.min.js`, également local. Cette organisation évite
le blocage des modules JavaScript et des CDN avec une URL `file://`, notamment
dans Firefox. Une URL personnalisée se terminant par `.mjs` reste prise en
charge par import dynamique lorsqu'un serveur HTTP est utilisé.

## Rendu Mermaid

Les sites statiques générés embarquent par défaut :

```text
assets/mermaid.min.js
```

Ce fichier est une copie de la distribution Mermaid dont la version, le nom de
fichier, les URL d'origine et la somme SHA-256 sont verrouillés dans
`scripts/vendor/javascript-dependencies.json`. Sa licence MIT est placée dans
`scripts/vendor/MERMAID-LICENSE.txt` et copiée avec le moteur dans les actifs
du site. La version est volontairement épinglée :
les diagrammes natifs `swimlane-beta`, utilisés pour les lignes d'eau,
nécessitent Mermaid 11.16.0 ou une version ultérieure. Une URL personnalisée
doit donc servir une version au moins équivalente si le site contient des
lignes d'eau.

Après rendu, les SVG plus larges que leur panneau conservent leur largeur
naturelle. Le panneau devient défilable horizontalement afin que les noms des
acteurs, activités et transitions restent lisibles. Mermaid dimensionne les
couloirs depuis leur contenu et la structure du graphe ; les couloirs d'un même
diagramme restent alignés sur la largeur globale du swimlane.

### Mise à jour de Mermaid

La mise à jour est une opération volontaire, effectuée sur une machine ayant un
accès Internet. Depuis la racine du dépôt :

```powershell
.\scripts\update_javascript_dependencies.ps1 -MermaidVersion 11.17.2
.\scripts\update_javascript_dependencies.ps1 -Check
py scripts/generate_workflow_site.py `
  data/workflows/catalog.json `
  --output build/site-workflows
py -m unittest discover -s tests -v
```

La première commande télécharge la distribution officielle et sa licence,
calcule la somme SHA-256 et actualise le fichier de verrouillage. L'ancienne
distribution versionnée n'est pas supprimée automatiquement afin de rendre la
mise à jour réversible ; elle peut être retirée après validation du nouveau
site. `-Check` ne contacte pas Internet et vérifie uniquement les fichiers
locaux. Il doit réussir sur les postes isolés.

En fonctionnement normal et lors de la génération, aucun téléchargement n'est
effectué. La page HTML unique incorpore aussi le moteur verrouillé ; le site
multi-pages le copie dans `assets/mermaid.min.js`.

### Dimensions des diagrammes

Les dimensions sont définies dans `site.diagram` du manifeste :

| Clé | Défaut | Effet |
|---|---:|---|
| `node_spacing` | `50` | Espace entre états d'un même rang. |
| `rank_spacing` | `80` | Espace entre rangs ; écart horizontal d'un `flowchart` orienté `LR`. |
| `diagram_padding` | `20` | Marge intérieure autour du diagramme. |
| `wrapping_width` | `200` | Largeur de référence pour l'enroulement des libellés d'état. |
| `lane_title_wrap` | `22` | Seuil de coupure des titres de couloir sur deux lignes ; `0` désactive la coupure. |
| `use_max_width` | `false` | `false` conserve la largeur naturelle ; `true` ajuste le SVG au panneau. |

`node_spacing`, `rank_spacing`, `diagram_padding` et `wrapping_width` sont les
options officielles du moteur flowchart réutilisé par `swimlane-beta`.
`lane_title_wrap` est appliqué par le générateur avant le rendu Mermaid. Les
titres de couloir utilisent uniquement `Ligne_eau.nom` : le nom du participant
parent, par exemple « Organisation porteuse du projet », n'est pas préfixé.

Avec Mermaid 11.17.2, les essais comparant `rank_spacing: 20` et
`rank_spacing: 100` donnent la même largeur pour les diagrammes
`swimlane-beta` : le réglage agit sur le flowchart général, mais pas encore sur
la distance horizontale du moteur swimlane. Le manifeste du projet utilise le
compromis testé `20 / 20 / 16 / 180 / 18`, qui réduit la largeur du workflow
complet grâce aux libellés plus courts tout en gardant assez d'espace vertical.
Le paramètre `rank_spacing` reste exposé pour les flowcharts et pour une future
prise en charge par Mermaid.

Mesures obtenues avec Mermaid 11.17.2 sur le workflow complet et la phase de
cadrage :

| Variante (`node/rank/padding/wrapping/titre`) | Phase | Workflow complet |
|---|---:|---:|
| compacte `10/10/20/200/22` | 5 326 × 592 px | 32 997 × 3 207 px |
| intermédiaire `30/50/16/190/20` | 5 318 × 664 px | 31 958 × 3 639 px |
| aérée `50/80/20/200/22` | 5 326 × 752 px | 32 997 × 4 167 px |
| retenue `20/20/16/180/18` | 5 030 × 632 px | 30 889 × 3 362 px |

Un essai isolé avec `rank_spacing: 100` conserve exactement les dimensions du
swimlane de la variante retenue. Un essai avec `use_max_width: true` comprime le
SVG complet dans les quelque 831 px disponibles du panneau et rend ses textes
illisibles ; la largeur naturelle avec défilement est donc conservée.

L'URL peut être remplacée, notamment par une version hébergée en interne :

```powershell
py scripts/generate_workflow_site.py `
  data/workflows/projet-informatique/manifest.json `
  --output build/site `
  --mermaid-url https://intranet.example/mermaid/mermaid.esm.min.mjs
```

Si le moteur n'est pas disponible, la navigation et les descriptions restent
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
- la génération des couloirs Mermaid `swimlane-beta` ;
- le filtrage du HTML dangereux ;
- la création des pages d'état et de phase ;
- la création et les contrôles principaux de l'éditeur JSON ;
- les liens de navigation ;
- la configuration de l'URL Mermaid.

Commande :

```powershell
py -m unittest discover -s tests -v
```
