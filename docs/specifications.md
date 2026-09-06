# Spécifications fonctionnelles

Chaque exigence possède un identifiant stable utilisé dans la matrice
`traceability/requirements.json`. Ces identifiants ne doivent pas être
réutilisés pour une autre exigence.

## Vocabulaire normatif

Les interfaces, la documentation et les nouvelles données doivent employer les
termes suivants :

| Terme | Définition |
|---|---|
| workflow | Processus complet décrit par un document JSON. |
| état | Situation stable du workflow. |
| texte de l'état | Contenu unique d'un état. Il remplace les expressions « description de l'état » et « texte associé ». |
| format du texte | Mode de saisie du texte de l'état : Markdown, HTML ou texte brut. |
| lien de l'état | Lien structuré facultatif porté par un état. |
| lien de transition | Lien structuré facultatif porté par une transition. |
| destination du lien | URL ou page visée par un lien. Le mot « cible » reste réservé aux noms de champs JSON historiques. |
| transition | Passage autorisé d'un état source à un état cible. |
| couloir | Couloir Mermaid `swimlane-beta` construit depuis une ligne d'eau. |
| ligne d'eau | Donnée métier `Ligne_eau` qui porte le libellé et l'ordre d'un couloir. |
| répertoire des états | Page `etats.html` regroupant les états d'un workflow. |
| répertoire des transitions | Page `transitions.html` regroupant les transitions d'un workflow. |
| page individuelle d'état | Ancienne page `states/<identifiant>.html`, désormais supprimée. |

Le champ JSON historique `Etat.description` reste accepté pour lire les
anciens documents. `Etat.contenu` et `Etat.type_contenu` constituent la forme
canonique. Lorsqu'un état est enregistré dans l'éditeur, son texte est écrit
dans ces champs et l'ancien champ `description` est retiré de cet état.

## REQ-DATA-001 — Compatibilité modèle-données

Le système doit valider les fichiers complets et les manifestes fragmentés
contre `schema/workflow-model.json`. Le contrôle couvre les tables, champs,
types, valeurs de choix, identifiants, références et cohérence des workflows.

## REQ-MERMAID-001 — Génération Mermaid

Le système doit produire un diagramme de processus Mermaid et un
`stateDiagram-v2` à partir du schéma ou d'un jeu de données validé. Pour un
workflow doté de lignes d'eau, le diagramme de processus doit utiliser la
syntaxe Mermaid native `swimlane-beta` : chaque ligne d'eau devient un couloir
de premier niveau. Pour une vue structurelle de schéma, le diagramme de
processus reste un `flowchart`. Les transitions inactives sont exclues et les
identifiants incompatibles avec Mermaid sont rejetés.

## REQ-HTML-001 — Page HTML documentaire

Le système doit produire une page HTML autonome contenant le diagramme de
processus Mermaid puis, en dessous, les textes des états dans leur ordre métier.
Le diagramme `stateDiagram-v2` n'est pas affiché dans les sorties HTML. Le code
Mermaid source doit rester consultable dans un volet repliable sous le schéma.

## REQ-SITE-001 — Site statique navigable

Le système doit produire un site statique contenant une vue générale, les
phases principales, les pages de phase, le répertoire des états et le répertoire
des transitions. Tous les liens internes générés doivent cibler un fichier
existant. Le moteur Mermaid et sa licence doivent être embarqués dans le site :
le rendu ne doit effectuer aucun accès réseau par défaut. Son chargement comme
script JavaScript classique doit fonctionner en HTTP comme lors de l'ouverture
directe des fichiers HTML en `file://`, notamment dans Firefox.

La page `index.html` regroupe la présentation générale et le diagramme des
phases. Une page `etats.html` présente tous les états et leur texte. Une page
`transitions.html` présente toutes les transitions, leurs états source et cible,
leur lien éventuel et la validité de sa destination. Les deux répertoires sont
accessibles depuis la navigation principale. Le
générateur ne doit créer aucune page individuelle `states/*.html` et doit
supprimer celles laissées par une génération antérieure.

Les pages qui affichent une navigation latérale doivent proposer un mécanisme
accessible permettant de la masquer et de la réafficher. Le choix de
l'utilisateur doit être conservé entre les pages lorsque le navigateur permet
l'utilisation de `localStorage`.

Le site doit proposer une page de paramètres d'affichage avec un mode clair,
un mode sombre et un mode suivant le système. Plusieurs paires clair/sombre
doivent être sélectionnables et le choix doit être conservé localement. Le
portail commun et chaque workflow doivent disposer d'une configuration initiale
et de préférences persistantes indépendantes. Une bascule accessible dans
l'en-tête doit appliquer dynamiquement le mode clair ou sombre, sans régénération
du site. Ces thèmes ne doivent ajouter aucune dépendance réseau.

## REQ-LINK-001 — Navigation portée par les données

Les tables `Etat` et `Transition` doivent pouvoir définir un lien typé vers une
page de phase ou une URL HTTP(S). Le workflow directeur doit
relier chaque phase à sa page détaillée. Dans un diagramme de phase, l'état
terminal doit pointer vers la page de la phase suivante.

La valeur historique `page_etat` reste lisible dans les données, mais aucune
page individuelle d'état n'est générée. L'éditeur doit donc la signaler comme
une destination invalide sans empêcher l'export JSON.

Les répertoires des états et des transitions doivent afficher, pour chaque
élément, son lien structuré et un statut `Valide`, `Invalide` ou `Aucun lien`.
Une destination interne absente doit être signalée comme invalide et ne doit
pas être rendue cliquable. Le workflow « Projet informatique » fournit des
exemples artificiels valides et invalides visibles dans ces deux répertoires.

## REQ-CATALOG-001 — Choix entre plusieurs workflows

Le générateur de site doit accepter un catalogue référençant plusieurs
manifestes. La page d'accueil du catalogue présente chaque workflow et permet
de l'ouvrir. Chaque sous-site doit proposer un lien de retour vers le choix des
workflows.

## REQ-EDITOR-001 — Édition et export JSON d'un workflow

Le site produit depuis un catalogue doit proposer un éditeur permettant de
choisir un workflow, d'ajouter, modifier et supprimer ses états et transitions,
puis de copier ou télécharger le document JSON fusionné.

Un lien depuis chaque workflow doit ouvrir l'éditeur avec ce workflow
présélectionné. L'éditeur doit réciproquement proposer un lien vers la version
publiée du workflow actuellement sélectionné.

L'éditeur doit fonctionner intégralement dans le navigateur, sans serveur. Il
doit contrôler la syntaxe JSON, les identifiants, les doublons et les
références entre workflows, états, transitions, rôles, règles et lignes d'eau.
Le formulaire d'état doit permettre de saisir son texte au format
Markdown, HTML ou texte brut, avec Markdown proposé par défaut. L'interface
doit utiliser le libellé « texte de l'état » et ne doit pas proposer un second
champ « description ».

Le formulaire d'état ne doit pas afficher un tableau exhaustif. Son champ
« identifiant » doit être une liste déroulante dont chaque option affiche
d'abord le nom de l'état, puis son identifiant. L'option « Nouvel état… » doit
afficher un champ de saisie pour le nouvel identifiant. La sélection d'un état
existant doit charger ses attributs dans le formulaire et afficher une action
explicite « Supprimer l’état ». L'inventaire exhaustif reste disponible dans
la page distincte `etats.html`, accessible depuis l'éditeur.

Le formulaire de transition ne doit pas afficher un tableau exhaustif. Son
champ « identifiant » doit être une liste déroulante dont chaque option affiche
d'abord le libellé de la transition, puis son identifiant. L'option « Nouvelle
transition… » doit afficher un champ de saisie pour le nouvel identifiant. La
sélection d'une transition existante doit charger ses attributs dans le
formulaire et afficher une action explicite « Supprimer la transition ».
Il doit également permettre de saisir le type, la destination et le libellé du
lien structuré de la transition.

L'éditeur doit proposer un bouton permettant de placer le formulaire des
transitions soit à droite du formulaire des états, soit en dessous. La
disposition choisie doit être conservée dans `localStorage` lorsque le
navigateur l'autorise. Sur un écran étroit, les formulaires restent empilés
pour préserver leur lisibilité.

L'éditeur doit présenter la validité des liens structurés portés par les états
et les transitions, ainsi que des liens HTML ou Markdown présents dans leur
texte. Le contrôle porte sur
le format, le protocole autorisé et les
références internes ; il ne garantit pas la disponibilité d'une URL distante.
Les états et transitions qui contiennent au moins une destination invalide
doivent être regroupés dans un signalement explicite et mis en évidence dans le
rapport de validité de l'éditeur.

Une destination invalide constitue un avertissement et non une erreur de
structure : elle ne doit bloquer ni l'application du JSON, ni sa copie, ni son
téléchargement. Seules les erreurs de syntaxe JSON, de structure, d'identifiant
ou de référence métier bloquante peuvent désactiver l'export.
Le JSON brut doit permettre de modifier les tables qui ne disposent pas d'un
formulaire dédié.

## REQ-SEC-001 — Filtrage du HTML métier

Le HTML provenant des données doit être filtré avant publication. Les scripts,
attributs événementiels et URL dangereuses doivent être supprimés, tandis que
les contenus non HTML doivent être échappés.

## REQ-TRACE-001 — Traçabilité automatisée

Chaque exigence doit être reliée à au moins un symbole de code, un test
unitaire et un test fonctionnel. Le contrôle de traçabilité doit échouer si un
document, symbole ou test référencé n'existe plus.

## REQ-TUI-001 — Console d’exploitation

Le projet doit proposer une interface terminal dédiée aux opérations courantes.
Elle doit permettre de parcourir le catalogue et les fichiers de paramétrage,
prévisualiser et ouvrir les sources JSON, Mermaid et documentaires, choisir une
palette visuelle persistante propre à la TUI, configurer séparément le thème du
portail web et celui de chaque workflow, créer un workflow initial compatible avec le
schéma, valider un workflow, générer ses diagrammes Mermaid et générer le site
complet. Les opérations longues ne doivent pas bloquer la navigation et leur
résultat doit être présenté dans un journal lisible.

La génération doit distinguer explicitement un fichier Mermaid unique du site
complet contenant l'accueil commun et tous les workflows. Après réussite, elle
doit indiquer le nombre de pages produites, le point d'entrée et proposer son
ouverture. La création d'un workflow ne doit avoir aucun raccourci global à une
seule lettre.

La création d'un workflow ne doit jamais remplacer un répertoire ou une entrée
existante. Le squelette produit doit comporter toutes les tables du modèle, des
identifiants compatibles avec Mermaid, deux états et une transition. Les modes
non interactifs `--list` et `--generate` doivent rester utilisables sans la
dépendance graphique optionnelle.
