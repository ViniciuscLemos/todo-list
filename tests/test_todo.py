import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import todo  # noqa: E402

# the program does this in main(); the tests call the functions directly, and on a
# Windows console the warning with an emoji would break with cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class TestRules(unittest.TestCase):
    def setUp(self):
        self.tasks = []

    def test_create_task_fills_fields(self):
        task = todo.create_task(self.tasks, "  Study  ", "high")
        self.assertEqual(task["name"], "Study")
        self.assertEqual(task["priority"], "high")
        self.assertFalse(task["done"])
        self.assertIsNotNone(task["created_at"])
        self.assertEqual(len(self.tasks), 1)

    def test_create_task_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            todo.create_task(self.tasks, "   ")

    def test_create_task_rejects_invalid_priority(self):
        with self.assertRaises(ValueError):
            todo.create_task(self.tasks, "x", "urgent")

    def test_complete_and_reopen(self):
        todo.create_task(self.tasks, "A")
        todo.complete(self.tasks, 1)
        self.assertTrue(self.tasks[0]["done"])
        self.assertIsNotNone(self.tasks[0]["done_at"])
        with self.assertRaises(ValueError):
            todo.complete(self.tasks, 1)

        todo.reopen(self.tasks, 1)
        self.assertFalse(self.tasks[0]["done"])
        self.assertIsNone(self.tasks[0]["done_at"])

    def test_invalid_number(self):
        todo.create_task(self.tasks, "A")
        for number in (0, 2, -1):
            with self.assertRaises(IndexError):
                todo.complete(self.tasks, number)

    def test_edit(self):
        todo.create_task(self.tasks, "A")
        todo.edit(self.tasks, 1, name="B", priority="low")
        self.assertEqual(self.tasks[0]["name"], "B")
        self.assertEqual(self.tasks[0]["priority"], "low")
        # None keeps the current value
        todo.edit(self.tasks, 1)
        self.assertEqual(self.tasks[0]["name"], "B")

    def test_remove(self):
        todo.create_task(self.tasks, "A")
        todo.create_task(self.tasks, "B")
        removed = todo.remove(self.tasks, 1)
        self.assertEqual(removed["name"], "A")
        self.assertEqual([t["name"] for t in self.tasks], ["B"])

    def test_clear_done(self):
        for name in "ABC":
            todo.create_task(self.tasks, name)
        todo.complete(self.tasks, 1)
        todo.complete(self.tasks, 3)
        self.assertEqual(todo.clear_done(self.tasks), 2)
        self.assertEqual([t["name"] for t in self.tasks], ["B"])

    def test_priority_accepts_any_case_and_initial(self):
        self.assertEqual(todo.normalize_priority("Medium"), "medium")
        self.assertEqual(todo.normalize_priority(" HIGH "), "high")
        self.assertEqual(todo.normalize_priority("l"), "low")
        self.assertEqual(todo.normalize_priority(""), "")
        self.assertEqual(todo.normalize_priority("urgent"), "urgent")  # create_task rejects it later

    def test_summary(self):
        todo.create_task(self.tasks, "A")
        todo.create_task(self.tasks, "B")
        todo.complete(self.tasks, 2)
        self.assertEqual(todo.summary(self.tasks), {"total": 2, "done": 1, "pending": 1})


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "tasks.json")

    def tearDown(self):
        self.folder.cleanup()

    def test_save_and_load(self):
        tasks = []
        todo.create_task(tasks, "Read", "high")
        todo.save_tasks(tasks, self.path)
        self.assertEqual(todo.load_tasks(self.path), tasks)

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(todo.load_tasks(self.path), [])

    def test_old_format_gets_filled_in(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([{"name": "Old one", "done": True}], f)
        task = todo.load_tasks(self.path)[0]
        self.assertEqual(task["priority"], "medium")
        self.assertIn("created_at", task)

    def test_corrupted_file_makes_backup(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{this is not json")
        self.assertEqual(todo.load_tasks(self.path), [])
        self.assertTrue(os.path.exists(self.path + ".corrupted"))

    def test_json_in_wrong_shape_also_makes_backup(self):
        for content in ('{"name": "not a list"}', '["loose text"]', '[{"no_name": true}]'):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(content)
            self.assertEqual(todo.load_tasks(self.path), [])
            self.assertTrue(os.path.exists(self.path + ".corrupted"))



class TestCli(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "tasks.json")

    def tearDown(self):
        self.folder.cleanup()

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = todo.cli(list(args), self.path)
        return code, output.getvalue()

    def test_add_done_and_list(self):
        self.assertEqual(self.run_cli("add", "Buy", "bread", "-p", "h")[0], 0)
        self.run_cli("add", "Study SQL")
        self.assertEqual(self.run_cli("done", "1"), (0, "Done: Buy bread\n"))

        tasks = todo.load_tasks(self.path)
        self.assertEqual([t["priority"] for t in tasks], ["high", "medium"])
        self.assertTrue(tasks[0]["done"])

        code, text = self.run_cli("list", "--pending")
        self.assertIn("Study SQL", text)
        self.assertNotIn("Buy bread", text)

    def test_errors_return_1_and_dont_save(self):
        self.run_cli("add", "Only one")
        code, text = self.run_cli("rm", "5")
        self.assertEqual(code, 1)
        self.assertIn("Invalid number", text)
        self.assertEqual(len(todo.load_tasks(self.path)), 1)

    def test_clear(self):
        self.run_cli("add", "A")
        self.run_cli("add", "B")
        self.run_cli("done", "2")
        self.assertEqual(self.run_cli("clear"), (0, "1 done task(s) removed.\n"))
        self.assertEqual([t["name"] for t in todo.load_tasks(self.path)], ["A"])

    def test_list_by_priority(self):
        self.run_cli("add", "Urgent", "-p", "h")
        self.run_cli("add", "Whenever", "-p", "l")
        code, text = self.run_cli("list", "-p", "high")
        self.assertIn("Urgent", text)
        self.assertNotIn("Whenever", text)

    def test_find(self):
        self.run_cli("add", "Buy bread")
        self.run_cli("add", "Study SQL")
        self.run_cli("add", "buy milk")
        self.assertEqual(self.run_cli("find", "BUY"), (0, "1. [ ] Buy bread\n3. [ ] buy milk\n"))
        self.assertEqual(self.run_cli("find", "python"), (0, "Nothing found.\n"))


if __name__ == "__main__":
    unittest.main()
