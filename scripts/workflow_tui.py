#!/usr/bin/env python3
"""Launch the graphical terminal console for workflow administration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from tui_core import (
    DEFAULT_BUILD,
    DEFAULT_CATALOG,
    PROJECT_ROOT,
    THEMES,
    CommandResult,
    SiteThemeTarget,
    TuiOperationError,
    WorkflowEntry,
    configuration_files,
    create_workflow,
    export_workflow_document,
    generate_mermaid,
    generate_site,
    generate_workflow_site,
    list_workflows,
    list_site_theme_targets,
    load_settings,
    open_in_editor,
    open_path,
    read_preview,
    save_settings,
    save_editor_setting,
    save_site_theme,
    validate_workflow,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Console d’exploitation des workflows et du site statique."
    )
    parser.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG, help="Catalogue à administrer."
    )
    parser.add_argument(
        "--list", action="store_true", help="Lister les workflows sans lancer la TUI."
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Générer le site sans lancer la TUI.",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_BUILD, help="Sortie de --generate."
    )
    return parser


def run_headless(args: argparse.Namespace) -> int | None:
    if args.list:
        for entry in list_workflows(args.catalog):
            print(f"{entry.slug}\t{entry.label}\t{entry.manifest}")
        return 0
    if args.generate:
        result = generate_site(args.catalog, args.output)
        print(result.output)
        return result.returncode
    return None


def launch_textual(catalog_path: Path, *, run: bool = True) -> int | Any:
    try:
        from textual import on, work
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Container, Horizontal, Vertical, VerticalScroll
        from textual.css.query import NoMatches
        from textual.screen import ModalScreen
        from textual.widgets import (
            Button,
            DataTable,
            Footer,
            Header,
            Input,
            Label,
            ListItem,
            ListView,
            LoadingIndicator,
            RichLog,
            Select,
            Static,
        )
    except ImportError:
        print(
            "Textual est requis pour l’interface graphique. Installez-le avec :\n"
            "  python -m pip install -r requirements-tui.txt\n\n"
            "Les modes --list et --generate restent disponibles sans dépendance.",
            file=sys.stderr,
        )
        return 2

    class FileItem(ListItem):
        def __init__(self, path: Path) -> None:
            super().__init__(Label(str(path.relative_to(PROJECT_ROOT)), markup=False))
            self.path = path

    class CreateWorkflowScreen(ModalScreen[tuple[str, str, str] | None]):
        BINDINGS = [Binding("escape", "cancel", "Annuler")]

        def compose(self) -> ComposeResult:
            with Vertical(id="new-dialog"):
                yield Label("Nouveau workflow", id="dialog-title")
                yield Label(
                    "Un socle valide avec deux états sera ajouté au catalogue.",
                    classes="muted",
                )
                yield Label("Nom affiché")
                yield Input(placeholder="Ex. Gestion des incidents", id="new-label")
                yield Label("Slug")
                yield Input(placeholder="gestion-incidents", id="new-slug")
                yield Label("Description")
                yield Input(placeholder="Finalité du workflow", id="new-description")
                yield Static("", id="dialog-error")
                with Horizontal(classes="dialog-actions"):
                    yield Button("Annuler", id="cancel-new", variant="default")
                    yield Button("Créer", id="confirm-new", variant="primary")

        def on_mount(self) -> None:
            self.query_one("#new-label", Input).focus()

        def action_cancel(self) -> None:
            self.dismiss(None)

        @on(Button.Pressed, "#cancel-new")
        def cancel_button(self) -> None:
            self.dismiss(None)

        @on(Button.Pressed, "#confirm-new")
        def confirm_button(self) -> None:
            label = self.query_one("#new-label", Input).value.strip()
            slug = self.query_one("#new-slug", Input).value.strip()
            description = self.query_one("#new-description", Input).value.strip()
            if not label or not slug:
                self.query_one("#dialog-error", Static).update(
                    "Le nom et le slug sont obligatoires."
                )
                return
            self.dismiss((slug, label, description))

    class WorkflowConsole(App[None]):
        TITLE = "Plan · Console d’exploitation"
        SUB_TITLE = "Workflows, Mermaid et publication"
        ENABLE_COMMAND_PALETTE = True
        CSS = """
        Screen {
            background: $surface;
            color: $text;
        }
        Screen.theme-ocean { background: #071521; color: #e5f2ff; }
        Screen.theme-ocean #sidebar { background: #0d2233; border-right: tall #369ad6; }
        Screen.theme-forest { background: #0a1710; color: #e1f3e7; }
        Screen.theme-forest #sidebar { background: #11281b; border-right: tall #4da66b; }
        Screen.theme-aubergine { background: #1c1023; color: #f3e8ff; }
        Screen.theme-aubergine #sidebar { background: #301b3b; border-right: tall #a970c2; }
        Screen.theme-graphite { background: #18191a; color: #f1f3f4; }
        Screen.theme-graphite #sidebar { background: #292a2d; border-right: tall #9aa0a6; }
        Header { background: $primary-background; color: $text; }
        Footer { background: $panel; }
        #body { height: 1fr; }
        #sidebar {
            width: 27;
            min-width: 23;
            background: $panel;
            border-right: tall $primary;
            padding: 1;
        }
        #brand { height: 3; text-style: bold; color: $accent; content-align: center middle; }
        #nav { height: 1fr; background: transparent; }
        #nav ListItem { padding: 0 1; height: 3; }
        #nav ListItem.--highlight { background: $primary 25%; }
        #workspace { width: 1fr; height: 1fr; padding: 1 2; }
        .view-title { text-style: bold; color: $accent; height: 2; }
        .eyebrow { color: $text-muted; }
        .muted { color: $text-muted; }
        .cards { height: auto; margin-top: 1; }
        .card {
            width: 1fr;
            height: 9;
            min-width: 23;
            margin-right: 1;
            padding: 1 2;
            background: $panel;
            border: round $primary 45%;
        }
        .metric { text-style: bold; color: $accent; }
        .quick-actions { height: auto; margin-top: 1; }
        Button { margin-right: 1; min-width: 18; }
        .toolbar { height: 3; margin-bottom: 1; }
        .toolbar Input { width: 1fr; }
        DataTable { height: 1fr; background: $surface; }
        #file-layout { height: 1fr; }
        #file-list { width: 42%; min-width: 30; border: round $primary 45%; }
        #preview-panel { width: 1fr; margin-left: 1; border: round $primary 45%; }
        #preview-path { height: 2; color: $accent; padding: 0 1; }
        #preview { padding: 1; }
        #operations { height: auto; margin-bottom: 1; }
        #operations Select { width: 40; margin-right: 1; }
        #busy { height: 3; display: none; }
        #busy.visible { display: block; }
        #log { height: 1fr; border: round $primary 45%; background: $panel; }
        .settings-row { height: auto; margin-top: 1; }
        .settings-row Label { width: 25; content-align: left middle; }
        .settings-row Select { width: 35; }
        #theme-swatch { height: 8; margin-top: 2; padding: 1 2; border: round $accent; }
        #generation-summary { height: auto; min-height: 4; margin-bottom: 1;
            padding: 1 2; border: round $primary 45%; background: $panel; }
        #open-output { display: none; }
        #open-output.visible { display: block; }
        #new-dialog {
            width: 62;
            height: auto;
            padding: 1 2;
            background: $panel;
            border: thick $accent;
        }
        CreateWorkflowScreen { align: center middle; background: $background 65%; }
        #dialog-title { text-style: bold; color: $accent; height: 2; }
        #new-dialog Input { margin-bottom: 1; }
        #dialog-error { color: $error; min-height: 1; }
        .dialog-actions { height: 3; align-horizontal: right; margin-top: 1; }
        .ocean { background: #0b1727; color: #e5f2ff; }
        .forest { background: #0e2118; color: #e1f3e7; }
        .aubergine { background: #281532; color: #f3e8ff; }
        .graphite { background: #202124; color: #f1f3f4; }
        """
        BINDINGS = [
            Binding("d", "show('dashboard')", "Accueil", show=False),
            Binding("w", "show('workflows')", "Workflows", show=False),
            Binding("f", "show('files')", "Fichiers", show=False),
            Binding("t", "show('settings')", "Thème TUI", show=False),
            Binding("g", "generate_selected", "Générer"),
            Binding("ctrl+r", "refresh", "Actualiser"),
            Binding("q", "quit", "Quitter"),
        ]
        NAVIGATION = [
            ("dashboard", "▦  Tableau de bord"),
            ("workflows", "◆  Workflows"),
            ("files", "≡  Paramétrages"),
            ("generate", "▶  Génération"),
            ("webthemes", "◑  Thèmes des sites"),
            ("settings", "◐  Préférences de la TUI"),
            ("help", "?  Raccourcis"),
        ]
        ALL_WORKFLOWS = "__all__"

        def __init__(self, catalog: Path) -> None:
            super().__init__()
            self.catalog = catalog.resolve()
            self.entries: list[WorkflowEntry] = []
            self.files: list[Path] = []
            self.site_theme_targets: list[SiteThemeTarget] = []
            self.current_view = "dashboard"
            self.last_artifact: Path | None = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="body"):
                with Vertical(id="sidebar"):
                    yield Static("◈  PLAN OPS", id="brand")
                    yield ListView(
                        *(ListItem(Label(label), id=f"nav-{key}") for key, label in self.NAVIGATION),
                        id="nav",
                    )
                    yield Static("G  générer\nCtrl+R  actualiser\nQ  quitter", classes="muted")
                yield Container(id="workspace")
            yield Footer()

        async def on_mount(self) -> None:
            self.refresh_data()
            self.apply_console_theme(load_settings()["theme"])
            await self.show_view("dashboard")

        def refresh_data(self) -> None:
            try:
                self.entries = list_workflows(self.catalog)
                self.files = configuration_files()
                self.site_theme_targets = list_site_theme_targets(self.catalog)
            except TuiOperationError as error:
                self.notify(str(error), severity="error", timeout=6)

        async def action_show(self, view: str) -> None:
            await self.show_view(view)

        async def action_refresh(self) -> None:
            self.refresh_data()
            await self.show_view(self.current_view)
            self.notify("Données actualisées")

        def action_new_workflow(self) -> None:
            self.push_screen(CreateWorkflowScreen(), self.finish_create)

        async def show_view(self, view: str) -> None:
            self.current_view = view
            workspace = self.query_one("#workspace", Container)
            builders = {
                "dashboard": self.dashboard_view,
                "workflows": self.workflows_view,
                "files": self.files_view,
                "generate": self.generate_view,
                "webthemes": self.webthemes_view,
                "settings": self.settings_view,
                "help": self.help_view,
            }
            await workspace.remove_children()
            await workspace.mount(builders.get(view, self.dashboard_view)())

        def dashboard_view(self) -> Vertical:
            container = Vertical()
            container.compose_add_child(Static("CENTRE DE CONTRÔLE", classes="eyebrow"))
            container.compose_add_child(Static("Vue d’exploitation", classes="view-title"))
            with_cards = Horizontal(classes="cards")
            with_cards.compose_add_child(
                Static(
                    f"[b]Workflows[/b]\n\n[bold #5cc8ff]{len(self.entries)}[/]\n\nconfigurations publiables",
                    classes="card",
                )
            )
            with_cards.compose_add_child(
                Static(
                    f"[b]Paramétrages[/b]\n\n[bold #7ee787]{len(self.files)}[/]\n\nJSON, Mermaid et documentation",
                    classes="card",
                )
            )
            site_ready = (DEFAULT_BUILD / "index.html").is_file()
            with_cards.compose_add_child(
                Static(
                    f"[b]Site statique[/b]\n\n[bold #d2a8ff]{'PRÊT' if site_ready else 'À GÉNÉRER'}[/]\n\n{DEFAULT_BUILD.relative_to(PROJECT_ROOT)}",
                    classes="card",
                )
            )
            container.compose_add_child(with_cards)
            actions = Horizontal(classes="quick-actions")
            actions.compose_add_child(Button("▶ Générer tous les sites", id="quick-generate", variant="primary"))
            actions.compose_add_child(Button("≡ Parcourir les fichiers", id="quick-files"))
            container.compose_add_child(actions)
            container.compose_add_child(
                Static(
                    "\nAstuce · Ctrl+P ouvre la palette de commandes. Le menu Génération distingue clairement un fichier Mermaid du site complet.",
                    classes="muted",
                )
            )
            return container

        def workflows_view(self) -> Vertical:
            table = DataTable(id="workflow-table", cursor_type="row", zebra_stripes=True)
            table.add_columns("Workflow", "Slug", "Description", "Manifeste")
            for entry in self.entries:
                table.add_row(
                    entry.label,
                    entry.slug,
                    entry.description,
                    str(entry.manifest.relative_to(PROJECT_ROOT)),
                    key=entry.slug,
                )
            return Vertical(
                Static("CATALOGUE", classes="eyebrow"),
                Static("Workflows", classes="view-title"),
                Horizontal(
                    Button("＋ Nouveau", id="workflow-new", variant="primary"),
                    Button("✓ Valider", id="workflow-validate"),
                    Button("⌁ Exporter Mermaid (.md)", id="workflow-mermaid"),
                    Button("▶ Générer ce site", id="workflow-site", variant="primary"),
                    Button("✎ Manifeste JSON", id="workflow-open"),
                    Button("✎ Document JSON complet", id="workflow-document"),
                    classes="toolbar",
                ),
                table,
            )

        def files_view(self) -> Vertical:
            file_list = ListView(*(FileItem(path) for path in self.files), id="file-list")
            preview = Static("Sélectionnez un fichier pour afficher son contenu.", id="preview", markup=False)
            return Vertical(
                Static("SOURCES", classes="eyebrow"),
                Static("Fichiers de paramétrage et Mermaid", classes="view-title"),
                Horizontal(
                    Input(placeholder="Filtrer par nom ou chemin…", id="file-filter"),
                    Button("↗ Ouvrir", id="file-open"),
                    classes="toolbar",
                ),
                Horizontal(
                    file_list,
                    VerticalScroll(Static("Aperçu", id="preview-path"), preview, id="preview-panel"),
                    id="file-layout",
                ),
            )

        def generate_view(self) -> Vertical:
            options = [("Tous les workflows · site complet", self.ALL_WORKFLOWS)]
            options.extend((entry.label, entry.slug) for entry in self.entries)
            select = Select(
                options,
                value=self.ALL_WORKFLOWS,
                id="operation-workflow",
                prompt="Choisir la portée de génération",
            )
            return Vertical(
                Static("PUBLICATION", classes="eyebrow"),
                Static("Validation et génération", classes="view-title"),
                Horizontal(
                    select,
                    Button("✓ Valider", id="operation-validate", disabled=True),
                    Button(
                        "⌁ Exporter le diagramme Mermaid (.md)",
                        id="operation-mermaid",
                        disabled=True,
                    ),
                    Button("▶ Générer tous les sites", id="operation-site", variant="primary"),
                    id="operations",
                ),
                Static(
                    "PORTÉE · TOUS LES WORKFLOWS\n"
                    "La génération produit l’accueil commun et tous les sous-sites de workflows. "
                    "L’export Mermaid est disponible après sélection d’un seul workflow.",
                    id="generation-summary",
                ),
                Button("↗ Ouvrir le résultat", id="open-output"),
                LoadingIndicator(id="busy"),
                RichLog(id="log", highlight=True, markup=True, wrap=True),
            )

        def webthemes_view(self) -> Vertical:
            target_options = [
                (target.label, target.target_id) for target in self.site_theme_targets
            ]
            selected = self.site_theme_targets[0] if self.site_theme_targets else None
            return Vertical(
                Static("SITES WEB STATIQUES", classes="eyebrow"),
                Static("Thèmes indépendants par site", classes="view-title"),
                Static(
                    "Ces réglages concernent les pages HTML générées, pas la console TUI. "
                    "L’accueil commun et chaque workflow conservent leur propre palette.",
                    id="web-theme-description",
                    classes="muted",
                ),
                Horizontal(
                    Label("Site à configurer"),
                    Select(
                        target_options,
                        value=selected.target_id if selected else Select.BLANK,
                        id="web-theme-target",
                    ),
                    classes="settings-row",
                ),
                Horizontal(
                    Label("Paire clair / sombre"),
                    Select(
                        [(name.capitalize(), name) for name in THEMES],
                        value=selected.pair if selected else "ocean",
                        id="web-theme-pair",
                    ),
                    classes="settings-row",
                ),
                Horizontal(
                    Label("Mode initial"),
                    Select(
                        [("Selon le système", "system"), ("Clair", "light"), ("Sombre", "dark")],
                        value=selected.mode if selected else "system",
                        id="web-theme-mode",
                    ),
                    classes="settings-row",
                ),
                Horizontal(
                    Button("Enregistrer pour ce site", id="save-web-theme", variant="primary"),
                    Button(
                        "▶ Enregistrer et régénérer tous les sites",
                        id="web-theme-generate",
                    ),
                    classes="quick-actions",
                ),
                Static(
                    "Après génération, chaque page propose aussi une bascule Clair / Sombre "
                    "dans son en-tête. Elle agit immédiatement et reste locale au site concerné.",
                    id="web-theme-status",
                    classes="muted",
                ),
            )

        def settings_view(self) -> Vertical:
            settings = load_settings()
            current = settings["theme"]
            theme_select = Select(
                [(name.capitalize(), name) for name in THEMES],
                value=current,
                id="theme-select",
            )
            return Vertical(
                Static("CONSOLE TUI UNIQUEMENT", classes="eyebrow"),
                Static("Préférences de la console", classes="view-title"),
                Static(
                    "Ce choix ne modifie aucun site web généré.",
                    id="tui-theme-description",
                    classes="muted",
                ),
                Horizontal(Label("Palette de la TUI"), theme_select, classes="settings-row"),
                Static(
                    "Aperçu de la palette\n\n◆ Action principale   ✓ Succès   ! Avertissement\n\nLe choix est conservé dans build/.workflow-tui.json.",
                    id="theme-swatch",
                    classes=current,
                ),
                Static(
                    "\nPour les pages HTML, utilisez le menu distinct « Thèmes des sites ».",
                    classes="muted",
                ),
                Static("ÉDITEUR DE FICHIERS", classes="eyebrow"),
                Static(
                    "Sans commande personnalisée, la TUI utilise l’application associée "
                    "au type de fichier par le système — par exemple Zed pour vos JSON.",
                    classes="muted",
                ),
                Horizontal(
                    Label("Commande de l’éditeur"),
                    Input(
                        value=settings["editor"],
                        placeholder="Ex. zed, code --wait — vide = application associée",
                        id="editor-command",
                    ),
                    classes="settings-row",
                ),
                Horizontal(
                    Button("Enregistrer l’éditeur", id="save-editor", variant="primary"),
                    Button(
                        "Réinitialiser vers l’application associée",
                        id="reset-editor",
                    ),
                    classes="quick-actions",
                ),
                Static(
                    "Éditeur actuel : "
                    + (settings["editor"] or "application associée du système"),
                    id="editor-status",
                    classes="muted",
                ),
            )

        def help_view(self) -> Vertical:
            return Vertical(
                Static("AIDE", classes="eyebrow"),
                Static("Navigation rapide", classes="view-title"),
                Static(
                    "[b]D / W / F / T[/]      Accueil, workflows, fichiers, thème TUI\n"
                    "[b]G[/]                  Générer le workflow sélectionné, ou tous les sites\n"
                    "[b]Ctrl+R[/]             Recharger le catalogue\n"
                    "[b]Ctrl+P[/]             Palette de commandes\n"
                    "[b]Entrée[/]             Activer ou ouvrir la sélection\n"
                    "[b]Q[/]                  Quitter\n\n"
                    "« Exporter Mermaid (.md) » produit uniquement le code du diagramme, "
                    "utile dans une documentation ou un outil compatible Mermaid ; cette "
                    "action ne génère aucune page HTML.\n\n"
                    "La console orchestre les scripts Python existants. Les sorties détaillées "
                    "restent visibles dans le journal de génération.",
                    classes="card",
                ),
            )

        @on(ListView.Selected, "#nav")
        async def navigation_selected(self, event: ListView.Selected) -> None:
            if event.item.id and event.item.id.startswith("nav-"):
                await self.show_view(event.item.id[4:])

        @on(Button.Pressed, "#quick-generate")
        async def quick_generate(self) -> None:
            await self.show_view("generate")
            self.query_one("#operation-workflow", Select).value = self.ALL_WORKFLOWS
            self.run_site_generation(None)

        @on(Button.Pressed, "#workflow-new")
        def new_button(self) -> None:
            self.action_new_workflow()

        @on(Button.Pressed, "#quick-files")
        async def quick_files(self) -> None:
            await self.show_view("files")

        def selected_workflow(self) -> WorkflowEntry | None:
            if self.current_view == "workflows":
                table = self.query_one("#workflow-table", DataTable)
                if table.row_count:
                    row = table.get_row_at(table.cursor_row)
                    slug = str(row[1])
                    return next((item for item in self.entries if item.slug == slug), None)
            elif self.current_view == "generate":
                select = self.query_one("#operation-workflow", Select)
                return next((item for item in self.entries if item.slug == select.value), None)
            return None

        async def action_generate_selected(self) -> None:
            """Generate according to the selection visible when G is pressed."""
            entry = self.selected_workflow()
            if self.current_view != "generate":
                await self.show_view("generate")
                self.query_one("#operation-workflow", Select).value = (
                    entry.slug if entry else self.ALL_WORKFLOWS
                )
            self.run_site_generation(entry)

        @on(Button.Pressed, "#workflow-open")
        def open_workflow_button(self) -> None:
            self.open_selected_workflow()

        def open_selected_workflow(self) -> None:
            entry = self.selected_workflow()
            if entry:
                try:
                    open_in_editor(entry.manifest, load_settings()["editor"])
                    self.notify(f"Édition de {entry.manifest.name}")
                except TuiOperationError as error:
                    self.notify(str(error), severity="error")

        @on(Button.Pressed, "#workflow-document")
        def open_workflow_document_button(self) -> None:
            entry = self.selected_workflow()
            if not entry:
                return
            try:
                document = export_workflow_document(entry)
                open_in_editor(document, load_settings()["editor"])
                self.notify(
                    f"Document complet assemblé puis ouvert : {document.name}"
                )
            except TuiOperationError as error:
                self.notify(str(error), severity="error")

        @on(Button.Pressed, "#workflow-site")
        async def workflow_site_button(self) -> None:
            entry = self.selected_workflow()
            if entry:
                await self.show_view("generate")
                self.query_one("#operation-workflow", Select).value = entry.slug
                self.run_site_generation(entry)

        @on(Button.Pressed, "#workflow-validate, #operation-validate")
        async def validate_button(self) -> None:
            entry = self.selected_workflow()
            if entry:
                if self.current_view != "generate":
                    await self.show_view("generate")
                self.start_workflow_operation("validate", entry)

        @on(Button.Pressed, "#workflow-mermaid, #operation-mermaid")
        async def mermaid_button(self) -> None:
            entry = self.selected_workflow()
            if entry:
                if self.current_view != "generate":
                    await self.show_view("generate")
                self.start_workflow_operation("mermaid", entry)

        def start_workflow_operation(
            self, operation: str, entry: WorkflowEntry
        ) -> None:
            """Start an operation once the generation view has been mounted."""
            self.query_one("#operation-workflow", Select).value = entry.slug
            self.run_workflow_operation(operation, entry)

        @on(Button.Pressed, "#operation-site")
        def site_button(self) -> None:
            self.run_site_generation(self.selected_workflow())

        @on(Select.Changed, "#operation-workflow")
        def operation_target_changed(self, event: Select.Changed) -> None:
            try:
                site_button = self.query_one("#operation-site", Button)
                validate_button = self.query_one("#operation-validate", Button)
                mermaid_button = self.query_one("#operation-mermaid", Button)
                summary = self.query_one("#generation-summary", Static)
            except NoMatches:
                return
            entry = next((item for item in self.entries if item.slug == event.value), None)
            is_all = entry is None
            validate_button.disabled = is_all
            mermaid_button.disabled = is_all
            site_button.label = (
                "▶ Générer tous les sites" if is_all else "▶ Générer ce workflow"
            )
            summary.update(
                "PORTÉE · TOUS LES WORKFLOWS\n"
                "La génération produit l’accueil commun et tous les sous-sites de workflows."
                if is_all
                else f"PORTÉE · UN WORKFLOW — {entry.label}\n"
                "La génération remplace uniquement le sous-site sélectionné. "
                "L’export Mermaid (.md) produit le code du diagramme sans page HTML."
            )

        @on(Button.Pressed, "#open-output")
        def open_output_button(self) -> None:
            if self.last_artifact:
                try:
                    open_path(self.last_artifact)
                except TuiOperationError as error:
                    self.notify(str(error), severity="error")

        @on(Select.Changed, "#web-theme-target")
        def web_theme_target_changed(self, event: Select.Changed) -> None:
            target = next(
                (item for item in self.site_theme_targets if item.target_id == event.value),
                None,
            )
            if target:
                try:
                    pair_select = self.query_one("#web-theme-pair", Select)
                    mode_select = self.query_one("#web-theme-mode", Select)
                    generate_button = self.query_one("#web-theme-generate", Button)
                except NoMatches:
                    # The target Select emits its initial value while its sibling
                    # controls are still being mounted. They already receive the
                    # same defaults from webthemes_view.
                    return
                pair_select.value = target.pair
                mode_select.value = target.mode
                generate_button.label = (
                    "▶ Enregistrer et régénérer tous les sites"
                    if target.target_id == "catalog"
                    else "▶ Enregistrer et régénérer ce workflow"
                )

        @on(Button.Pressed, "#save-web-theme")
        def save_web_theme_button(self) -> None:
            self.save_current_web_theme()

        def save_current_web_theme(self) -> SiteThemeTarget | None:
            target_id = self.query_one("#web-theme-target", Select).value
            pair = self.query_one("#web-theme-pair", Select).value
            mode = self.query_one("#web-theme-mode", Select).value
            try:
                saved = save_site_theme(
                    str(target_id), str(pair), str(mode), catalog_path=self.catalog
                )
            except TuiOperationError as error:
                self.notify(str(error), severity="error")
                return None
            self.site_theme_targets = list_site_theme_targets(self.catalog)
            self.query_one("#web-theme-status", Static).update(
                f"Thème {saved.pair} / {saved.mode} enregistré pour « {saved.label} ». "
                "Régénérez les sites pour publier ce nouveau réglage initial."
            )
            self.notify(f"Thème web enregistré pour {saved.label}")
            return saved

        @on(Button.Pressed, "#web-theme-generate")
        async def web_theme_generate_button(self) -> None:
            saved = self.save_current_web_theme()
            if saved is None:
                return
            entry = next(
                (item for item in self.entries if item.slug == saved.target_id),
                None,
            )
            await self.show_view("generate")
            self.query_one("#operation-workflow", Select).value = (
                entry.slug if entry else self.ALL_WORKFLOWS
            )
            self.run_site_generation(entry)

        def set_busy(self, busy: bool) -> None:
            indicator = self.query_one("#busy", LoadingIndicator)
            indicator.set_class(busy, "visible")
            for button in self.query("#operations Button"):
                button.disabled = busy
            if not busy:
                is_all = (
                    self.query_one("#operation-workflow", Select).value
                    == self.ALL_WORKFLOWS
                )
                self.query_one("#operation-validate", Button).disabled = is_all
                self.query_one("#operation-mermaid", Button).disabled = is_all

        @work(thread=True, exclusive=True, group="operations")
        def run_workflow_operation(self, operation: str, entry: WorkflowEntry) -> None:
            self.call_from_thread(self.set_busy, True)
            result = validate_workflow(entry) if operation == "validate" else generate_mermaid(entry)
            self.call_from_thread(self.finish_operation, operation, entry.label, result)

        @work(thread=True, exclusive=True, group="operations")
        def run_site_generation(self, entry: WorkflowEntry | None = None) -> None:
            self.call_from_thread(self.set_busy, True)
            if entry:
                result = generate_workflow_site(entry, DEFAULT_BUILD / entry.slug)
                self.call_from_thread(
                    self.finish_operation, "site-one", entry.label, result
                )
            else:
                result = generate_site(self.catalog, DEFAULT_BUILD)
                self.call_from_thread(
                    self.finish_operation, "site-all", "Tous les workflows", result
                )

        def finish_operation(
            self, operation: str, label: str, result: CommandResult
        ) -> None:
            self.set_busy(False)
            log = self.query_one("#log", RichLog)
            status = "[bold green]SUCCÈS[/]" if result.succeeded else "[bold red]ÉCHEC[/]"
            title = {
                "validate": "Validation",
                "mermaid": "Mermaid",
                "site-one": "Site du workflow",
                "site-all": "Tous les sites",
            }[operation]
            log.write(f"\n{status}  [bold]{title} · {label}[/]")
            log.write(result.output or "Opération terminée sans message.")
            self.last_artifact = result.artifact
            open_button = self.query_one("#open-output", Button)
            open_button.set_class(bool(result.succeeded and result.artifact), "visible")
            if result.succeeded and operation in {"site-one", "site-all"}:
                headline = (
                    "✓ TOUS LES SITES ONT ÉTÉ GÉNÉRÉS"
                    if operation == "site-all"
                    else f"✓ LE SITE DU WORKFLOW « {label} » A ÉTÉ GÉNÉRÉ"
                )
                details = "\n".join(result.output.splitlines()[-2:])
                self.query_one("#generation-summary", Static).update(
                    f"{headline}\n{details}"
                )
            elif result.succeeded and operation == "mermaid":
                self.query_one("#generation-summary", Static).update(
                    f"✓ UN FICHIER MERMAID GÉNÉRÉ\n{result.artifact}"
                )
            self.notify(
                f"{title} terminé" if result.succeeded else f"{title} en échec",
                severity="information" if result.succeeded else "error",
            )

        @on(ListView.Highlighted, "#file-list")
        def file_highlighted(self, event: ListView.Highlighted) -> None:
            if isinstance(event.item, FileItem):
                self.query_one("#preview-path", Static).update(
                    str(event.item.path.relative_to(PROJECT_ROOT))
                )
                self.query_one("#preview", Static).update(read_preview(event.item.path))

        @on(ListView.Selected, "#file-list")
        def file_selected(self, event: ListView.Selected) -> None:
            if isinstance(event.item, FileItem):
                self.open_file(event.item.path)

        @on(Button.Pressed, "#file-open")
        def open_file_button(self) -> None:
            file_list = self.query_one("#file-list", ListView)
            if isinstance(file_list.highlighted_child, FileItem):
                self.open_file(file_list.highlighted_child.path)

        def open_file(self, path: Path) -> None:
            try:
                open_in_editor(path, load_settings()["editor"])
                self.notify(f"Ouverture de {path.name}")
            except TuiOperationError as error:
                self.notify(str(error), severity="error")

        @on(Input.Changed, "#file-filter")
        def filter_files(self, event: Input.Changed) -> None:
            query = event.value.casefold().strip()
            file_list = self.query_one("#file-list", ListView)
            file_list.clear()
            filtered = [
                path
                for path in self.files
                if not query or query in str(path.relative_to(PROJECT_ROOT)).casefold()
            ]
            file_list.extend(FileItem(path) for path in filtered)

        @on(Select.Changed, "#theme-select")
        def theme_changed(self, event: Select.Changed) -> None:
            if event.value not in THEMES:
                return
            save_settings(str(event.value))
            self.apply_console_theme(str(event.value))
            swatch = self.query_one("#theme-swatch", Static)
            for theme in THEMES:
                swatch.remove_class(theme)
            swatch.add_class(str(event.value))
            self.notify(f"Thème {str(event.value).capitalize()} enregistré")

        @on(Button.Pressed, "#save-editor")
        def save_editor_button(self) -> None:
            command = self.query_one("#editor-command", Input).value.strip()
            save_editor_setting(command)
            label = command or "application associée du système"
            self.query_one("#editor-status", Static).update(
                f"Éditeur actuel : {label}"
            )
            self.notify("Choix de l’éditeur enregistré")

        @on(Button.Pressed, "#reset-editor")
        def reset_editor_button(self) -> None:
            save_editor_setting("")
            self.query_one("#editor-command", Input).value = ""
            self.query_one("#editor-status", Static).update(
                "Éditeur actuel : application associée du système"
            )
            self.notify("Association système restaurée")

        def apply_console_theme(self, theme: str) -> None:
            for candidate in THEMES:
                self.screen.remove_class(f"theme-{candidate}")
            self.screen.add_class(f"theme-{theme}")

        async def finish_create(self, values: tuple[str, str, str] | None) -> None:
            if values is None:
                return
            try:
                entry = create_workflow(*values, catalog_path=self.catalog)
            except TuiOperationError as error:
                self.notify(str(error), severity="error", timeout=7)
                return
            self.refresh_data()
            await self.show_view("workflows")
            self.notify(f"Workflow « {entry.label} » créé", timeout=5)

    app = WorkflowConsole(catalog_path)
    if not run:
        return app
    app.run()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        headless_result = run_headless(args)
        if headless_result is not None:
            return headless_result
        return launch_textual(args.catalog)
    except TuiOperationError as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
