import argparse
import base64
import http.server
import io
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# System defaults
PORT = 10043
TIME_LIMIT_SEC = 4.0
APP_DIR = "~/.vc-zed-cp-helper"  # CHANGE THIS ACCORDINGLY

# Language profiles: compiler command, CF/AtCoder language IDs
LANGUAGES = {
    "cpp20": {
        "compile": ["g++", "-std=c++20", "-O2", "-Wall", "-Wextra"],
        "cf_id": "89",
        "cf_name": "GNU G++20 13.2 (64 bit)",
        "ac_id": "5001",
        "ac_name": "C++ 20 (gcc 12.2)",
    },
    "cpp23": {
        "compile": [
            "g++",
            "-std=c++23",
            "-O2",
            "-Winvalid-pch",
            # precompiled bits/stdc++.h header for faster compilation
            # "-include-pch",
            # "/usr/local/include/bits/stdc++.h.pch"
        ],
        "cf_id": "91",
        "cf_name": "GNU G++23 14.2 (64 bit, msys2)",
        "ac_id": "5002",
        "ac_name": "C++ 23 (gcc 12.2)",
    },
    "cpp17": {
        "compile": ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra"],
        "cf_id": "54",
        "cf_name": "GNU G++17 7.3.0",
        "ac_id": "5001",
        "ac_name": "C++ 20 (gcc 12.2)",
    },
    "python": {
        "run": ["python3"],
        "cf_id": "31",
        "cf_name": "Python 3.8.10",
        "ac_id": "5055",
        "ac_name": "Python (CPython 3.11.4)",
    },
    "java": {
        "compile": ["javac"],
        "run_compiled": ["java", "-cp"],
        "cf_id": "36",
        "cf_name": "Java 21 64bit",
        "ac_id": "5005",
        "ac_name": "Java (OpenJDK 17)",
    },
}
DEFAULT_LANG = "cpp23"
CONFIG_PATH = Path(APP_DIR).expanduser() / "config.json"
DEFAULT_BROWSER = "safari"
DEFAULT_TEMPLATE = "boilerplate"  # "boilerplate" or "zed_snippets"


def _load_config():
    """Load config.json, returning a dict."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"⚠️  Warning: {CONFIG_PATH} contains invalid JSON. Using defaults.")
        except PermissionError:
            print(f"⚠️  Warning: Cannot read {CONFIG_PATH} (permission denied). Using defaults.")
        except Exception as e:
            print(f"⚠️  Warning: Failed to read {CONFIG_PATH}: {e}. Using defaults.")
    return {}


def _save_config(cfg):
    """Save a dict to config.json."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_saved_lang():
    """Read the saved language from config. Falls back to DEFAULT_LANG."""
    cfg = _load_config()
    lang = cfg.get("lang", DEFAULT_LANG)
    if lang in LANGUAGES:
        return lang
    return DEFAULT_LANG


def get_saved_browser():
    """Read the saved browser from config. Falls back to DEFAULT_BROWSER."""
    cfg = _load_config()
    browser = cfg.get("browser", DEFAULT_BROWSER)
    # Only Safari is supported for silent submissions
    if browser == "safari":
        return browser
    return DEFAULT_BROWSER


def set_lang_cmd(args):
    """Save the chosen language to config."""
    lang = args.lang
    if lang not in LANGUAGES:
        print(f"❌ Unknown language '{lang}'. Available: {', '.join(LANGUAGES.keys())}")
        return
    cfg = _load_config()
    cfg["lang"] = lang
    _save_config(cfg)
    print(f"✅ Language set to \033[92m{lang}\033[0m")
    print(f"   Compiler:  {LANGUAGES[lang].get('compile', LANGUAGES[lang].get('run', []))}")
    print(f"   CF Submit:  {LANGUAGES[lang]['cf_name']} (id={LANGUAGES[lang]['cf_id']})")
    print(f"\n   Saved to {CONFIG_PATH}")
    print("   All future Run/Submit tasks will use this language.")


def set_browser_cmd(args):
    """Save the chosen browser to config."""
    browser = args.browser.lower()
    if browser != "safari":
        print(f"❌ Only Safari is supported for silent submissions.")
        print(f"   Other browsers (Brave, Chrome, Orion) cannot submit in the background.")
        return
    cfg = _load_config()
    cfg["browser"] = browser
    _save_config(cfg)
    print(f"✅ Browser set to \033[92mSafari\033[0m")
    print(f"\n   Saved to {CONFIG_PATH}")
    print("   All future Submit tasks will use Safari.")


def set_template_cmd(args):
    """Save the template source to config."""
    template = args.template
    if template not in ("boilerplate", "zed_snippets"):
        print(f"❌ Unknown template source '{template}'. Use 'boilerplate' or 'zed_snippets'.")
        return
    cfg = _load_config()
    cfg["template"] = template
    if template == "zed_snippets":
        if not args.snippet_name or not args.snippet_name.strip():
            print("❌ Snippet name is required for Zed snippets.")
            return

        path = "~/.config/zed/snippets/c++.json"
        zed_snippets = Path(path).expanduser()
        if zed_snippets.exists():
            try:
                snippet_data = json.loads(zed_snippets.read_text(encoding="utf-8"))
                # Look for snippet named "{snippet_name}" (case-insensitive)
                template_key = None
                for key in snippet_data:
                    if key.lower() == args.snippet_name.strip().lower():
                        template_key = key
                        break

                if template_key:
                    pass
                else:
                    print(f"[Companion] ❌ No snippet named \033[91m {args.snippet_name}\033[0m found in \033[92m {zed_snippets}\033[0m .")
                    return
            except Exception as e:
                print(f"[Companion] Failed to parse Zed snippets: {e}")
                return
        else:
            print(f"[Companion] ❌ Failed to parse Zed snippets, c++.json not found in \033[91m {path}\033[0m")
            return
        cfg["snippet_name"] = args.snippet_name.strip().lower()
    _save_config(cfg)

    if template == "boilerplate":
        print(f"✅ Template source set to \033[92mboilerplate.cpp\033[0m")
        print(f"   Reading from: {Path(APP_DIR).expanduser() / 'boilerplate.cpp'}")
    else:
        print(
            f"✅ Template source set to \033[92mZed snippets\033[0m (snippet name: \033[31m{args.snippet_name}\033[0m)"
        )
        print("   Reading from: ~/.config/zed/snippets/c++.json")
    print(f"\n   Saved to {CONFIG_PATH}")


def is_folder_open_in_zed(folder_path):
    """Checks if a Zed process is currently managing this folder path."""
    try:
        output = subprocess.check_output(["ps", "aux"]).decode("utf-8")
        folder_str = str(folder_path)
        for line in output.splitlines():
            if "Zed" in line and folder_str in line:
                return True
        return False
    except Exception:
        return False


def get_project_folder(source_file):
    # Heuristic: the project folder is the first directory looking upwards that has .TestCases or .zed,
    # or just the directory of the file if not found.
    curr = Path(source_file).parent.resolve()
    for p in [curr] + list(curr.parents):
        if (
            (p / ".TestCases").exists()
            or (p / ".zed").exists()
            or (p / ".git").exists()
        ):
            return p
    return curr


def get_binary_path(source_file):
    compiled_dir = Path(APP_DIR).expanduser() / ".Compiled"
    compiled_dir.mkdir(exist_ok=True)
    # Use parent directory name and file stem to prevent name collisions
    safe_name = f"{source_file.parent.name}_{source_file.stem}"
    safe_name = re.sub(r"[^\w_]", "", safe_name)
    return compiled_dir / safe_name


def get_testcases_path(source_file):
    testcases_dir = Path(APP_DIR).expanduser() / ".testcases"
    testcases_dir.mkdir(exist_ok=True)
    return testcases_dir / f"{Path(source_file).stem}.json"


def prune_compiled_binaries():
    """Deletes compiled binaries older than 24 hours in the global .Compiled directory."""
    try:
        compiled_dir = Path(APP_DIR).expanduser() / ".Compiled"
        if not compiled_dir.exists():
            return
        now = time.time()
        limit = now - 86400  # 24 hours
        for item in compiled_dir.iterdir():
            if item.is_file():
                if item.stat().st_mtime < limit:
                    try:
                        item.unlink()
                    except Exception:
                        pass
    except Exception:
        pass


# ======================== Listener ========================
class CompanionHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
            print(f"[Companion] ❌ Received malformed request: {e}")
            self.send_response(400)
            self.end_headers()
            return
        self.server.foc_process_problem(data)
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        import urllib.parse
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/command":
            params = urllib.parse.parse_qs(parsed_url.query)
            action = params.get("action", [None])[0]
            file_path = params.get("file", [None])[0]
            if action:
                if file_path:
                    active_problem["file_path"] = Path(file_path)
                self.server.foc_handle_command(action)
                self.send_response(200)
                self.end_headers()
                return
        self.send_response(404)
        self.end_headers()


def process_problem(data, active_folder):
    problem_name = data.get("name", "problem")
    safe_filename = problem_name.replace(" ", "_").replace(".", "_")
    safe_filename = re.sub(r"[^\w_]", "", safe_filename)
    if not safe_filename:
        safe_filename = "problem"

    # Determine file extension based on language
    lang_key = get_saved_lang()
    ext_map = {"cpp20": ".cpp", "cpp23": ".cpp", "cpp17": ".cpp", "python": ".py", "java": ".java"}
    file_ext = ext_map.get(lang_key, ".cpp")
    file_name = f"{safe_filename}{file_ext}"
    file_path = active_folder / file_name

    print(f"\n[Companion] Received problem: {problem_name}")
    print(f"[Companion] Writing to: {file_path}")

    url = data.get("url", "")
    time_limit = data.get("timeLimit", 0)  # in ms

    # Write template if file doesn't exist
    if not file_path.exists():
        content = ""
        cfg = _load_config()
        template_source = cfg.get("template", DEFAULT_TEMPLATE)

        if template_source == "zed_snippets":
            # Read from Zed's cpp.json snippets (useful for multi-IDE sync via symlink)
            snippet_name = str(cfg.get("snippet_name", "boilerplate")).strip().lower()
            zed_snippets = Path("~/.config/zed/snippets/c++.json").expanduser()
            if zed_snippets.exists():
                try:
                    snippet_data = json.loads(zed_snippets.read_text(encoding="utf-8"))
                    # Look for snippet named "{snippet_name}" (case-insensitive)
                    template_key = None
                    for key in snippet_data:
                        if key.lower() == snippet_name:
                            template_key = key
                            break

                    if template_key:
                        body = snippet_data[template_key].get("body", [])
                        content = "\n".join(body) if isinstance(body, list) else body
                        # Strip snippet placeholders like $1, ${2:default}
                        content = re.sub(r"\$\d+", "", content)
                        content = re.sub(r"\$\{\d+(:.*?)?\}", "", content)
                        print(f"[Companion] Using Zed snippet: {template_key}")
                    else:
                        print(
                            f"[Companion] No snippet named \033[91m{snippet_name}\033[0m found in \033[92m{zed_snippets}\033[0m "
                        )
                except Exception as e:
                    print(f"[Companion] Failed to parse Zed snippets: {e}")

        # Default: read from APP_DIR/boilerplate.<ext>
        if not content:
            # Try language-specific boilerplate first, then fallback to .cpp
            for ext in [file_ext, ".cpp"]:
                boilerplate = Path(APP_DIR).expanduser() / f"boilerplate{ext}"
                if boilerplate.exists():
                    try:
                        content = boilerplate.read_text(encoding="utf-8")
                        print(f"[Companion] Using template: {boilerplate.name}")
                        break
                    except Exception as e:
                        print(f"[Companion] Failed to read boilerplate: {e}")

        # Prepend URL comment to the top of the file
        url_comment = f"# URL: {url}\n" if file_ext == ".py" else f"// URL: {url}\n"
        full_content = url_comment + content
        file_path.write_text(full_content, encoding="utf-8")
    else:
        # If the file already exists, make sure it has the URL comment at the top if missing
        original_code = file_path.read_text(encoding="utf-8")
        url_pattern = r"^(?://|#) URL: https?://\S+"
        if not re.match(url_pattern, original_code):
            url_comment = f"# URL: {url}\n" if file_ext == ".py" else f"// URL: {url}\n"
            file_path.write_text(url_comment + original_code, encoding="utf-8")

    # Save tests to the .testcases JSON database file
    testcases_path = get_testcases_path(file_path)
    testcases_data = {
        "name": problem_name,
        "url": url,
        "timeLimit": time_limit,
        "tests": [
            {
                "input": test.get("input", ""),
                "output": test.get("output", "")
            }
            for test in data.get("tests", [])
        ]
    }
    testcases_path.write_text(json.dumps(testcases_data, indent=2), encoding="utf-8")
    print(f"[Companion] Saved {len(data.get('tests', []))} tests in hidden database: {testcases_path.name}")
    print(f"[Companion] Ready in Zed! Open {file_path}")

    return file_path


def force_kill_process_on_port(port):
    """Finds and kills any process listening on the given port (macOS/Linux)."""
    if sys.platform not in ("darwin", "linux"):
        return
    command = f"lsof -ti tcp:{port}"
    try:
        output = subprocess.check_output(command, shell=True).decode().strip()
        if not output:
            return
        import signal

        pids = output.splitlines()
        for pid_str in pids:
            pid_str = pid_str.strip()
            if not pid_str:
                continue
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            print(f"[Listen] Port {port} is in use by PID {pid}. Terminating it...")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue  # Already dead
            except PermissionError:
                print(f"[Listen] ⚠️  Cannot kill PID {pid} (permission denied). Try running with sudo.")
                continue
        time.sleep(0.3)  # Give the OS a moment to release the port

        # If SIGTERM didn't work, try SIGKILL
        try:
            remaining = subprocess.check_output(command, shell=True).decode().strip()
            for pid_str in remaining.splitlines():
                pid_str = pid_str.strip()
                if pid_str:
                    try:
                        os.kill(int(pid_str), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, ValueError):
                        pass
            time.sleep(0.1)
        except subprocess.CalledProcessError:
            pass  # All processes are dead
    except subprocess.CalledProcessError:
        pass  # Port is not in use


def get_active_zed_folder():
    """Uses AppleScript and lsof to magically find Zed's active absolute project directory."""
    if sys.platform != "darwin":
        return None
    try:
        applescript = """
        tell application "System Events"
            if exists process "zed" then
                tell process "zed" to get name of front window
            else if exists process "Zed" then
                tell process "Zed" to get name of front window
            else
                return ""
            end if
        end tell
        """
        title = (
            subprocess.check_output(
                [
                    "osascript",
                    "-e",
                    applescript,
                ],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )

        # Zed title looks like: "project_name — file.cpp"
        # Extract the project name:
        project_name = title.split(" — ")[0].split(" - ")[0].strip()

        if project_name:
            lsof_out = subprocess.check_output(
                ["lsof", "-c", "zed"], stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            for line in lsof_out.splitlines():
                if "DIR" in line and f"/{project_name}" in line:
                    # Extract path from lsof output (it starts at the first '/')
                    try:
                        path = "/" + line.split(" /", 1)[1]
                        if Path(path).name == project_name and Path(path).is_dir():
                            return Path(path)
                    except Exception:
                        pass
    except Exception:
        pass
    return None


# Global state to track active problem context in the REPL
import threading
active_problem = {
    "file_path": None,
    "name": None
}


def get_prompt():
    if active_problem["file_path"]:
        return f"\033[96mcp-helper [{active_problem['file_path'].name}]\033[0m> "
    return "\033[96mcp-helper\033[0m> "


def print_help():
    print("""
Available Commands:
  r, run      Compile and run tests for the active problem.
  a, add      Add a custom test case to the active problem.
  e, edit     Edit an existing testcase for the active problem.
  v, view     Reprint all test cases for the active problem.
  s, submit   Submit active problem solution to Codeforces / AtCoder.
  h, help     Print this help message.
  q, exit     Quit the CP helper shell.
""")


def shell_view():
    file_path = active_problem["file_path"]
    if not file_path:
        print("⚠️  No active problem loaded yet. Use Competitive Companion browser extension.")
        return
    tests = load_tests_for_file(file_path)
    if not tests:
        print("⚠️  No test cases found for the active problem.")
        return
    print(f"\n=================== TEST CASES ===================")
    for idx, t in enumerate(tests):
        print(f"[Case {idx + 1}]")
        print("Input:")
        print(t["test"].rstrip())
        print("Expected:")
        print(t["correct_answers"][0].rstrip() if t["correct_answers"] else "(no expected)")
        print("-" * 35)
    print(f"==================================================")


def shell_run():
    file_path = active_problem["file_path"]
    if not file_path:
        print("⚠️  No active problem loaded yet.")
        return
    class Args:
        def __init__(self, file):
            self.file = file
    run_cmd(Args(file_path))


def open_buffer_in_zed(source_file, add_blank=False):
    tests_path = get_testcases_path(source_file)
    data = {}
    if tests_path.exists():
        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    tests = data.get("tests", [])
    
    # Format the cases into a pretty text buffer
    lines = []
    lines.append(f"# === TEST CASES FOR: {source_file.name} ===")
    lines.append("# Edit inputs and expected outputs. Save (Cmd+S) and Close (Cmd+W) to apply changes.")
    lines.append("# To add a case, write a new '=== Case X ===' block at the bottom.")
    lines.append("# To delete a case, just remove its block.")
    lines.append("")

    for idx, t in enumerate(tests):
        lines.append(f"=== Case {idx + 1} ===")
        lines.append("Input:")
        lines.append(t.get("input", "").rstrip())
        lines.append("")
        lines.append("Expected:")
        lines.append(t.get("output", "").rstrip())
        lines.append("")

    if add_blank:
        lines.append(f"=== Case {len(tests) + 1} ===")
        lines.append("Input:")
        lines.append("")
        lines.append("Expected:")
        lines.append("")
        
    temp_file = Path(tempfile.gettempdir()) / f"cp_cases_{source_file.stem}.test"
    temp_file.write_text("\n".join(lines), encoding="utf-8")
    
    # Open in Zed and wait
    import shutil
    zed_bin = shutil.which("zed") or "/usr/local/bin/zed"
    subprocess.run([zed_bin, "-w", str(temp_file)])
    
    # Read the updated buffer back
    if temp_file.exists():
        content = temp_file.read_text(encoding="utf-8")
        try:
            temp_file.unlink()
        except Exception:
            pass
            
        # Parse the custom format
        cases_raw = re.split(r"=== Case \d+ ===", content)
        new_tests = []
        for case_str in cases_raw:
            case_str = case_str.strip()
            if not case_str:
                continue
            
            # Extract Input: and Expected:
            input_marker = "Input:"
            expected_marker = "Expected:"
            
            if input_marker in case_str and expected_marker in case_str:
                try:
                    input_idx = case_str.index(input_marker) + len(input_marker)
                    expected_idx = case_str.index(expected_marker)
                    
                    input_val = case_str[input_idx:expected_idx].strip()
                    expected_val = case_str[expected_idx + len(expected_marker):].strip()
                    
                    new_tests.append({
                        "input": input_val + "\n" if input_val else "",
                        "output": expected_val + "\n" if expected_val else ""
                    })
                except Exception:
                    pass
                    
        # Save back to JSON database
        data["tests"] = new_tests
        tests_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return len(new_tests)
    return len(tests)


class CancelledException(Exception):
    pass


def _read_multiline_cancelable(prompt):
    print(prompt)
    lines = []
    try:
        while True:
            line = input()
            if line.strip().lower() in ("q", "exit", "cancel", ":q"):
                raise CancelledException()
            if line == "" and lines:  # Empty line after content = done
                break
            if line == "" and not lines:
                break  # Immediate Enter = empty input
            lines.append(line)
    except KeyboardInterrupt:
        raise CancelledException()
    return "\n".join(lines)


def shell_add():
    file_path = active_problem["file_path"]
    if not file_path:
        print("⚠️  No active problem loaded yet.")
        return

    print(f"\n📝 Adding custom test case to \033[96m{file_path.name}\033[0m")
    print("   (Type 'q', 'exit', or press Ctrl+C at any prompt to cancel)")

    try:
        test_input = _read_multiline_cancelable("\033[1mEnter input\033[0m (empty line to finish):")
        test_output = _read_multiline_cancelable("\n\033[1mEnter expected output\033[0m (empty line to finish, or Enter immediately to skip):")
    except CancelledException:
        print("\n⚠️  Add case cancelled. No changes were made.")
        return

    # Save to JSON database
    tests_path = get_testcases_path(file_path)
    data = {}
    if tests_path.exists():
        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if "tests" not in data:
        data["tests"] = []

    data["tests"].append({
        "input": test_input,
        "output": test_output
    })

    tests_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    next_case_num = len(data["tests"])
    if test_output:
        label = test_output[:50] + ('...' if len(test_output) > 50 else '')
        print(f"\n✅ Added \033[92mCase {next_case_num}\033[0m (expected: {label})")
    else:
        print(f"\n✅ Added \033[92mCase {next_case_num}\033[0m (no expected output)")


def shell_edit():
    file_path = active_problem["file_path"]
    if not file_path:
        print("⚠️  No active problem loaded yet.")
        return
    print(f"\n✏️  Opening test cases buffer in Zed to edit...")
    num_cases = open_buffer_in_zed(file_path, add_blank=False)
    print(f"✅ Test cases updated! Total cases: {num_cases}")


def shell_submit():
    file_path = active_problem["file_path"]
    if not file_path:
        print("⚠️  No active problem loaded yet.")
        return
    class Args:
        def __init__(self, file):
            self.file = file
            self.yes = False
    submit_cmd(Args(file_path))


import queue
import select

command_queue = queue.Queue()


def focus_zed_terminal():
    """Toggles/focuses the terminal panel in Zed on macOS."""
    if sys.platform == "darwin":
        try:
            # First activate zed using standard Applescript (does not require assistive access)
            subprocess.run(["osascript", "-e", 'tell application "zed" to activate'], capture_output=True)
            
            applescript = """
            tell application "System Events"
                if exists process "zed" then
                    tell process "zed"
                        set frontmost to true
                        keystroke "`" using control down
                    end tell
                else if exists process "Zed" then
                    tell process "Zed"
                        set frontmost to true
                        keystroke "`" using control down
                    end tell
                end if
            end tell
            """
            res = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=2)
            if res.returncode != 0 and "assistive access" in res.stderr:
                print("\n⚠️  Note: To automatically focus the terminal when adding test cases, please grant Accessibility permissions to Zed (or your terminal app) in System Settings -> Privacy & Security -> Accessibility.")
        except Exception:
            pass


def execute_command(cmd_line):
    parts = cmd_line.split()
    if not parts:
        return
    cmd = parts[0].lower()

    if cmd in ("help", "h"):
        print_help()
    elif cmd in ("exit", "quit", "q"):
        print("Exiting CP Helper shell. Goodbye!")
        sys.exit(0)
    elif cmd in ("view", "v"):
        shell_view()
    elif cmd in ("run", "r"):
        shell_run()
    elif cmd in ("add", "a"):
        shell_add()
    elif cmd == "add_remote":
        shell_add()
    elif cmd in ("edit", "e"):
        shell_edit()
    elif cmd in ("submit", "s"):
        shell_submit()
    else:
        print(f"❌ Unknown command: '{cmd}'. Type 'h' or 'help' for instructions.")


def repl_loop():
    # Print the initial prompt
    prompt = get_prompt()
    sys.stdout.write(prompt)
    sys.stdout.flush()

    while True:
        try:
            # 1. Check if there are dispatched commands in the queue
            try:
                cmd_line = command_queue.get_nowait()
                # Clear the prompt line
                sys.stdout.write("\r\033[K")
                execute_command(cmd_line)
                # Print prompt again
                prompt = get_prompt()
                sys.stdout.write(prompt)
                sys.stdout.flush()
                continue
            except queue.Empty:
                pass

            # 2. Check if user typed anything on stdin
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if r:
                cmd_line = sys.stdin.readline()
                if not cmd_line:  # EOF
                    print("\nExiting CP Helper shell. Goodbye!")
                    break
                cmd_line = cmd_line.strip()
                if cmd_line:
                    execute_command(cmd_line)
                # Print prompt again
                prompt = get_prompt()
                sys.stdout.write(prompt)
                sys.stdout.flush()
        except KeyboardInterrupt:
            # Graceful cancellation of commands/REPL loop
            print("\n")
            prompt = get_prompt()
            sys.stdout.write(prompt)
            sys.stdout.flush()


def listen_cmd(args):
    # Determine the target directory: defaults to current directory (".")
    target_dir = Path(args.directory).resolve()

    force_kill_process_on_port(PORT)

    # Prune old compiled binaries
    prune_compiled_binaries()

    # Write PID file
    pid_path = Path(APP_DIR).expanduser() / "listener.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    socketserver.TCPServer.allow_reuse_address = True
    try:
        server = socketserver.TCPServer(("", PORT), CompanionHandler)
    except OSError as e:
        if "Address already in use" in str(e) or e.errno == 48:
            print(f"❌ Port {PORT} is still in use after kill attempt.")
            print(f"   Try: lsof -ti tcp:{PORT} | xargs kill -9")
            return
        raise

    problem_count = [0]  # Mutable counter for closure

    def handle_problem(data):
        problem_count[0] += 1
        problem_name = data.get("name", "problem")
        time_limit = data.get("timeLimit", 0)
        tl_str = f" (TL: {time_limit}ms)" if time_limit else ""

        file_path = process_problem(data, target_dir)
        if file_path:
            active_problem["file_path"] = file_path
            active_problem["name"] = problem_name

            print(f"\n{'─' * 45}")
            print(f"📥 Received Problem #{problem_count[0]}: {problem_name}{tl_str}")
            print(f"   Saved to: {file_path.name}")
            print(f"{'─' * 45}")

            # Print test cases directly to the listener terminal
            shell_view()
            
            # Print a fresh prompt so the user knows they can continue typing
            prompt = get_prompt()
            sys.stdout.write(f"\r\033[K{prompt}")
            sys.stdout.flush()

            import shutil
            zed_bin = shutil.which("zed") or "/usr/local/bin/zed"
            # Handle Zed Logic: Open folder if missing
            if not is_folder_open_in_zed(target_dir):
                subprocess.run([zed_bin, str(target_dir)])
                time.sleep(1)  # Brief pause to let Zed initialize the workspace

            # '-a' adds the file to the active or nearest workspace cleanly
            subprocess.run([zed_bin, "-a", str(file_path)])

    def handle_command(action):
        action = action.lower()
        if action in ("add", "a"):
            command_queue.put("add_remote")
        else:
            command_queue.put(action)

    server.foc_process_problem = handle_problem
    server.foc_handle_command = handle_command

    # Start the HTTP server on a daemon thread so it doesn't block the prompt
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"[Listen] Starting Competitive Companion listener on port {PORT}...")
    print(f"[Listen] Saving problems to: {target_dir}")
    print("[Listen] Unified CP Shell started. Waiting for requests from browser extension...")
    print("         Type 'help' or 'h' for list of commands.\n")

    try:
        repl_loop()
    finally:
        try:
            pid_path.unlink()
        except Exception:
            pass


# ======================== Run Tests ========================
def normalize(text):
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def check_answer(expected_answers, output):
    if not expected_answers:
        return True
    norm_output = normalize(output)
    for expected in expected_answers:
        if normalize(expected) == norm_output:
            return True
    return False


def extract_tests_from_code(code):
    """Parses the block comment to extract test cases (supports C++/Java and Python syntax)"""
    # Try C++/Java block comment syntax first
    m = re.search(
        r"/\* === TEST CASES ===(.*?)=== END TEST CASES === \*/", code, re.DOTALL
    )
    # Try Python triple-quote syntax
    if not m:
        m = re.search(
            r'""" === TEST CASES ===(.*?)=== END TEST CASES === """', code, re.DOTALL
        )
    if not m:
        return []

    block = m.group(1)
    # Split by [Case X]
    cases = re.split(r"\[Case \d+\]", block)[1:]  # drop the first empty split

    parsed_tests = []
    for c in cases:
        c = c.strip()
        if not c:
            continue
        # Extract Input: and Expected:
        in_m = re.search(r"Input:\s*(.*?)(?:Expected:|$)", c, re.DOTALL)
        out_m = re.search(r"Expected:\s*(.*)", c, re.DOTALL)

        test_in = in_m.group(1).strip() if in_m else ""
        test_out = out_m.group(1).strip() if out_m else ""

        parsed_tests.append(
            {"test": test_in, "correct_answers": [test_out] if test_out else []}
        )
    return parsed_tests


def extract_time_limit_from_code(code):
    """Extract the problem's time limit (in seconds) from the test block.
    Falls back to TIME_LIMIT_SEC if not found."""
    m = re.search(r"TIME_LIMIT:\s*(\d+)ms", code)
    if m:
        return int(m.group(1)) / 1000.0
    return TIME_LIMIT_SEC


def load_tests_for_file(source_file):
    """Loads tests for a given source file from its .testcases/<stem>.json file.
    Falls back to parsing comment blocks in the code for backward compatibility."""
    tests_path = get_testcases_path(source_file)
    if tests_path.exists():
        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
            tests = []
            for test in data.get("tests", []):
                tests.append({
                    "test": test.get("input", ""),
                    "correct_answers": [test.get("output", "")] if test.get("output", "") is not None else []
                })
            return tests
        except Exception:
            pass

    # Fallback to comment parsing
    try:
        code = source_file.read_text(encoding="utf-8")
        return extract_tests_from_code(code)
    except Exception:
        return []


def load_time_limit_for_file(source_file):
    """Loads time limit (in seconds) for a given source file from its .testcases/<stem>.json file,
    or falls back to parsing comments, then falls back to default TIME_LIMIT_SEC."""
    tests_path = get_testcases_path(source_file)
    if tests_path.exists():
        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
            time_limit_ms = data.get("timeLimit", 0)
            if time_limit_ms:
                return time_limit_ms / 1000.0
        except Exception:
            pass

    try:
        code = source_file.read_text(encoding="utf-8")
        return extract_time_limit_from_code(code)
    except Exception:
        return TIME_LIMIT_SEC


def _format_wa_diff(expected_str, actual_str):
    """Format a visual side-by-side diff between expected and actual output."""
    exp_lines = expected_str.strip().splitlines() if expected_str.strip() else []
    act_lines = actual_str.strip().splitlines() if actual_str.strip() else []
    max_lines = max(len(exp_lines), len(act_lines))

    if max_lines == 0:
        return "  (both empty)"

    # Determine column widths: at least 30 chars, max 45 chars
    max_exp_len = max((len(l) for l in exp_lines), default=0)
    max_act_len = max((len(l) for l in act_lines), default=0)
    col_width = max(30, min(45, max(max_exp_len, max_act_len)))

    def color_diff(exp, act):
        """Return act string with only differing characters in red."""
        result = []
        max_len = max(len(exp), len(act))
        for i in range(max_len):
            e = exp[i] if i < len(exp) else None
            a = act[i] if i < len(act) else None
            if e == a:
                result.append(a if a is not None else "")
            else:
                if a is not None:
                    result.append("\033[91m" + a + "\033[0m")
        return "".join(result)

    result = []
    
    # Header box drawing using safe + corners
    hdr_exp = " EXPECTED ".ljust(col_width, "─")
    hdr_act = " GOT ".ljust(col_width, "─")
    result.append(f"+──{hdr_exp}─+─{hdr_act}──+")

    for i in range(max_lines):
        e_line = exp_lines[i] if i < len(exp_lines) else ""
        a_line = act_lines[i] if i < len(act_lines) else ""
        
        # Format expected column
        e_display = e_line.ljust(col_width)
        
        # Format got column with diff coloring
        if e_line == a_line:
            a_display = a_line.ljust(col_width)
            pointer = ""
        else:
            colored_act = color_diff(e_line, a_line)
            visual_len = len(a_line)
            padding = " " * max(0, col_width - visual_len)
            a_display = colored_act + padding
            pointer = " \033[91m◀\033[0m"

        result.append(f"│  {e_display} │  {a_display} │{pointer}")

    # Bottom border using safe + corners
    result.append(f"+──" + ("─" * col_width) + "─+─" + ("─" * col_width) + "──+")

    if len(exp_lines) != len(act_lines):
        result.append(f"  \033[90mNote: Expected {len(exp_lines)} lines, but got {len(act_lines)} lines.\033[0m")

    return "\n".join(result)

def compile_and_get_run_cmd(source_file, lang_key):
    """Returns the command list to execute the program, or None on failure."""
    lang = LANGUAGES[lang_key]

    # Interpreted languages (python, etc.)
    if "run" in lang:
        return lang["run"] + [str(source_file)]

    # Compiled languages
    bin_path = get_binary_path(source_file)
    compile_cmd = lang["compile"] + [str(source_file), "-o", str(bin_path)]

    # Java special case: compile with -d to place .class in source directory
    if "run_compiled" in lang:
        compile_cmd = lang["compile"] + ["-d", str(source_file.parent), str(source_file)]

    print(f"⚙️  \033[90mCompiling: {' '.join(compile_cmd)}\033[0m")
    t0 = time.time()
    res = subprocess.run(
        compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    t1 = time.time()
    if res.returncode != 0:
        print(f"❌ \033[91mCompilation Failed in {((t1 - t0) * 1000):.0f}ms\033[0m\n")
        print(res.stderr)
        return None
    print(f"✅ \033[92mCompiled successfully in {((t1 - t0) * 1000):.0f}ms\033[0m\n")
    if res.stderr and res.stderr.strip():
        print(f"\033[93m⚠️  Compilation Warnings:\033[0m")
        print(f"\033[90m{res.stderr.strip()}\033[0m\n")

    # Ad-hoc code sign binary on macOS to eliminate gatekeeper scan lag
    if sys.platform == "darwin" and "run" not in lang and "run_compiled" not in lang:
        try:
            subprocess.run(
                ["codesign", "-s", "-", "--force", str(bin_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    if "run_compiled" in lang:
        return lang["run_compiled"] + [str(source_file.parent), source_file.stem]
    return [str(bin_path)]


def run_cmd(args):
    print("\033[H\033[J", end="")
    source_file = Path(args.file).resolve()
    if not source_file.exists():
        print(f"❌ Error: File {source_file} not found.")
        return

    lang_key = get_saved_lang()
    # Extract time limit from database (falls back to code if JSON is missing)
    tl_sec = load_time_limit_for_file(source_file)
    print(f"🔧 \033[90mLanguage: {lang_key} │ Time Limit: {tl_sec:.1f}s\033[0m\n")

    tests = load_tests_for_file(source_file)

    if not tests:
        print("⚠️  No test cases found for this problem.")
        print("💡 To fetch them, open the problem page in your browser and click the Competitive Companion extension icon.\n")
        print("👉 Running interactively (Ctrl+D to send EOF, Ctrl+C to stop)...")
        run_cmd_list = compile_and_get_run_cmd(source_file, lang_key)
        if run_cmd_list:
            try:
                subprocess.run(run_cmd_list, timeout=30)
            except subprocess.TimeoutExpired:
                print("\n⏰ Interactive run timed out after 30s.")
            except KeyboardInterrupt:
                print("\n⏹️  Stopped.")
        return

    run_cmd_list = compile_and_get_run_cmd(source_file, lang_key)
    if not run_cmd_list:
        return

    # Show compact test preview
    print(f"🧪 Running {len(tests)} test case{'s' if len(tests) != 1 else ''}...")
    for i, test in enumerate(tests):
        preview_in = test.get("test", "").split("\n")[0][:40]
        has_expected = bool(test.get("correct_answers", []))
        exp_tag = "" if has_expected else " \033[90m(no expected)\033[0m"
        print(f"   Case {i+1}: \033[90m{preview_in}{'...' if len(test.get('test','')) > 40 else ''}\033[0m{exp_tag}")
    print()

    passed = 0

    for i, test in enumerate(tests):
        print(f"--- Case {i + 1} ---")
        test_in = test.get("test", "")
        if not test_in.endswith("\n"):
            test_in += "\n"
        test_out_expected = test.get("correct_answers", [])

        t0 = time.time()
        try:
            proc = subprocess.run(
                run_cmd_list,
                input=test_in,
                text=True,
                capture_output=True,
                timeout=tl_sec,
            )
            t1 = time.time()
            elapsed_ms = (t1 - t0) * 1000

            # Show stderr (debug output) immediately
            if proc.stderr and proc.stderr.strip():
                print(f"\033[93m\033[1m⚠️  Debug Output (stderr):\033[0m")
                print(f"\033[90m{proc.stderr.strip()}\033[0m\n")

            if proc.returncode != 0:
                print(
                    f"❌ \033[91mRuntime Error (Exit Code {proc.returncode})\033[0m - {elapsed_ms:.0f}ms"
                )
                if proc.stderr:
                    print(proc.stderr.strip())
            else:
                is_correct = check_answer(test_out_expected, proc.stdout)
                if is_correct:
                    print(f"✅ \033[92mPassed\033[0m - {elapsed_ms:.0f}ms")
                    passed += 1
                else:
                    print(f"❌ \033[91mWrong Answer\033[0m - {elapsed_ms:.0f}ms\n")
                    
                    # Dynamic width input card using safe + corners
                    input_lines = test_in.strip().splitlines()
                    max_in_len = max((len(l) for l in input_lines), default=0)
                    in_width = max(30, max_in_len)
                    
                    hdr_in = " INPUT ".ljust(in_width, "─")
                    print(f"+──{hdr_in}──+")
                    for line in input_lines:
                        print(f"│  {line.ljust(in_width)}  │")
                    print(f"+──" + ("─" * in_width) + "──+\n")
                    
                    expected_str = test_out_expected[0] if test_out_expected else ""
                    print(_format_wa_diff(expected_str, proc.stdout))
        except subprocess.TimeoutExpired:
            print(
                f"⏰ \033[93mTime Limit Exceeded\033[0m - >{tl_sec * 1000:.0f}ms"
            )
        print("")

    print("=====================================")
    if passed == len(tests):
        print(f"🏆 \033[92mALL {passed}/{len(tests)} CASES PASSED!\033[0m")
        print(f"\n💡 Ready to submit! Use \033[96mcmd+enter\033[0m or:")
        print(f"   python3 {Path(APP_DIR).expanduser() / 'main.py'} submit \"{source_file}\"")
    else:
        print(
            f"💥 \033[91mFAILED: {len(tests) - passed}/{len(tests)} cases failed.\033[0m"
        )
    print("=====================================")


# ======================== Submit ========================


def _strip_test_block(source_code):
    """Remove embedded test cases and URL comment before submitting.
    Only strips the URL+test-block combo anchored together, not stray URL comments in user code."""
    code = source_code
    # Strip the URL line + test block as a combined unit (anchored together)
    code = re.sub(
        r"\n*(?://|#) URL: https?://\S+\n(?:(?:/\*|\"\"\") === TEST CASES ===.*?=== END TEST CASES === (?:\*/|\"\"\")\s*)",
        "",
        code,
        flags=re.DOTALL,
    )
    return code.rstrip() + "\n"


def _detect_platform(url):
    """Detect platform and extract submit_url + problem_code from a problem URL."""

    # Codeforces: contest/gym/group (supports subdomains like m.codeforces.com)
    m = re.search(
        r"(https?://(?:\w+\.)?codeforces\.com/.*(?:contest|gym)/\d+)/problem/(\w+)", url
    )
    if m:
        return {
            "platform": "codeforces",
            "submit_url": m.group(1) + "/submit",
            "problem_code": m.group(2),
        }

    # Codeforces: problemset
    m = re.search(r"(https?://(?:\w+\.)?codeforces\.com/problemset)/problem/(\d+)/(\w+)", url)
    if m:
        return {
            "platform": "codeforces",
            "submit_url": m.group(1) + "/submit",
            "problem_code": f"{m.group(2)}{m.group(3)}",
        }

    # AtCoder
    m = re.search(r"https?://atcoder\.jp/contests/(\w+)/tasks/(\w+)", url)
    if m:
        return {
            "platform": "atcoder",
            "submit_url": f"https://atcoder.jp/contests/{m.group(1)}/submit",
            "problem_code": m.group(2),  # e.g. abc452_c
        }

    return None



# ======================== Fill & Result JavaScript ========================
# These are shared across all browser engines — only the execution method differs.

def _build_cf_fill_js(code_b64, lang_id, problem_code):
    """Build the JavaScript that fills the Codeforces submit form."""
    return r"""(function() {
    try {
        var code = atob('__CODE_B64__');

        // Problem selection: text input (problemset) or dropdown (contest)
        var probInput = document.querySelector('input[name="submittedProblemCode"]');
        if (probInput) {
            probInput.value = '__PROBLEM_CODE__';
            probInput.dispatchEvent(new Event('input', {bubbles: true}));
        }
        var probSelect = document.querySelector('select[name="submittedProblemIndex"]');
        if (probSelect) {
            var target = '__PROBLEM_CODE__'.toUpperCase();
            var found = false;
            for (var i = 0; i < probSelect.options.length; i++) {
                var val = probSelect.options[i].value.toUpperCase();
                var txt = probSelect.options[i].text.toUpperCase().trim();
                if (val === target || txt.indexOf(target + " -") === 0 || txt.indexOf(target + ".") === 0 || txt === target) {
                    probSelect.value = probSelect.options[i].value;
                    found = true; break;
                }
            }
            if (found) probSelect.dispatchEvent(new Event('change', {bubbles: true}));
        }

        // Code injection
        var ta = document.getElementById('sourceCodeTextarea');
        if (ta) ta.value = code;
        try { var ed = document.querySelector('.ace_editor'); if (ed && typeof ace !== 'undefined') ace.edit(ed).setValue(code, -1); } catch(e) {}

        // Language selection
        var sel = document.querySelector('select[name="programTypeId"]');
        if (sel) {
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === '__LANG_ID__') { sel.value = '__LANG_ID__'; break; }
            }
            sel.dispatchEvent(new Event('change', {bubbles: true}));
        }

        // Submit
        var form = document.getElementById('submitForm') || document.querySelector('form.submit-form');
        if (!form) {
            var forms = document.querySelectorAll('form');
            for (var i = 0; i < forms.length; i++) {
                if ((forms[i].getAttribute('action') || '').indexOf('submit') > -1) { form = forms[i]; break; }
            }
        }
        if (form) {
            setTimeout(function() {
                var btn = form.querySelector('input[type="submit"], button[type="submit"], .submit');
                if (btn) btn.click();
                else form.submit();
            }, 800);
            return 'SUBMITTED';
        }
        return 'ERROR: Form not found.';
    } catch(e) { return 'ERROR: ' + e.message; }
})();""".replace("__CODE_B64__", code_b64).replace("__LANG_ID__", lang_id).replace("__PROBLEM_CODE__", problem_code.upper())


def _build_cf_result_js():
    """Build the JavaScript that reads the Codeforces verdict."""
    return r"""(function() {
    try {
        var url = document.location.href;
        var hasCap = false;

        if (document.title.indexOf('Just a moment') > -1 || document.title.indexOf('Attention Required') > -1) hasCap = true;
        var eSub = document.querySelector('.error.for__submittedProblemCode, .error.for__source');
        if (eSub && eSub.textContent.toLowerCase().indexOf('captcha') > -1) hasCap = true;

        if (url.indexOf('/submit') > -1) {
            var ws = document.querySelectorAll('.cf-turnstile, #turnstile-wrapper, .g-recaptcha');
            for (var i = 0; i < ws.length; i++) { if (ws[i].innerHTML.trim() !== '') hasCap = true; }
            if (document.querySelector('iframe[src*="captcha"], iframe[src*="challenge"], iframe[src*="turnstile"]')) hasCap = true;
        }

        if (hasCap) return 'CAPTCHA';

        if (document.readyState !== 'complete') return 'WAIT';

        if (eSub) return 'REJECTED: ' + eSub.textContent.trim();
        var rows = document.querySelectorAll('tr[data-submission-id]');
        if (rows.length > 0) {
            var cell = rows[0].querySelector('td.status-verdict-cell, td:nth-child(6), .submissionVerdictWrapper, .verdict-waiting, .verdict-accepted, .verdict-rejected');
            var vt = cell ? cell.textContent.replace(/\s+/g, ' ').trim() : '';
            if (!vt || vt.indexOf('Running') > -1 || vt.indexOf('queue') > -1 || vt.indexOf('Judging') > -1 || vt.indexOf('testing') > -1) {
                return 'RELOAD: ' + (vt || 'In queue');
            }
            return 'RESULT: ' + vt;
        }
        if (url.indexOf('/my') > -1 || url.indexOf('/status') > -1) return 'RELOAD: Waiting for submission';
        if (url.indexOf('/submit') > -1) return 'WAIT';
        return 'WAIT';
    } catch(e) { return 'WAIT'; }
})();"""


def _build_ac_fill_js(code_b64, lang_id, problem_code):
    """Build the JavaScript that fills the AtCoder submit form."""
    return r"""(function() {
    try {
        var code = atob('__CODE_B64__');

        // 1. Select the problem from the task dropdown
        var taskSelect = document.querySelector('select[name="data.TaskScreenName"]');
        if (taskSelect) {
            var target = '__PROBLEM_CODE__'.toLowerCase();
            for (var i = 0; i < taskSelect.options.length; i++) {
                if (taskSelect.options[i].value.toLowerCase() === target) {
                    taskSelect.value = taskSelect.options[i].value;
                    taskSelect.dispatchEvent(new Event('change', {bubbles: true}));
                    try { $(taskSelect).trigger('change'); } catch(e) {}
                    break;
                }
            }
        }

        // 2. Select language
        var langSelects = document.querySelectorAll('select[name="data.LanguageId"]');
        for (var s = 0; s < langSelects.length; s++) {
            var sel = langSelects[s];
            if (sel.offsetParent === null && langSelects.length > 1) continue;
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === '__LANG_ID__') {
                    sel.value = '__LANG_ID__';
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    try { $(sel).trigger('change'); } catch(e) {}
                    break;
                }
            }
        }

        // 3. Inject code into the editor
        setTimeout(function() {
            var ta = document.querySelector('#sourceCode, textarea[name="sourceCode"], textarea.plain-textarea');
            if (ta) { ta.value = code; ta.dispatchEvent(new Event('input', {bubbles: true})); }
            try {
                var editors = document.querySelectorAll('.ace_editor');
                if (editors.length > 0) {
                    var lastEd = editors[editors.length - 1];
                    if (typeof ace !== 'undefined') ace.edit(lastEd).setValue(code, -1);
                }
            } catch(e) {}

            // 4. Click submit
            var btn = document.querySelector('#submit, input[type="submit"], button[type="submit"]');
            if (btn) btn.click();
        }, 800);

        return 'SUBMITTED';
    } catch(e) { return 'ERROR: ' + e.message; }
})();""".replace("__CODE_B64__", code_b64).replace("__PROBLEM_CODE__", problem_code).replace("__LANG_ID__", lang_id)


def _build_ac_result_js():
    """Build the JavaScript that reads the AtCoder verdict."""
    return r"""(function() {
    try {
        if (document.readyState !== 'complete') return 'WAIT';
        var url = document.location.href;

        // Still on submit page? Check for error banner
        if (url.indexOf('/submit') > -1) {
            var errorBanner = document.querySelector('.alert-danger, .alert.alert-danger, div.error');
            if (errorBanner) return 'CAPTCHA';
            return 'WAIT';
        }

        // Check for submission table rows
        var rows = document.querySelectorAll('table.table-bordered tbody tr');
        if (rows.length > 0) {
            var verdictSpan = rows[0].querySelector('span.label');
            if (verdictSpan) {
                var vt = verdictSpan.textContent.trim();
                if (vt === 'WJ' || vt === 'WR' || vt.indexOf('Judging') > -1 || vt.indexOf('/') > -1) {
                    return 'RELOAD: ' + vt;
                }
                return 'RESULT: ' + vt;
            }
        }

        if (url.indexOf('/submissions') > -1) return 'RELOAD: Waiting for results';
        return 'WAIT';
    } catch(e) { return 'WAIT'; }
})();"""


# ======================== AppleScript Engine ========================

def _write_temp_js(content):
    """Write JS to a secure temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".js", prefix="cphelper_")
    os.write(fd, content.encode("utf-8"))
    os.close(fd)
    return path


def _run_applescript(applescript, fill_js, result_js=None):
    """Write temp files, run AppleScript, stream stderr live, return stdout."""
    fill_path = _write_temp_js(fill_js)
    result_path = _write_temp_js(result_js) if result_js else None

    # Patch AppleScript to use the temp file paths
    applescript = applescript.replace("__FILL_JS_PATH__", fill_path)
    if result_path:
        applescript = applescript.replace("__RESULT_JS_PATH__", result_path)

    as_fd, as_path = tempfile.mkstemp(suffix=".applescript", prefix="cphelper_")
    os.write(as_fd, applescript.encode("utf-8"))
    os.close(as_fd)

    try:
        proc = subprocess.Popen(
            ["osascript", as_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        for line in iter(proc.stderr.readline, ''):
            info = line.strip()
            if not info:
                continue
            if info.startswith("CAPTCHA:"):
                sys.stdout.write(f"\r\033[K🔒 \033[91m{info} — solve it, script will continue automatically\033[0m\n")
                sys.stdout.flush()
            elif info.startswith("RELOAD:") or info.startswith("WAIT"):
                sys.stdout.write(f"\r\033[K⏳ \033[93m{info}\033[0m")
                sys.stdout.flush()
            elif "RESULT" not in info and "REJECTED" not in info:
                sys.stdout.write(f"\r\033[K👀 \033[90m{info}\033[0m")
                sys.stdout.flush()
        stdout, _ = proc.communicate()
        sys.stdout.write("\n")
        return stdout.strip()
    finally:
        for f in [fill_path, result_path, as_path]:
            if f:
                try:
                    Path(f).unlink()
                except Exception:
                    pass


def _build_applescript_webkit(app_name, submit_url, ready_selector):
    """Build AppleScript for WebKit-based browsers (Safari, Orion).
    Uses 'do JavaScript ... in <tab>' syntax."""
    # Escape double quotes in ready_selector for AppleScript strings
    # AppleScript needs literal \" to represent a quote inside a string
    safe_selector = ready_selector.replace('"', '\\"')
    return f"""tell application "System Events" to set frontAppName to name of first application process whose frontmost is true
tell application "{app_name}"
    if (count of windows) is 0 then make new document with properties {{URL:"about:blank"}}
    tell window 1 to set submitTab to make new tab with properties {{URL:"{submit_url}"}}
    set captchaAlerted to false
    repeat 120 times
        delay 2
        try
            set pageCheck to do JavaScript "(function(){{
                var isC = false;
                if(document.title.indexOf('Just a moment')>-1 || document.title.indexOf('Attention Required')>-1) isC=true;
                if(isC) return 'CAPTCHA';
                if(document.querySelector('{safe_selector}')) return 'READY';
                return 'WAITING';
            }})()" in submitTab
            if pageCheck is "READY" then exit repeat
            if pageCheck is "CAPTCHA" then
                if captchaAlerted is false then
                    set captchaAlerted to true
                    tell application "{app_name}" to activate
                    log "CAPTCHA: Please solve the CAPTCHA in {app_name}..."
                end if
            end if
        on error errMsg
            if errMsg contains "not allowed" then return "ERROR: Enable 'Allow JavaScript from Apple Events' in {app_name}"
        end try
    end repeat
    delay 0.5
    set fillJS to read POSIX file "__FILL_JS_PATH__"
    set submitResult to do JavaScript fillJS in submitTab
    if submitResult does not start with "SUBMITTED" then return submitResult
    delay 4
    set resultJS to read POSIX file "__RESULT_JS_PATH__"
    set resultInfo to "UNKNOWN: Timed out"
    set resCaptchaAlerted to false
    repeat 120 times
        try
            set resultInfo to do JavaScript resultJS in submitTab
        on error
            set resultInfo to "WAIT"
        end try

        if resultInfo is "CAPTCHA" then
            if resCaptchaAlerted is false then
                set resCaptchaAlerted to true
                tell application "{app_name}" to activate
            end if
            log "CAPTCHA: Waiting for you to solve and resubmit..."
        else
            log resultInfo
        end if

        if resultInfo starts with "RESULT:" or resultInfo starts with "REJECTED:" then exit repeat
        if resultInfo starts with "RELOAD:" then
            do JavaScript "window.location.reload()" in submitTab
            delay 1
            repeat 30 times
                delay 1
                try
                    if (do JavaScript "document.readyState" in submitTab) is "complete" then exit repeat
                end try
            end repeat
        else
            delay 2
        end if
    end repeat
    close submitTab
end tell
tell application frontAppName to activate
return resultInfo"""


def _check_browser_available(browser_key=None):
    """Check if Safari is installed on macOS."""
    try:
        result = subprocess.run(
            ["osascript", "-e", f'tell application "System Events" to get name of every process whose background only is false'],
            capture_output=True, text=True, timeout=5
        )
        if "Safari" in result.stdout:
            return True
        # Check if Safari exists in /Applications
        app_path = "/Applications/Safari.app"
        if Path(app_path).exists():
            return True
        print(f"❌ Safari is not installed.")
        print(f"   Silent submission only works with Safari.")
        return False
    except Exception:
        return True  # Assume available if we can't check


# ======================== Submit Dispatchers ========================

def _submit_applescript(submit_url, fill_js, result_js, ready_selector):
    """Submit via Safari AppleScript."""
    app_name = "Safari"
    applescript = _build_applescript_webkit(app_name, submit_url, ready_selector)
    return _run_applescript(applescript, fill_js, result_js)


def _do_submit(submit_url, fill_js, result_js, platform, ready_selector):
    """Submit via Safari."""
    return _submit_applescript(submit_url, fill_js, result_js, ready_selector)


# ======================== Main Submit Command ========================

def submit_cmd(args):
    print("\033[H\033[J", end="")
    source_file = Path(args.file).resolve()
    if not source_file.exists():
        print(f"❌ Error: File {source_file} not found.")
        return

    source_code = source_file.read_text(encoding="utf-8")

    # Try to load URL from database
    url = None
    tests_path = get_testcases_path(source_file)
    if tests_path.exists():
        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
            url = data.get("url")
        except Exception:
            pass

    if not url:
        # Support both C++/Java style (// URL:) and Python style (# URL:)
        m_url = re.search(r"(?://|#) URL: (https?://\S+)", source_code)
        if not m_url:
            print(f"❌ Error: No URL comment found in the file (expected '// URL: ...' or '# URL: ...').")
            return
        url = m_url.group(1)
    info = _detect_platform(url)
    if not info:
        print(f"❌ Unsupported platform or URL format: {url}")
        print(f"   Supported: Codeforces, AtCoder")
        return

    clean_code = _strip_test_block(source_code)
    code_b64 = base64.b64encode(clean_code.encode("utf-8")).decode("ascii")
    platform = info["platform"]
    submit_url = info["submit_url"]
    problem_code = info["problem_code"]

    # Language info
    lang_key = get_saved_lang()
    lang = LANGUAGES[lang_key]
    if platform == "codeforces":
        lang_id, lang_name = lang["cf_id"], lang["cf_name"]
    elif platform == "atcoder":
        lang_id, lang_name = lang["ac_id"], lang["ac_name"]
    else:
        print(f"❌ Unknown platform: {platform}")
        return

    print(f"🚀 \033[94mSubmitting {source_file.name}...\033[0m")
    print(f"   Platform: {platform}")
    print(f"   Problem:  {problem_code}")
    print(f"   URL:      {submit_url}")
    print(f"   Lang:     {lang_name} ({lang_id})")
    print(f"   Browser:  Safari")

    # Check Safari availability
    if not _check_browser_available("safari"):
        return

    # Confirmation (skip with --yes flag)
    if not args.yes:
        print()
        try:
            import termios
            import tty

            sys.stdout.write("\033[93m⚠️  Press Enter to submit, Backspace to cancel: \033[0m")
            sys.stdout.flush()
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print()
            if ch in ("\x7f", "\x08", "\x1b"):
                print("❌ Submission cancelled.")
                return
        except (ImportError, OSError, io.UnsupportedOperation):
            # Non-TTY environment (e.g., piped input, IDE task runner)
            try:
                confirm = input("\033[93m⚠️  Type 'yes' to submit, anything else to cancel: \033[0m").strip().lower()
            except EOFError:
                print("❌ Submission cancelled (no interactive input available).")
                return
            if confirm != "yes":
                print("❌ Submission cancelled.")
                return

    print(f"\n\033[93mSafari will handle the submission.\033[0m")

    # Build JS and ready selector
    if platform == "codeforces":
        fill_js = _build_cf_fill_js(code_b64, lang_id, problem_code)
        result_js = _build_cf_result_js()
        ready_selector = 'select[name="programTypeId"]'
    elif platform == "atcoder":
        fill_js = _build_ac_fill_js(code_b64, lang_id, problem_code)
        result_js = _build_ac_result_js()
        ready_selector = 'select[name="data.TaskScreenName"]'

    # Submit
    res = _do_submit(submit_url, fill_js, result_js, platform, ready_selector)

    # Print verdict
    print("\n==============================")
    if not res:
        print("\u26a0\ufe0f  \033[93mNo response from browser. Safari may have been closed or the tab crashed.\033[0m")
    else:
        v = res.lower()
        if res.startswith("RESULT:"):
            if "accepted" in v or ": ac" in v:
                print(f"\u2705 \033[92m{res}\033[0m")
            elif any(x in v for x in ["wrong", "time limit", "memory limit", "runtime error", "compilation error", ": wa", ": tle", ": mle", ": re", ": ce"]):
                print(f"\u274c \033[91m{res}\033[0m")
            else:
                print(f"\u26a0\ufe0f  \033[93m{res}\033[0m")
        elif "REJECTED" in res or "ERROR" in res:
            print(f"\u274c \033[91m{res}\033[0m")
        else:
            print(f"\u26a0\ufe0f  {res}")
    print("==============================")


# ======================== Status Command ========================

def status_cmd(args):
    """Check listener status and current config."""
    # Check if listener is running
    pid_path = Path(APP_DIR).expanduser() / "listener.pid"
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)  # Check if alive
            print(f"✅ Listener is running (PID {pid})")
        except (ValueError, ProcessLookupError):
            print("❌ No listener is running (stale PID file)")
            pid_path.unlink(missing_ok=True)
        except PermissionError:
            print(f"⚠️  PID {pid} exists but belongs to another user. Stale PID file?")
            pid_path.unlink(missing_ok=True)
    else:
        print("❌ No listener is running.")

    # Show current config
    cfg = _load_config()
    lang = cfg.get("lang", DEFAULT_LANG)
    browser = cfg.get("browser", DEFAULT_BROWSER)
    template = cfg.get("template", DEFAULT_TEMPLATE)
    template_name = "boilerplate.cpp" if template == "boilerplate" else "Zed snippets (cpp.json)"
    print(f"\n📋 Config ({CONFIG_PATH}):")
    print(f"   Language:  {lang}")
    print(f"   Browser:   {browser}")
    print(f"   Template:  {template_name}")
    if template_name=="Zed snippets (cpp.json)":
        print(f"   Snippets:  {cfg.get('snippet_name', 'boilerplate')}")
    


# ======================== Add Test Command ========================

def _read_multiline(prompt):
    """Read multi-line input from the user. Empty line (double Enter) to finish."""
    print(prompt)
    lines = []
    try:
        while True:
            line = input()
            if line == "" and lines:  # Empty line after content = done
                break
            if line == "" and not lines:
                break  # Immediate Enter = empty input
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    return "\n".join(lines)


def add_test_cmd(args):
    """Add a custom test case to a source file interactively using console prompt (TUI)."""
    source_file = Path(args.file).resolve()
    if not source_file.exists():
        print(f"❌ Error: File {source_file} not found.")
        return

    print(f"\n📝 Adding custom test case to \033[96m{source_file.name}\033[0m")
    print("   (Type 'q', 'exit', or press Ctrl+C at any prompt to cancel)")

    try:
        test_input = _read_multiline_cancelable("\033[1mEnter input\033[0m (empty line to finish):")
        test_output = _read_multiline_cancelable("\n\033[1mEnter expected output\033[0m (empty line to finish, or Enter immediately to skip):")
    except CancelledException:
        print("\n⚠️  Add case cancelled. No changes were made.")
        return

    # Save to JSON database
    tests_path = get_testcases_path(source_file)
    data = {}
    if tests_path.exists():
        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if "tests" not in data:
        data["tests"] = []

    data["tests"].append({
        "input": test_input,
        "output": test_output
    })

    try:
        tests_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        num_cases = len(data["tests"])
        print(f"\n✅ Test cases updated! Total cases: {num_cases}")
    except Exception as e:
        print(f"❌ Failed to save test cases: {e}")


# ======================== Send REPL Command ========================

def send_repl_cmd(args):
    """Sends a command to the active REPL shell via HTTP."""
    action = args.action
    file_arg = args.file if hasattr(args, "file") and args.file else ""
    import urllib.request
    import urllib.parse
    
    # URL encode parameters
    params = {"action": action}
    if file_arg:
        params["file"] = str(Path(file_arg).resolve())
        
    query = urllib.parse.urlencode(params)
    url = f"http://localhost:{PORT}/command?{query}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as response:
            if response.status == 200:
                pass
    except Exception as e:
        print(f"❌ Failed to send command '{action}' to REPL listener: {e}")
        print("   Make sure the listener is running (run task: CP: Start Listener)")


# ======================== Main ========================
def main():
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description="Zed CP Helper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Listen
    listen_parser = subparsers.add_parser(
        "listen", help="Start Competitive Companion listener"
    )
    listen_parser.add_argument(
        "directory", default=".", nargs="?", help="Directory to save problems to"
    )

    # Run
    run_parser = subparsers.add_parser("run", help="Compile and run tests")
    run_parser.add_argument("file", help="Source code file")

    # Submit
    submit_parser = subparsers.add_parser("submit", help="Submit to Codeforces / AtCoder")
    submit_parser.add_argument("file", help="Source code file")
    submit_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # Add Test
    add_test_parser = subparsers.add_parser("add_test", help="Add a custom test case interactively")
    add_test_parser.add_argument("file", help="Source code file")

    # Send REPL command
    send_parser = subparsers.add_parser("send_repl", help="Send command to running REPL")
    send_parser.add_argument("action", help="Command to send (r, s, a, e, v)")
    send_parser.add_argument("file", nargs="?", default="", help="Active source file path")



    # Set Language
    lang_parser = subparsers.add_parser("set_lang", help="Set language for run/submit")
    lang_parser.add_argument("lang", choices=LANGUAGES.keys(), help="Language to use")

    # Set Browser
    browser_parser = subparsers.add_parser("set_browser", help="Set browser for submissions")
    browser_parser.add_argument("browser", help="Browser (only 'safari' supported)")

    # Set Template
    template_parser = subparsers.add_parser("set_template", help="Set template source (boilerplate.cpp or Zed snippets)")
    template_parser.add_argument("template", choices=["boilerplate", "zed_snippets"], help="Template source")
    template_parser.add_argument("snippet_name", nargs="?", default=None, help="Write snippet name for Zed snippets")

    # Status
    subparsers.add_parser("status", help="Check listener status and current config")

    args = parser.parse_args()

    if args.command == "listen":
        listen_cmd(args)
    elif args.command == "run":
        run_cmd(args)
    elif args.command == "submit":
        submit_cmd(args)
    elif args.command == "add_test":
        add_test_cmd(args)
    elif args.command == "send_repl":
        send_repl_cmd(args)

    elif args.command == "set_lang":
        set_lang_cmd(args)
    elif args.command == "set_browser":
        set_browser_cmd(args)
    elif args.command == "set_template":
        set_template_cmd(args)
    elif args.command == "status":
        status_cmd(args)


if __name__ == "__main__":
    main()
