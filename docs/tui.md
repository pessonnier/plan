# Console d’exploitation terminal

La commande `scripts/workflow_tui.py` centralise les opérations quotidiennes
sur les workflows. L'interface repose sur Textual, tandis que son moteur
d'opérations utilise uniquement la bibliothèque standard Python.

## Installation et démarrage

Depuis la racine du projet :

```powershell
python -m pip install -r requirements-tui.txt
python scripts/workflow_tui.py
```

La génération historique du site et des pages HTML ne dépend pas de Textual et
continue de fonctionner hors ligne. Une fois la dépendance installée, la console
elle-même n'effectue aucun accès réseau.

## Organisation de l'interface

- **Tableau de bord** : état synthétique du catalogue, des paramétrages et du
  dernier site généré, avec actions directes.
- **Workflows** : une ligne peut être sélectionnée sans ouvrir de fichier. Des
  boutons distincts ouvrent ensuite le manifeste JSON ou une copie assemblée du
  document JSON complet. Cette copie est actualisée dans
  `build/site-workflows/sources/<slug>.json` ; les fragments référencés par le
  manifeste restent les sources durables de la prochaine génération.
- **Paramétrages** : recherche instantanée, aperçu intégré et ouverture dans
  l'application associée des JSON, documents et scripts Mermaid.
- **Génération** : la liste de portée propose soit un workflow, soit « Tous les
  workflows ». Le bouton principal génère alors uniquement le sous-site choisi
  ou l'accueil commun avec tous les sites. L'export Mermaid produit explicitement
  un fichier `.md` pour un workflow. Le bilan indique le nombre de pages et
  propose d'ouvrir directement le résultat.
- **Thèmes des sites** : configure séparément l'accueil commun et chaque site de
  workflow, avec une paire de couleurs et un mode clair, sombre ou système.
- **Thème de la TUI** : personnalise uniquement la console terminal. Ce choix
  est enregistré dans `build/.workflow-tui.json` et ne modifie jamais le HTML.
  La même page permet de définir une commande d'éditeur (`zed`, `code --wait`,
  etc.) ou de revenir à l'application associée au type de fichier par le système.

Les raccourcis `D`, `W`, `F` et `T` ouvrent les principales vues. `G` lance la
génération : depuis **Workflows**, il cible la ligne sélectionnée ; depuis
**Génération**, il respecte la portée affichée ; depuis les autres vues, il
génère tous les sites. La création d'un workflow reste disponible depuis le
menu **Workflows**, sans raccourci global. `Ctrl+R` recharge les données,
`Ctrl+P` ouvre la palette de commandes et `Q` quitte l'application.

L'action **Exporter le diagramme Mermaid (.md)** produit uniquement un document
Markdown contenant le code Mermaid dans `build/mermaid`. Elle sert à réutiliser
le diagramme dans une documentation ou un autre outil compatible et ne génère
aucune page HTML.

Le bouton de publication de la page **Thèmes des sites** enregistre le choix
affiché avant de régénérer. Pour un workflow il ne régénère que son sous-site ;
pour l'accueil commun il régénère le catalogue et tous les sites.
Dans le site statique produit, la bascule clair/sombre de l'en-tête reste
modifiable instantanément, rerend les diagrammes Mermaid avec la palette
correspondante et conserve une préférence isolée pour chaque workflow.

## Création d'un workflow

L'action **Nouveau workflow** demande un nom, un slug et une description. Le
slug accepte les lettres ASCII minuscules, les chiffres et les tirets. La
console crée un dossier sous `data/workflows`, un manifeste, un fichier de
données complet et ajoute l'entrée correspondante au catalogue. Elle refuse
tout slug déjà utilisé et ne remplace jamais un dossier existant.

Le squelette comprend un participant, une ligne d'eau, un état initial, un état
final et une transition. Il peut donc être validé et généré immédiatement avant
d'être enrichi.

## Utilisation sans interface

Deux commandes restent disponibles sans installer Textual :

```powershell
python scripts/workflow_tui.py --list
python scripts/workflow_tui.py --generate --output build/site-workflows
```
