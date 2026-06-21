# Spécifications fonctionnelles

Chaque exigence possède un identifiant stable utilisé dans la matrice
`traceability/requirements.json`. Ces identifiants ne doivent pas être
réutilisés pour une autre exigence.

## REQ-DATA-001 — Compatibilité modèle-données

Le système doit valider les fichiers complets et les manifestes fragmentés
contre `schema/workflow-model.json`. Le contrôle couvre les tables, champs,
types, valeurs de choix, identifiants, références et cohérence des workflows.

## REQ-MERMAID-001 — Génération Mermaid

Le système doit produire un `flowchart` et un `stateDiagram-v2` à partir du
schéma ou d'un jeu de données validé. Les transitions inactives sont exclues et
les identifiants incompatibles avec Mermaid sont rejetés.

## REQ-HTML-001 — Page HTML documentaire

Le système doit produire une page HTML autonome contenant le `flowchart`
Mermaid puis, en dessous, les descriptions des états dans leur ordre métier.
Le diagramme `stateDiagram-v2` n'est pas affiché dans les sorties HTML.

## REQ-SITE-001 — Site statique navigable

Le système doit produire un site statique contenant une vue générale, les
phases principales, les pages de phase et les pages d'état. Tous les liens
internes générés doivent cibler un fichier existant. Le chargement de Mermaid
doit fonctionner lorsque le site est servi en HTTP et ne doit pas dépendre du
chargement d'un module JavaScript local, afin de rester compatible avec
l'ouverture directe des fichiers HTML.

La page `index.html` regroupe la présentation générale et le diagramme des
phases. Une page `etats.html` présente tous les états détaillés et permet
d'accéder à leur page individuelle.

Les pages qui affichent une navigation latérale doivent proposer un mécanisme
accessible permettant de la masquer et de la réafficher. Le choix de
l'utilisateur doit être conservé entre les pages lorsque le navigateur permet
l'utilisation de `localStorage`.

## REQ-LINK-001 — Navigation portée par les données

Les tables `Etat` et `Transition` doivent pouvoir définir un lien typé vers une
page de phase, une page d'état ou une URL HTTP(S). Le workflow directeur doit
relier chaque phase à sa page détaillée. Dans un diagramme de phase, l'état
terminal doit pointer vers la page de la phase suivante.

## REQ-CATALOG-001 — Choix entre plusieurs workflows

Le générateur de site doit accepter un catalogue référençant plusieurs
manifestes. La page d'accueil du catalogue présente chaque workflow et permet
de l'ouvrir. Chaque sous-site doit proposer un lien de retour vers le choix des
workflows.

## REQ-SEC-001 — Filtrage du HTML métier

Le HTML provenant des données doit être filtré avant publication. Les scripts,
attributs événementiels et URL dangereuses doivent être supprimés, tandis que
les contenus non HTML doivent être échappés.

## REQ-TRACE-001 — Traçabilité automatisée

Chaque exigence doit être reliée à au moins un symbole de code, un test
unitaire et un test fonctionnel. Le contrôle de traçabilité doit échouer si un
document, symbole ou test référencé n'existe plus.
