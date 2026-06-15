# Zed CP Helper

A fully automated, native background tool for managing competitive programming workflows seamlessly in the [Zed](https://zed.dev/) editor on macOS.

This tool runs entirely locally as a Python script. It intercepts problem data from the [Competitive Companion](https://github.com/jmerle/competitive-companion) browser extension, auto-creates your source files with problem-specific template and test cases, allows you to instantly compile and run tests in Zed, and even fully automates submissions to Codeforces and AtCoder using Safari.

## Features

- 📥 **Auto-Parses Problems**: Captures problem requirements and sample test cases via Competitive Companion.
- 🏗️ **Boilerplate Template Injection**: Injects your C++ template cleanly (no test cases comments in code; test cases are kept in a separate database under `.testcases/`).
- 🚀 **Auto-Run Test Cases**: Compiles and runs all sample and custom test cases locally from the JSON database with precise execution time per case.
- 🤖 **Zero-Click Submissions**: Submits directly to Codeforces and AtCoder in the background by automating Safari.
- 📡 **Live Verdict Polling**: Shows live Codeforces status (In queue, Judging, AC, WA) directly in the terminal without ever looking at the browser.
- 🧱 **No WASM/Sandboxing Limits**: Standard Zed CP extensions have network/sandbox limits. This native approach has zero limits.

## Prerequisites

- **macOS** (Relies on AppleScript to interact with Safari)
- **Python 3.8+**
- **Safari** with **"Allow JavaScript from Apple Events"** enabled:
  - Safari → Preferences → Advanced → Check "Show Develop menu"
  - Then Develop → Allow JavaScript from Apple Events
- **[Zed Code Editor](https://zed.dev/)**
- **C++ Compiler** (e.g., `g++` installed via Homebrew)
- **[Competitive Companion](https://github.com/jmerle/competitive-companion)** browser extension for Chrome/Firefox/Safari/Brave.

### Why Safari Only?

Submission automation requires the browser to run JavaScript in the background without bringing the window to the foreground. **Only Safari supports this** via AppleScript's `do JavaScript ... in tab` command. Other browsers (Brave, Chrome, Orion) require the window to be foregrounded, which interrupts your workflow.

## Installation

### 1. Place the Script
By default (and recommended), the script and its configurations live in `~/.vc-zed-cp-helper/` in the main script.

```bash
cd ~ && git clone https://github.com/prsweet/vc-zed-cp-helper.git .vc-zed-cp-helper # OR your directory
```

*(Note: If you want to install it to a different custom folder or path, you must edit the `APP_DIR = "~/.vc-zed-cp-helper"` variable at the top of `main.py` to match your desired path!)*

### 2. Add Custom Code Template (Optional)
Put your default template inside the app directory at `~/.vc-zed-cp-helper/`:
- C++ → `boilerplate.cpp`
- Python → `boilerplate.py`
- Java → `boilerplate.java`

If the language-specific file doesn't exist, it falls back to `boilerplate.cpp`. If neither exists, new files will be empty before injecting tests.

### 3. Setup Zed Tasks
Open your Zed tasks file (`~/.config/zed/tasks.json`) and add the following tasks with your `APP_DIR` to integrate smoothly with Zed's task runner (`cmd+shift+R`):

```json
[
  {
    "label": "CP: Start Listener (Current Folder)",
    "command": "python3 ~/.vc-zed-cp-helper/main.py listen",
    "use_new_terminal": true,
    "allow_concurrent_runs": false,
    "hide": "never",
    "reveal_target": "center"
  },
  {
    "label": "CP: Run Tests",
    "command": "python3 ~/.vc-zed-cp-helper/main.py send_repl r \"${ZED_FILE}\"",
    "use_new_terminal": false,
    "allow_concurrent_runs": false,
    "reveal": "never",
    "hide": "always"
  },
  {
    "label": "CP: Submit to Codeforces / AtCoder",
    "command": "python3 ~/.vc-zed-cp-helper/main.py submit \"${ZED_FILE}\"",
    "use_new_terminal": true,
    "allow_concurrent_runs": true,
    "reveal": "always"
  },
  {
    "label": "CP: Set Language [cpp23]",
    "command": "python3 ~/.vc-zed-cp-helper/main.py set_lang cpp23",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Set Template [boilerplate]",
    "command": "python3 ~/.vc-zed-cp-helper/main.py set_template boilerplate",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Status",
    "command": "python3 ~/.vc-zed-cp-helper/main.py status",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Add Custom Test Case",
    "command": "python3 ~/.vc-zed-cp-helper/main.py send_repl a \"${ZED_FILE}\"",
    "use_new_terminal": false,
    "allow_concurrent_runs": false,
    "reveal": "never",
    "hide": "always"
  },
  {
    "label": "CP: Edit Test Cases",
    "command": "python3 ~/.vc-zed-cp-helper/main.py send_repl e \"${ZED_FILE}\"",
    "use_new_terminal": false,
    "allow_concurrent_runs": false,
    "reveal": "never",
    "hide": "always"
  }
]
```

### 4. Basic Keymap
Below is the optimized keymap. Add these to your user keymap file (`~/.config/zed/keymap.json`) to integrate shortcuts cleanly:

```json
[
  {
    "context": "Editor",
    "bindings": {
      "cmd-'": ["task::Spawn", { "task_name": "CP: Run Tests" }],
      "cmd-enter": ["task::Spawn", { "task_name": "CP: Submit to Codeforces / AtCoder" }],
      "cmd-r": ["workspace::SendKeystrokes", "cmd-alt-shift-r cmd-\\"],
      "cmd-alt-a": ["workspace::SendKeystrokes", "cmd-k cmd-right a enter"],
      "cmd-alt-e": ["task::Spawn", { "task_name": "CP: Edit Test Cases" }]
    }
  },
  {
    "context": "Terminal",
    "bindings": {
      "shift-enter": [
        "terminal::SendText",
        "\u001b\r"
      ]
    }
  },
  {
    "context": "Workspace",
    "bindings": {
      "cmd-alt-shift-r": ["task::Spawn", { "task_name": "CP: Start Listener (Current Folder)" }]
    }
  }
]
```

*(Note: `cmd-r` in Editor mode triggers the split-pane workaround by calling the Workspace-level listener start `cmd-alt-shift-r` and then splitting the pane to the right using `cmd-\\`).*

---

## Usage

### 1. Starting the Listener
At the start of your competitive programming session, press **`cmd-r`**.
* This launches the unified, persistent interactive REPL shell as an editor tab. Drag this tab to the right side of the screen to arrange your workspace as a split editor pane layout (Code on the left, REPL on the right).
* Click the green `+` on the **Competitive Companion** extension in your browser when viewing a problem page.
* Zed will automatically save the problem, compile config, and create a clean `.cpp` source file (no block comments at the bottom).
* Sample test cases are stored in `.testcases/problem_name.json`.

### 2. Set Language
You only have to do this once. Run the **CP: Set Language [cpp23]** task. Every "Run" or "Submit" task will use this language.
*(You can press **TAB** before hitting Enter in the task selector to modify `cpp23` to `cpp20`, `cpp17`, `python`, `java`, etc.)*

### 3. Set Template Source
By default, the tool injects the template from `~/.vc-zed-cp-helper/boilerplate.cpp` (or corresponding language extension). If you prefer to use your native Zed snippets instead, run the **CP: Set Template [boilerplate]** task.
*(You can press **TAB** before hitting Enter in the task selector to modify the argument to `zed_snippets` instead of `boilerplate`.)*

### 4. Testing
Solve your problem and save the file. Press **`cmd-'`** to run tests.
* The script sends the command to your active REPL pane on the right without opening new tabs.
* If no test cases are found yet, it will print instructions on how to fetch them using the browser extension.

### 5. Direct Submissions
Press **`cmd-enter`** to submit the solution.
* This automatically spawns a separate terminal tab (`python3 main.py submit`) for the submission, allowing you to submit and poll multiple submissions concurrently without blocking your main REPL.
* **For Codeforces:** It tracks the submission live and prints `WJ`, `Running on test 5`, etc., until eventually showing `✅ ACCEPTED` or `❌ WRONG ANSWER` directly in the terminal tab.

### 6. Interactive REPL Commands
Inside the active REPL terminal pane on the right, you can also type commands directly:
* `r` or `run` - Compile and run tests.
* `a` or `add` - Add custom test cases interactively in the console.
* `e` or `edit` - Edit existing test cases using a temporary tab.
* `v` or `view` - View current test cases.
* `s` or `submit` - Submit solution to Codeforces/AtCoder.
* `h` or `help` - Show help.


---

## Dealing with CAPTCHAs
Platforms like AtCoder, and occasionally Codeforces (via Cloudflare), heavily use invisible CAPTCHAs.
If the automation hits a CAPTCHA wall:
1. The terminal output will alert you: `🔒 CAPTCHA: Please solve the CAPTCHA in Safari`.
2. Safari will be brought to the foreground automatically on the submit page.
3. Once you manually click the CAPTCHA (and/or submit), the script detects the form change, and automatically resumes live verdict polling in your Zed terminal!

## Supporting New Languages
To modify compiler flags or add custom languages (e.g. Rust), just edit the `LANGUAGES` mapping inside `main.py`. You'll need the `cf_id` (Codeforces Language ID) or `ac_id` (AtCoder Language ID) depending on the platform.

---

## Keeping Templates in Sync Across IDEs (Zed + VS Code)

If you use both **Zed** (with this tool) and **VS Code** (with CPH or similar), you can keep your template consistent across both IDEs by using a symlink.

### The Idea
Instead of maintaining two separate template files, make one IDE point to the other's file. Edit in either IDE — changes persist in both.

### How to Set Up

**Option A: Make Zed use VS Code's `cpp.json`**

1. Backup Zed's current snippets:
   - Open `~/.config/zed/snippets/c++.json` and save a copy somewhere safe
2. Delete Zed's `c++.json` and create a symlink to VS Code's file:
   - In terminal: `ln -sf ~/Library/Application\ Support/Code/User/snippets/cpp.json ~/.config/zed/snippets/c++.json`
3. In your `cpp.json`, make sure you have a snippet named exactly `boilerplate` (lowercase):
   ```json
   {
     "boilerplate": {
       "prefix": "cp",
       "body": [
         "#include <bits/stdc++.h>",
         "using namespace std;",
         "// ... your template here ..."
       ],
       "description": "C++ Boilerplate"
     }
   }
   ```
4. Run **CP: Status** task and verify it shows `Template: Zed snippets (cpp.json)`

Now edit `cpp.json` in either Zed or VS Code — both see the same file.

**Option B: Make VS Code use Zed's `c++.json`**

1. Backup VS Code's current snippets:
   - Open `~/Library/Application Support/Code/User/snippets/cpp.json` and save a copy somewhere safe
2. Delete VS Code's `cpp.json` and create a symlink to Zed's file:
   - In terminal: `ln -sf ~/.config/zed/snippets/c++.json ~/Library/Application\ Support/Code/User/snippets/cpp.json`

### Which Snippet to Use as Template?

When using `zed_snippets` template source, the tool looks for a snippet named exactly `boilerplate` (case-insensitive) in `~/.config/zed/snippets/c++.json`.

Make sure your main boilerplate template has this name in your `cpp.json`.
