import argparse
import json
import os
import sys
from datetime import datetime

# saved next to the script; TODO_FILE is there to change the path in tests
FILE = os.environ.get(
    "TODO_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json"),
)

PRIORITIES = ("low", "medium", "high")
PRIORITY_ICONS = {"low": "🟢", "medium": "🟡", "high": "🔴"}
DATE_FORMAT = "%Y-%m-%d %H:%M"



def _normalize(task):
    # tasks from the first version only had name and done
    task.setdefault("done", False)
    task.setdefault("priority", "medium")
    task.setdefault("created_at", None)
    task.setdefault("done_at", None)
    return task


def load_tasks(path=None):
    path = path or FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # valid JSON in the wrong shape (someone edited it by hand, for example) also counts as corrupted
        if not isinstance(data, list) or not all(isinstance(t, dict) and "name" in t for t in data):
            raise ValueError("unexpected format")
        return [_normalize(t) for t in data]
    except (ValueError, OSError):
        # corrupted file: keep a copy and start from scratch
        backup = path + ".corrupted"
        os.replace(path, backup)
        print(f"  ⚠️  Invalid tasks file. A copy was saved to {backup}.")
        return []


def save_tasks(tasks, path=None):
    path = path or FILE
    # write to a temp file and swap, so the file isn't left half written if the program crashes
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    os.replace(temp, path)



def _now():
    return datetime.now().strftime(DATE_FORMAT)


def create_task(tasks, name, priority="medium"):
    name = name.strip()
    if not name:
        raise ValueError("Name can't be empty.")
    if priority not in PRIORITIES:
        raise ValueError("Priority must be: low, medium or high.")
    task = {
        "name": name,
        "done": False,
        "priority": priority,
        "created_at": _now(),
        "done_at": None,
    }
    tasks.append(task)
    return task


def get_task(tasks, number):
    """Takes the number shown to the user (starts at 1)."""
    if not 1 <= number <= len(tasks):
        raise IndexError("Invalid number.")
    return tasks[number - 1]


def complete(tasks, number):
    task = get_task(tasks, number)
    if task["done"]:
        raise ValueError("Task is already done.")
    task["done"] = True
    task["done_at"] = _now()
    return task


def reopen(tasks, number):
    task = get_task(tasks, number)
    if not task["done"]:
        raise ValueError("Task isn't done yet.")
    task["done"] = False
    task["done_at"] = None
    return task


def edit(tasks, number, name=None, priority=None):
    task = get_task(tasks, number)
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("Name can't be empty.")
        task["name"] = name
    if priority is not None:
        if priority not in PRIORITIES:
            raise ValueError("Priority must be: low, medium or high.")
        task["priority"] = priority
    return task


def move(tasks, number, to):
    """Puts the task at position `to`, the others slide to make room."""
    task = get_task(tasks, number)
    get_task(tasks, to)
    tasks.insert(to - 1, tasks.pop(number - 1))
    return task


def remove(tasks, number):
    get_task(tasks, number)  # validates the number
    return tasks.pop(number - 1)


def clear_done(tasks):
    """Removes the done tasks and returns how many were removed."""
    before = len(tasks)
    tasks[:] = [t for t in tasks if not t["done"]]
    return before - len(tasks)


def find(tasks, text):
    """Returns (number, task) for the tasks whose name has the text, ignoring case."""
    text = text.strip().lower()
    if not text:
        raise ValueError("Type something to search for.")
    return [(i, t) for i, t in enumerate(tasks, 1) if text in t["name"].lower()]


def summary(tasks):
    done = sum(1 for t in tasks if t["done"])
    return {"total": len(tasks), "done": done, "pending": len(tasks) - done}



def list_tasks(tasks, pending_only=False, priority=None, by_priority=False, done_only=False):
    visible = [(i, t) for i, t in enumerate(tasks, 1)
               if not (pending_only and t["done"])
               and not (done_only and not t["done"])
               and (priority is None or t["priority"] == priority)]
    if by_priority:
        # high first; the numbers stay the same so done/rm still work with them
        visible.sort(key=lambda item: -PRIORITIES.index(item[1]["priority"]))
    if not visible:
        print("\n  No tasks to show.\n")
        return
    title = ("📋 Pending tasks:" if pending_only
             else "📋 Done tasks:" if done_only
             else "📋 Your tasks:")
    print(f"\n  {title}")
    print("  " + "-" * 45)
    for i, task in visible:
        status = "✅" if task["done"] else "⬜"
        icon = PRIORITY_ICONS.get(task["priority"], "")
        print(f"  {i}. {status} {icon} {task['name']}")
        if task["done_at"]:
            print(f"        done on {task['done_at']}")
    s = summary(tasks)
    print("  " + "-" * 45)
    print(f"  {s['done']}/{s['total']} done · {s['pending']} pending\n")


def read_number(message):
    try:
        return int(input(message))
    except ValueError:
        return -1


def normalize_priority(text):
    """Accepts "Medium", "medium" or just the initial (l/m/h)."""
    clean = text.strip().lower()
    shortcuts = {p[0]: p for p in PRIORITIES}
    return shortcuts.get(clean, clean)


def read_priority(current=None):
    default = current or "medium"
    text = input(f"  Priority (low/medium/high) [{default}]: ")
    return normalize_priority(text) or default


def run(action, *args, **kwargs):
    """Runs the function and shows the error without breaking the program."""
    try:
        return action(*args, **kwargs)
    except (ValueError, IndexError) as error:
        print(f"  ⚠️  {error}\n")
        return None


def menu():
    print("\n  ================================")
    print("          📝 To-Do List          ")
    print("  ================================")
    print("  1. Show all tasks")
    print("  2. Show pending tasks")
    print("  3. Add task")
    print("  4. Complete task")
    print("  5. Reopen task")
    print("  6. Edit task")
    print("  7. Remove task")
    print("  8. Clear done tasks")
    print("  9. Search tasks")
    print("  0. Quit")
    print("  ================================")
    return input("  Choose an option: ").strip()


def run_option(option, tasks):
    """Runs a menu option. Returns False when it's time to quit."""
    if option == "1":
        list_tasks(tasks)
    elif option == "2":
        list_tasks(tasks, pending_only=True)
    elif option == "3":
        name = input("  Task name: ")
        task = run(create_task, tasks, name, read_priority())
        if task:
            save_tasks(tasks)
            print(f"  ✅ Task '{task['name']}' added!\n")
    elif option == "4":
        list_tasks(tasks, pending_only=True)
        task = run(complete, tasks, read_number("  Number of the task to complete: "))
        if task:
            save_tasks(tasks)
            print(f"  ✅ '{task['name']}' marked as done!\n")
    elif option == "5":
        list_tasks(tasks)
        task = run(reopen, tasks, read_number("  Number of the task to reopen: "))
        if task:
            save_tasks(tasks)
            print(f"  🔄 '{task['name']}' is pending again.\n")
    elif option == "6":
        list_tasks(tasks)
        number = read_number("  Number of the task to edit: ")
        current = run(get_task, tasks, number)
        if current:
            new_name = input(f"  New name [{current['name']}]: ").strip() or None
            task = run(edit, tasks, number, new_name, read_priority(current["priority"]))
            if task:
                save_tasks(tasks)
                print("  ✏️  Task updated!\n")
    elif option == "7":
        list_tasks(tasks)
        removed = run(remove, tasks, read_number("  Number of the task to remove: "))
        if removed:
            save_tasks(tasks)
            print(f"  🗑️  '{removed['name']}' removed!\n")
    elif option == "8":
        count = clear_done(tasks)
        save_tasks(tasks)
        print(f"  🧹 {count} done task(s) removed.\n")
    elif option == "9":
        found = run(find, tasks, input("  Search for: "))
        if found is None:
            return True
        for i, task in found:
            print(f"  {i}. {'✅' if task['done'] else '⬜'} {task['name']}")
        print(f"  {len(found)} task(s) found.\n")
    elif option == "0":
        print("\n  See you! 👋\n")
        return False
    else:
        print("  ⚠️  Invalid option.\n")

    return True


def cli(argv, path=None):
    """Direct commands, for when you don't want the menu: python todo.py add "Buy bread" -p high"""
    parser = argparse.ArgumentParser(
        prog="todo.py",
        description="To-do list. Without a command it opens the menu.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    show = commands.add_parser("list", help="show the tasks")
    which = show.add_mutually_exclusive_group()
    which.add_argument("--pending", action="store_true", help="only the ones not done")
    which.add_argument("--done", action="store_true", help="only the ones already done")
    show.add_argument("-p", "--priority", type=normalize_priority, choices=PRIORITIES,
                      help="only this priority")
    show.add_argument("-s", "--sort", action="store_true", help="high priority first")
    show.add_argument("--json", action="store_true", help="print the raw tasks, to use in scripts")
    show.add_argument("--md", action="store_true", help="markdown checklist, to paste in an issue or notes")

    add = commands.add_parser("add", help="add a task")
    add.add_argument("name", nargs="+", help="task name (quotes are optional)")
    add.add_argument("-p", "--priority", default="medium", type=normalize_priority,
                     help="low, medium or high (or l/m/h)")

    finish = commands.add_parser("done", help="mark as done (one or more numbers)")
    finish.add_argument("numbers", type=int, nargs="+")

    back = commands.add_parser("reopen", help="mark as pending again (one or more numbers)")
    back.add_argument("numbers", type=int, nargs="+")

    delete = commands.add_parser("rm", help="remove (one or more numbers)")
    delete.add_argument("numbers", type=int, nargs="+", help="the task numbers shown by list")

    commands.add_parser("clear", help="remove the done tasks")

    change = commands.add_parser("edit", help="rename a task or change its priority")
    change.add_argument("number", type=int)
    change.add_argument("-n", "--name")
    change.add_argument("-p", "--priority", type=normalize_priority)

    search = commands.add_parser("find", help="search tasks by name")
    search.add_argument("text", nargs="+")

    commands.add_parser("stats", help="how many are done and pending")

    reorder = commands.add_parser("move", help="change a task's position in the list")
    reorder.add_argument("number", type=int)
    reorder.add_argument("to", type=int, help="the new position")

    args = parser.parse_args(argv)
    tasks = load_tasks(path)

    try:
        if args.command == "list" and args.md:
            for task in tasks:
                print(f"- [{'x' if task['done'] else ' '}] {task['name']}")
            return 0
        if args.command == "list" and args.json:
            print(json.dumps(tasks, ensure_ascii=False, indent=2))
            return 0
        if args.command == "list":
            list_tasks(tasks, pending_only=args.pending, priority=args.priority,
                       by_priority=args.sort, done_only=args.done)
            return 0
        if args.command == "find":
            found = find(tasks, " ".join(args.text))
            for i, task in found:
                print(f"{i}. {'[x]' if task['done'] else '[ ]'} {task['name']}")
            if not found:
                print("Nothing found.")
            return 0
        if args.command == "stats":
            s = summary(tasks)
            pending = [t["priority"] for t in tasks if not t["done"]]
            parts = [f"{pending.count(p)} {p}" for p in reversed(PRIORITIES) if p in pending]
            detail = f" ({', '.join(parts)})" if parts else ""
            print(f"{s['done']}/{s['total']} done, {s['pending']} pending{detail}")
            return 0
        if args.command == "add":
            task = create_task(tasks, " ".join(args.name), args.priority)
            message = f"Added: {task['name']}"
        elif args.command == "done":
            # if one number is wrong nothing gets saved, so it's all or nothing
            names = [complete(tasks, n)["name"] for n in args.numbers]
            message = "\n".join(f"Done: {name}" for name in names)
        elif args.command == "reopen":
            names = [reopen(tasks, n)["name"] for n in args.numbers]
            message = "\n".join(f"Pending again: {name}" for name in names)
        elif args.command == "move":
            message = f"Moved to {args.to}: {move(tasks, args.number, args.to)['name']}"
        elif args.command == "edit":
            if args.name is None and args.priority is None:
                raise ValueError("Nothing to change, use --name or --priority.")
            message = f"Updated: {edit(tasks, args.number, args.name, args.priority)['name']}"
        elif args.command == "rm":
            for n in args.numbers:
                get_task(tasks, n)
            # from the biggest number down, so removing one doesn't shift the others
            removed = [remove(tasks, n)["name"] for n in sorted(set(args.numbers), reverse=True)]
            message = "\n".join(f"Removed: {name}" for name in reversed(removed))
        else:
            count = clear_done(tasks)
            if not count:
                print("Nothing to clear, no task is done.")
                return 0
            message = f"{count} done task(s) removed."
    except (ValueError, IndexError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    save_tasks(tasks, path)
    print(message)
    return 0


def main():
    # On Windows, with input or output redirected, Python uses cp1252
    # and the output breaks on the emojis
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    if len(sys.argv) > 1:
        sys.exit(cli(sys.argv[1:]))

    tasks = load_tasks()
    keep_going = True
    while keep_going:
        # Ctrl+C or Ctrl+D on any prompt (not just the menu) quits the program
        # instead of showing the Python error
        try:
            keep_going = run_option(menu(), tasks)
        except (EOFError, KeyboardInterrupt):
            keep_going = run_option("0", tasks)


if __name__ == "__main__":
    main()
