import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import tui_core
import workflow_tui


@unittest.skipUnless(importlib.util.find_spec("textual"), "Textual non installé")
class WorkflowTuiTests(unittest.TestCase):
    def test_global_shortcuts_generate_but_do_not_create(self):
        app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
        keys = {binding.key for binding in app.BINDINGS}

        self.assertNotIn("n", keys)
        self.assertIn("g", keys)

    def test_tui_and_web_theme_views_are_distinct(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            async with app.run_test(size=(160, 40)):
                await app.show_view("webthemes")
                self.assertIsNotNone(app.query_one("#web-theme-target"))
                self.assertIn(
                    "pages HTML générées",
                    str(app.query_one("#web-theme-description").render()),
                )

                await app.show_view("settings")
                self.assertIsNotNone(app.query_one("#theme-select"))
                self.assertIn(
                    "ne modifie aucun site web",
                    str(app.query_one("#tui-theme-description").render()),
                )

        asyncio.run(scenario())

    def test_mermaid_action_waits_until_generation_view_is_mounted(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            result = tui_core.CommandResult(("test",), 0, "Diagramme généré")
            with mock.patch.object(workflow_tui, "generate_mermaid", return_value=result):
                async with app.run_test(size=(140, 36)) as pilot:
                    await app.show_view("workflows")
                    selected = app.selected_workflow()
                    self.assertIsNotNone(selected)

                    await app.mermaid_button()
                    await pilot.pause()
                    await pilot.pause()

                    self.assertEqual("generate", app.current_view)
                    self.assertEqual(
                        selected.slug,
                        app.query_one("#operation-workflow").value,
                    )

        asyncio.run(scenario())

    def test_complete_site_success_is_explicit_and_openable(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            artifact = PROJECT_ROOT / "build" / "site-workflows" / "index.html"
            result = tui_core.CommandResult(
                ("test",),
                0,
                "Site complet généré: 3 workflows, 30 pages HTML, 47 fichiers.\n"
                f"Point d’entrée commun: {artifact}",
                artifact,
            )
            with mock.patch.object(workflow_tui, "generate_site", return_value=result):
                async with app.run_test(size=(160, 40)) as pilot:
                    await app.show_view("generate")

                    app.run_site_generation(None)
                    await pilot.pause()
                    await pilot.pause()

                    summary = str(app.query_one("#generation-summary").render())
                    self.assertIn("TOUS LES SITES ONT ÉTÉ GÉNÉRÉS", summary)
                    self.assertIn("30 pages HTML", summary)
                    self.assertTrue(app.query_one("#open-output").has_class("visible"))
                    self.assertEqual(artifact, app.last_artifact)

        asyncio.run(scenario())

    def test_generation_scope_follows_visible_workflow_selection(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            artifact = PROJECT_ROOT / "build" / "site-workflows" / "documentation" / "index.html"
            result = tui_core.CommandResult(
                ("test",),
                0,
                "Site du workflow généré: 8 pages HTML et 12 fichiers écrits.\n"
                f"Point d’entrée du workflow: {artifact}",
                artifact,
            )
            with mock.patch.object(
                workflow_tui, "generate_workflow_site", return_value=result
            ) as generate_one:
                async with app.run_test(size=(170, 42)) as pilot:
                    await app.show_view("workflows")
                    selected = app.selected_workflow()
                    self.assertIsNotNone(selected)

                    await pilot.press("g")
                    await pilot.pause()
                    await pilot.pause()

                    generate_one.assert_called_once_with(
                        selected, tui_core.DEFAULT_BUILD / selected.slug
                    )
                    self.assertEqual("generate", app.current_view)
                    self.assertEqual(
                        selected.slug, app.query_one("#operation-workflow").value
                    )
                    summary = str(app.query_one("#generation-summary").render())
                    self.assertIn("LE SITE DU WORKFLOW", summary)
                    self.assertNotIn("TOUS LES SITES", summary)

        asyncio.run(scenario())

    def test_theme_generation_saves_pending_choice_and_targets_workflow(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            artifact = tui_core.DEFAULT_BUILD / "documentation" / "index.html"
            result = tui_core.CommandResult(
                ("test",),
                0,
                "Site du workflow généré: 8 pages HTML et 12 fichiers écrits.\n"
                f"Point d’entrée du workflow: {artifact}",
                artifact,
            )
            with (
                mock.patch.object(workflow_tui, "save_site_theme") as save_theme,
                mock.patch.object(
                    workflow_tui, "generate_workflow_site", return_value=result
                ) as generate_one,
            ):
                async with app.run_test(size=(180, 44)) as pilot:
                    entry = app.entries[0]
                    save_theme.return_value = tui_core.SiteThemeTarget(
                        entry.slug,
                        entry.label,
                        "aubergine",
                        "dark",
                        entry.manifest,
                    )
                    await app.show_view("webthemes")
                    app.query_one("#web-theme-target").value = entry.slug
                    await pilot.pause()
                    app.query_one("#web-theme-pair").value = "aubergine"
                    app.query_one("#web-theme-mode").value = "dark"

                    await app.web_theme_generate_button()
                    await pilot.pause()
                    await pilot.pause()

                    save_theme.assert_called_once_with(
                        entry.slug,
                        "aubergine",
                        "dark",
                        catalog_path=app.catalog,
                    )
                    generate_one.assert_called_once_with(
                        entry, tui_core.DEFAULT_BUILD / entry.slug
                    )
                    self.assertEqual("generate", app.current_view)

        asyncio.run(scenario())

    def test_workflow_selection_and_two_explicit_editor_actions(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            merged = tui_core.DEFAULT_BUILD / "sources" / "documentation.json"
            with (
                mock.patch.object(workflow_tui, "open_in_editor") as open_editor,
                mock.patch.object(
                    workflow_tui,
                    "export_workflow_document",
                    return_value=merged,
                ) as export_document,
            ):
                async with app.run_test(size=(180, 44)) as pilot:
                    await app.show_view("workflows")
                    entry = app.selected_workflow()
                    self.assertIsNotNone(entry)
                    app.query_one("#workflow-table").focus()
                    await pilot.press("enter")
                    await pilot.pause()
                    open_editor.assert_not_called()

                    app.open_workflow_button()
                    open_editor.assert_called_once_with(
                        entry.manifest, tui_core.load_settings()["editor"]
                    )

                    open_editor.reset_mock()
                    app.open_workflow_document_button()
                    export_document.assert_called_once_with(entry)
                    open_editor.assert_called_once_with(
                        merged, tui_core.load_settings()["editor"]
                    )

        asyncio.run(scenario())

    def test_editor_override_can_be_saved_and_reset(self):
        async def scenario():
            app = workflow_tui.launch_textual(tui_core.DEFAULT_CATALOG, run=False)
            with mock.patch.object(workflow_tui, "save_editor_setting") as save_editor:
                async with app.run_test(size=(180, 44)):
                    await app.show_view("settings")
                    app.query_one("#editor-command").value = "zed --reuse-window"
                    app.save_editor_button()
                    save_editor.assert_called_with("zed --reuse-window")

                    app.reset_editor_button()
                    save_editor.assert_called_with("")
                    self.assertEqual("", app.query_one("#editor-command").value)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
