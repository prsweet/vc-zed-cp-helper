import argparse
import base64
import http.server
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
        "compile": ["g++-15", "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wshadow"],
        "cf_id": "89",
        "cf_name": "GNU G++20 13.2 (64 bit)",
        "ac_id": "5001",
        "ac_name": "C++ 20 (gcc 12.2)",
    },
    "cpp23": {
        "compile": ["g++-15", "-std=c++23", "-O2", "-Wall", "-Wextra", "-Wshadow"],
        "cf_id": "91",
        "cf_name": "GNU G++23 14.2 (64 bit, msys2)",
        "ac_id": "5002",
        "ac_name": "C++ 23 (gcc 12.2)",
    },
    "cpp17": {
        "compile": ["g++-15", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Wshadow"],
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

# Browser profiles: app_name, engine (webkit/chromium), type (applescript)
BROWSERS = {
    "safari": {"app_name": "Safari", "engine": "webkit", "type": "applescript"},
    "brave":  {"app_name": "Brave Browser", "engine": "chromium", "type": "applescript"},
    "chrome": {"app_name": "Google Chrome", "engine": "chromium", "type": "applescript"},
    "orion":  {"app_name": "Orion", "engine": "webkit", "type": "applescript"},
}


def _load_config():
    """Load config.json, returning a dict."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
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
    if browser in BROWSERS:
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
    if browser not in BROWSERS:
        print(f"❌ Unknown browser '{browser}'. Available: {', '.join(BROWSERS.keys())}")
        print(f"   Note: Put quotes around names with spaces in tasks.json (e.g. 'Brave Browser')")
        return
    cfg = _load_config()
    cfg["browser"] = browser
    _save_config(cfg)
    b = BROWSERS[browser]
    print(f"✅ Browser set to \033[92m{b['app_name']}\033[0m")
    print(f"   Engine:    {b['engine']}")
    print(f"\n   Saved to {CONFIG_PATH}")
    print("   All future Submit tasks will use this browser.")


def set_template_cmd(args):
    """Save the template source to config."""
    template = args.template
    if template not in ("boilerplate", "zed_snippets"):
        print(f"❌ Unknown template source '{template}'. Use 'boilerplate' or 'zed_snippets'.")
        return
    cfg = _load_config()
    cfg["template"] = template
    _save_config(cfg)

    if template == "boilerplate":
        print(f"✅ Template source set to \033[92mboilerplate.cpp\033[0m")
        print(f"   Reading from: {Path(APP_DIR).expanduser() / 'boilerplate.cpp'}")
    else:
        print(f"✅ Template source set to \033[92mZed snippets\033[0m")
        print(f"   Reading from: ~/.config/zed/snippets/c++.json")
    print(f"\n   Saved to {CONFIG_PATH}")


def is_folder_open_in_zed(folder_path):
    """Checks if a Zed process is currently managing this folder path."""
    try:
        output = subprocess.check_output(["ps", "aux"]).decode("utf-8")
        return str(folder_path) in output and "Zed" in output
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
    project_folder = get_project_folder(source_file)
    compiled_dir = project_folder / ".Compiled"
    compiled_dir.mkdir(exist_ok=True)
    return compiled_dir / Path(source_file).stem


# ======================== Listener ========================
class CompanionHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode("utf-8"))
        self.server.foc_process_problem(data)
        self.send_response(200)
        self.end_headers()


def process_problem(data, active_folder):
    problem_name = data.get("name", "problem")
    safe_filename = problem_name.replace(" ", "_").replace(".", "_", 1)
    safe_filename = re.sub(r"[^\w_]", "", safe_filename)
    file_name = f"{safe_filename}.cpp"
    file_path = active_folder / file_name

    print(f"\n[Companion] Received problem: {problem_name}")
    print(f"[Companion] Writing to: {file_path}")

    # Write template if file doesn't exist
    if not file_path.exists():
        content = ""
        cfg = _load_config()
        template_source = cfg.get("template", DEFAULT_TEMPLATE)

        if template_source == "zed_snippets":
            # Read from Zed's cpp.json snippets (useful for multi-IDE sync via symlink)
            zed_snippets = Path("~/.config/zed/snippets/c++.json").expanduser()
            if zed_snippets.exists():
                try:
                    snippet_data = json.loads(zed_snippets.read_text(encoding="utf-8"))
                    # Look for snippet named "boilerplate" (case-insensitive)
                    template_key = None
                    for key in snippet_data:
                        if key.lower() == "boilerplate":
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
                        print(f"[Companion] No snippet named 'boilerplate' found in {zed_snippets}")
                except Exception as e:
                    print(f"[Companion] Failed to parse Zed snippets: {e}")

        # Default: read from APP_DIR/boilerplate.cpp
        if not content:
            boilerplate = Path(APP_DIR).expanduser() / "boilerplate.cpp"
            if boilerplate.exists():
                try:
                    content = boilerplate.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"[Companion] Failed to read boilerplate: {e}")

        file_path.write_text(content, encoding="utf-8")

    # Tests blocks & Meta extraction
    url = data.get("url", "")
    tests_str = f"\n\n// URL: {url}\n/* === TEST CASES ===\n"
    for i, test in enumerate(data.get("tests", [])):
        tests_str += f"[Case {i + 1}]\n"
        tests_str += f"Input:\n{test.get('input', '').strip()}\n"
        tests_str += f"Expected:\n{test.get('output', '').strip()}\n\n"
    tests_str += "=== END TEST CASES === */\n"

    # Append tests to .cpp snippet
    original_code = file_path.read_text(encoding="utf-8")

    # Strip old test cases if they exist
    if "// URL: " in original_code:
        original_code = re.sub(r"// URL: .*?\n", "", original_code)
    if "/* === TEST CASES ===" in original_code:
        original_code = re.sub(
            r"/\* === TEST CASES ===.*?=== END TEST CASES === \*/\s*",
            "",
            original_code,
            flags=re.DOTALL,
        )

    new_code = original_code.rstrip() + tests_str
    file_path.write_text(new_code, encoding="utf-8")
    print(
        f"[Companion] Saved {len(data.get('tests', []))} tests natively in the .cpp file."
    )
    print(f"[Companion] Ready in Zed! Open {file_path}")

    return file_path


def force_kill_process_on_port(port):
    """Finds and kills any process listening on the given port (macOS/Linux)."""
    if sys.platform not in ("darwin", "linux"):
        return
    command = f"lsof -ti tcp:{port}"
    try:
        pid = subprocess.check_output(command, shell=True).decode().strip()
        if pid:
            print(f"[Listen] Port {port} is in use by PID {pid}. Terminating it...")
            import signal

            os.kill(int(pid), signal.SIGKILL)
            time.sleep(0.1)  # Give the OS a moment to release the port
    except subprocess.CalledProcessError:
        pass  # Port is not in use


def get_active_zed_folder():
    """Uses AppleScript and lsof to magically find Zed's active absolute project directory."""
    if sys.platform != "darwin":
        return None
    try:
        title = (
            subprocess.check_output(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get name of front window of process "Zed"',
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


def listen_cmd(args):
    # Determine the target directory: defaults to current directory (".")
    target_dir = Path(args.directory).resolve()

    force_kill_process_on_port(PORT)

    # Write PID file
    pid_path = Path(APP_DIR).expanduser() / "listener.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    print(f"[Listen] Starting Competitive Companion listener on port {PORT}...")
    print(f"[Listen] Saving problems natively to: {target_dir}")
    print("[Listen] Waiting for requests from browser extension...")

    # Pre-create the directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("", PORT), CompanionHandler)

    def handle_problem(data):
        file_path = process_problem(data, target_dir)
        if file_path:
            import shutil

            zed_bin = shutil.which("zed") or "/usr/local/bin/zed"
            # Handle Zed Logic: Open folder if missing
            if not is_folder_open_in_zed(target_dir):
                subprocess.run([zed_bin, str(target_dir)])
                time.sleep(1)  # Brief pause to let Zed initialize the workspace

            # '-a' adds the file to the active or nearest workspace cleanly
            subprocess.run([zed_bin, "-a", str(file_path)])

    server.foc_process_problem = handle_problem

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Listen] Server stopped.")
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
    """Parses the block comment to extract test cases"""
    m = re.search(
        r"/\* === TEST CASES ===(.*?)=== END TEST CASES === \*/", code, re.DOTALL
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


def compile_and_get_run_cmd(source_file, lang_key):
    """Returns the command list to execute the program, or None on failure."""
    lang = LANGUAGES[lang_key]

    # Interpreted languages (python, etc.)
    if "run" in lang:
        return lang["run"] + [str(source_file)]

    # Compiled languages
    bin_path = get_binary_path(source_file)
    compile_cmd = lang["compile"] + [str(source_file), "-o", str(bin_path)]

    # Java special case
    if "run_compiled" in lang:
        compile_cmd = lang["compile"] + [str(source_file)]

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

    if "run_compiled" in lang:
        return lang["run_compiled"] + [str(source_file.parent), source_file.stem]
    return [str(bin_path)]


def run_cmd(args):
    source_file = Path(args.file).resolve()
    if not source_file.exists():
        print(f"❌ Error: File {source_file} not found.")
        return

    lang_key = get_saved_lang()
    print(f"🔧 \033[90mLanguage: {lang_key}\033[0m\n")

    code = source_file.read_text(encoding="utf-8")
    tests = extract_tests_from_code(code)

    if not tests:
        print("⚠️  No tests found. Running binary manually.")
        run_cmd_list = compile_and_get_run_cmd(source_file, lang_key)
        if run_cmd_list:
            subprocess.run(run_cmd_list)
        return

    run_cmd_list = compile_and_get_run_cmd(source_file, lang_key)
    if not run_cmd_list:
        return

    print(f"🧪 Running {len(tests)} test cases...\n")
    passed = 0

    # Store results to print a summary
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
                timeout=TIME_LIMIT_SEC,
            )
            t1 = time.time()
            elapsed_ms = (t1 - t0) * 1000

            # --- ALWAYS FETCH AND DISCLOSE INTERNAL LOGS IMMEDIATELY ---
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
                    print(f"❌ \033[91mWrong Answer\033[0m - {elapsed_ms:.0f}ms")
                    print("\n\033[1mInput:\033[0m")
                    print(test_in.strip())
                    print("\n\033[1mExpected Output:\033[0m")
                    print(test_out_expected[0].strip() if test_out_expected else "")
                    print("\n\033[1mYour Output:\033[0m")
                    print(proc.stdout.strip())
        except subprocess.TimeoutExpired:
            print(
                f"⏰ \033[93mTime Limit Exceeded\033[0m - >{TIME_LIMIT_SEC * 1000:.0f}ms"
            )
        print("")

    print("=====================================")
    if passed == len(tests):
        print(f"🏆 \033[92mALL {passed}/{len(tests)} CASES PASSED!\033[0m")
    else:
        print(
            f"💥 \033[91mFAILED: {len(tests) - passed}/{len(tests)} cases failed.\033[0m"
        )
    print("=====================================")


# ======================== Submit ========================


def _strip_test_block(source_code):
    """Remove embedded test cases and URL comment before submitting."""
    code = source_code
    if "// URL: " in code:
        code = re.sub(r"// URL: .*?\n", "", code)
    if "/* === TEST CASES ===" in code:
        code = re.sub(
            r"/\* === TEST CASES ===.*?=== END TEST CASES === \*/\s*",
            "",
            code,
            flags=re.DOTALL,
        )
    return code.rstrip() + "\n"


def _detect_platform(url):
    """Detect platform and extract submit_url + problem_code from a problem URL."""

    # Codeforces: contest/gym/group
    m = re.search(
        r"(https?://codeforces\.com/.*(?:contest|gym)/\d+)/problem/(\w+)", url
    )
    if m:
        return {
            "platform": "codeforces",
            "submit_url": m.group(1) + "/submit",
            "problem_code": m.group(2),
        }

    # Codeforces: problemset
    m = re.search(r"(https?://codeforces\.com/problemset)/problem/(\d+)/(\w+)", url)
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
                if(document.querySelector('{ready_selector}')) return 'READY';
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


def _build_applescript_chromium(app_name, submit_url, ready_selector):
    """Build AppleScript for Chromium-based browsers (Chrome, Brave).
    Uses 'execute javascript ... in active tab of window 1' syntax."""
    return f"""tell application "System Events" to set frontAppName to name of first application process whose frontmost is true
tell application "{app_name}"
    if (count of windows) is 0 then make new window
    tell window 1 to set submitTab to make new tab with properties {{URL:"{submit_url}"}}
    set captchaAlerted to false
    repeat 120 times
        delay 2
        try
            tell submitTab
                set pageCheck to execute javascript "(function(){{
                    var isC = false;
                    if(document.title.indexOf('Just a moment')>-1 || document.title.indexOf('Attention Required')>-1) isC=true;
                    if(isC) return 'CAPTCHA';
                    if(document.querySelector('{ready_selector}')) return 'READY';
                    return 'WAITING';
                }})()"
            end tell
            if pageCheck is "READY" then exit repeat
            if pageCheck is "CAPTCHA" then
                if captchaAlerted is false then
                    set captchaAlerted to true
                    tell application "{app_name}" to activate
                    log "CAPTCHA: Please solve the CAPTCHA in {app_name}..."
                end if
            end if
        on error errMsg
            if errMsg contains "not allowed" then return "ERROR: Enable 'Allow JavaScript from Apple Events' in {app_name} (View > Developer)"
        end try
    end repeat
    delay 0.5
    set fillJS to read POSIX file "__FILL_JS_PATH__"
    tell submitTab
        set submitResult to execute javascript fillJS
    end tell
    if submitResult does not start with "SUBMITTED" then return submitResult
    delay 4
    set resultJS to read POSIX file "__RESULT_JS_PATH__"
    set resultInfo to "UNKNOWN: Timed out"
    set resCaptchaAlerted to false
    repeat 120 times
        try
            tell submitTab
                set resultInfo to execute javascript resultJS
            end tell
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
            tell submitTab
                execute javascript "window.location.reload()"
            end tell
            delay 1
            repeat 30 times
                delay 1
                try
                    tell submitTab
                        set rs to execute javascript "document.readyState"
                    end tell
                    if rs is "complete" then exit repeat
                end try
            end repeat
        else
            delay 2
        end if
    end repeat
    delay 0.5
    try
        close submitTab
    end try
end tell
tell application frontAppName to activate
return resultInfo"""


def _check_browser_available(browser_key):
    """Check if the selected browser is installed on macOS."""
    b = BROWSERS[browser_key]
    app_name = b["app_name"]
    try:
        result = subprocess.run(
            ["osascript", "-e", f'tell application "System Events" to get name of every process whose background only is false'],
            capture_output=True, text=True, timeout=5
        )
        if app_name in result.stdout:
            return True
        # Check if app exists in /Applications
        app_path = f"/Applications/{app_name}.app"
        if Path(app_path).exists():
            return True
        print(f"❌ Browser '{app_name}' is not installed.")
        print(f"   Install it or switch with: python3 main.py set_browser safari")
        return False
    except Exception:
        return True  # Assume available if we can't check


# ======================== Submit Dispatchers ========================

def _submit_applescript(submit_url, fill_js, result_js, browser_key, ready_selector):
    """Submit via AppleScript (Safari, Chrome, Brave, Orion)."""
    b = BROWSERS[browser_key]
    app_name = b["app_name"]
    engine = b["engine"]

    if engine == "webkit":
        applescript = _build_applescript_webkit(app_name, submit_url, ready_selector)
    elif engine == "chromium":
        applescript = _build_applescript_chromium(app_name, submit_url, ready_selector)
    else:
        print(f"❌ Unknown engine type: {engine}")
        return "ERROR: Unknown browser engine"

    return _run_applescript(applescript, fill_js, result_js)


def _do_submit(submit_url, fill_js, result_js, platform, browser_key, ready_selector):
    """Route submission to the correct browser engine."""
    b = BROWSERS[browser_key]
    if b["type"] == "applescript":
        return _submit_applescript(submit_url, fill_js, result_js, browser_key, ready_selector)
    else:
        return "ERROR: Unknown browser type"


# ======================== Main Submit Command ========================

def submit_cmd(args):
    source_file = Path(args.file).resolve()
    if not source_file.exists():
        print(f"❌ Error: File {source_file} not found.")
        return

    source_code = source_file.read_text(encoding="utf-8")
    m_url = re.search(r"// URL: (https?://\S+)", source_code)
    if not m_url:
        print(f"❌ Error: No // URL: comment found in the file.")
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

    # Browser info
    browser_key = get_saved_browser()
    browser_name = BROWSERS[browser_key]["app_name"]

    print(f"🚀 \033[94mSubmitting {source_file.name}...\033[0m")
    print(f"   Platform: {platform}")
    print(f"   Problem:  {problem_code}")
    print(f"   URL:      {submit_url}")
    print(f"   Lang:     {lang_name} ({lang_id})")
    print(f"   Browser:  {browser_name}")

    # Check browser availability
    if not _check_browser_available(browser_key):
        return

    # Confirmation
    print()
    sys.stdout.write("\033[93m⚠️  Press Enter to submit, Backspace to cancel: \033[0m")
    sys.stdout.flush()
    import termios
    import tty

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

    print(f"\n\033[93m{browser_name} will handle the submission.\033[0m")

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
    res = _do_submit(submit_url, fill_js, result_js, platform, browser_key, ready_selector)

    # Print verdict
    print("\n==============================")
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
    print(f"   Browser:   {browser} ({BROWSERS.get(browser, {}).get('app_name', '?')})")
    print(f"   Template:  {template_name}")


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
    run_parser.add_argument("file", help="Source code file (.cpp)")

    # Submit
    submit_parser = subparsers.add_parser("submit", help="Submit to Codeforces / AtCoder")
    submit_parser.add_argument("file", help="Source code file (.cpp)")

    # Set Language
    lang_parser = subparsers.add_parser("set_lang", help="Set C++ standard for run/submit")
    lang_parser.add_argument("lang", choices=LANGUAGES.keys(), help="C++ standard to use")

    # Set Browser
    browser_parser = subparsers.add_parser("set_browser", help="Set browser for submissions")
    browser_parser.add_argument("browser", choices=BROWSERS.keys(), help="Browser to use")

    # Set Template
    template_parser = subparsers.add_parser("set_template", help="Set template source (boilerplate.cpp or Zed snippets)")
    template_parser.add_argument("template", choices=["boilerplate", "zed_snippets"], help="Template source")

    # Status
    subparsers.add_parser("status", help="Check listener status and current config")

    args = parser.parse_args()

    if args.command == "listen":
        listen_cmd(args)
    elif args.command == "run":
        run_cmd(args)
    elif args.command == "submit":
        submit_cmd(args)
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
