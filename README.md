# Zed CP Helper

A fully automated, native background tool for managing competitive programming workflows seamlessly in the [Zed](https://zed.dev/) editor on macOS.

This tool runs entirely locally as a Python script. It intercepts problem data from the [Competitive Companion](https://github.com/jmerle/competitive-companion) browser extension, auto-creates your source files with problem-specific template and test cases, allows you to instantly compile and run tests in Zed, and even fully automates submissions to Codeforces and AtCoder using your chosen browser.

## Features

- 📥 **Auto-Parses Problems**: Captures problem requirements and sample test cases via Competitive Companion.
- 🏗️ **Native C++ Template Injection**: Injects test cases directly into block comments at the bottom of the `.cpp` file (no multiple `.in`/`.out` files).
- 🚀 **Auto-Run Test Cases**: Compiles and runs all embedded test cases locally with precise execution time per case.
- 🤖 **Zero-Click Submissions**: Submits directly to Codeforces and AtCoder in the background by automating your browser.
- 📡 **Live Verdict Polling**: Shows live Codeforces status (In queue, Judging, AC, WA) directly in the terminal without ever looking at the browser.
- 🧱 **No WASM/Sandboxing Limits**: Standard Zed CP extensions have network/sandbox limits. This native approach has zero limits.

## Prerequisites

- **macOS** (Relies on AppleScript to interact with browsers)
- **Python 3.8+**
- **A supported browser** with **"Allow JavaScript from Apple Events"** enabled:
  - **Safari**: Safari → Preferences → Advanced → Check "Show Develop menu". Then Develop → Allow JavaScript from Apple Events.
  - **Brave**: View → Developer → Allow JavaScript from Apple Events
  - **Chrome**: View → Developer → Allow JavaScript from Apple Events
  - **Orion**: Similar to Safari (WebKit-based)
- **[Zed Code Editor](https://zed.dev/)**
- **C++ Compiler** (e.g., `g++` installed via Homebrew)
- **[Competitive Companion](https://github.com/jmerle/competitive-companion)** browser extension for Chrome/Firefox/Safari/Brave.

## Installation

### 1. Place the Script
By default (and recommended), the script and its configurations live in `~/.vc-zed-cp-helper/` in the main script.

```bash
cd ~ && git clone https://github.com/prsweet/vc-zed-cp-helper.git .vc-zed-cp-helper # OR your directory
```

*(Note: If you want to install it to a different custom folder or path, you must edit the `APP_DIR = "~/.vc-zed-cp-helper"` variable at the top of `main.py` to match your desired path!)*

### 2. Add Custom Code Template (Optional)
Put your default `C++` (or Python/Java) template inside the app directory at `~/.vc-zed-cp-helper/boilerplate.cpp` (or whatever custom `APP_DIR` you set). If this file doesn't exist, it will just leave your new files empty before injecting tests.

### 3. Setup Zed Tasks
Open your Zed tasks file (`~/.config/zed/tasks.json`) and add the following tasks with your `APP_DIR` to integrate smoothly with Zed's task runner (`cmd+shift+R`):

```json
// if you changed to the custom directory, change the directory to main.py in all tasks accordingly
[
  {
    "label": "CP: Start Listener (Current Folder)",
    "command": "python3 ~/.vc-zed-cp-helper/main.py listen",
    "use_new_terminal": true,
    "allow_concurrent_runs": false,
    "hide": "never"
  },
  {
    "label": "CP: Run Tests",
    "command": "python3 ~/.vc-zed-cp-helper/main.py run \"${ZED_FILE}\"",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Submit to Codeforces / AtCoder",
    "command": "python3 ~/.vc-zed-cp-helper/main.py submit \"${ZED_FILE}\"",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Set Language [cpp23]",
    "command": "python3 ~/.vc-zed-cp-helper/main.py set_lang cpp23",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Set Browser [safari]",
    "command": "python3 ~/.vc-zed-cp-helper/main.py set_browser safari",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  },
  {
    "label": "CP: Status",
    "command": "python3 ~/.vc-zed-cp-helper/main.py status",
    "use_new_terminal": false,
    "allow_concurrent_runs": false
  }
]
```

### 4. Basic Keymap
Below is a basic keymap. You can add these to your (`~/.config/zed/keymap.json`) according to your workspace preferences:

```json
[
  {
    "context": "Editor",
    "bindings": {
      "cmd-'": ["task::Spawn", { "task_name": "CP: Run Tests" }],
      "cmd-enter": ["task::Spawn", { "task_name": "CP: Submit to Codeforces / AtCoder" }],
      "cmd-r": ["task::Spawn", { "task_name": "CP: Start Listener (Current Folder)" }]
    }
  }
]
```

---

## Usage

### 1. Starting the Listener
At the start of your programming session, open Zed and launch the **CP: Start Listener (Current Folder)** task.

Click the green `+` on the Competitive Companion extension in your browser when viewing a Codeforces or AtCoder problem. Zed will automatically open the generated source file.

### 2. Set Language / Browser
You only have to do this once. Run the **CP: Set Language [cpp23]** task. 
*(You can press `TAB` before hitting enter to modify it to `cpp20`, `cpp17`, `python`, `java`, etc.)*
This saves the active language inside `~/.vc-zed-cp-helper/config.json`. Every "Run" or "Submit" task will use this language.

Similarly, run **CP: Set Browser [safari]** (or brave) to choose which browser handles submissions.

Available browsers: `safari`, `brave`, `chrome`, `orion`

### 3. Testing 
Solve your problem and save the file. Open the Zed Task Menu (`cmd+shift+R`) and run **CP: Run Tests**. The script compiles the code dynamically and tests every embedded sample case.

### 4. Direct Submissions
Run the **CP: Submit to Codeforces / AtCoder** task. 
- It strips out the embedded test case blocks from the bottom.
- Opens your chosen browser invisibly, finds the Codeforces/AtCoder judge, sets the code, sets your selected language, and safely submits.
- **For Codeforces:** It tracks the submission live and prints `WJ`, `Running on test 5`, until eventually showing `✅ ACCEPTED` or `❌ WRONG ANSWER` directly in Zed's terminal.
- **For AtCoder:** Validates the submission and handles Captchas via browser forwarding if required.

## Dealing with CAPTCHAs
Platforms like AtCoder, and occasionally Codeforces (via Cloudflare), heavily use invisible CAPTCHAs.
If the automation hits a CAPTCHA wall:
1. The terminal output will alert you: `🔒 CAPTCHA: Please solve the CAPTCHA in [Browser]`.
2. The browser will be brought to the foreground automatically on the submit page.
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
4. Run **CP: Set Template** task and set it to `zed_snippets`

Now edit `cpp.json` in either Zed or VS Code — both see the same file.

**Option B: Make VS Code use Zed's `c++.json`**

1. Backup VS Code's current snippets:
   - Open `~/Library/Application Support/Code/User/snippets/cpp.json` and save a copy somewhere safe
2. Delete VS Code's `cpp.json` and create a symlink to Zed's file:
   - In terminal: `ln -sf ~/.config/zed/snippets/c++.json ~/Library/Application\ Support/Code/User/snippets/cpp.json`

### Which Snippet to Use as Template?

When using `zed_snippets` template source, the tool looks for a snippet named exactly `boilerplate` (case-insensitive) in `~/.config/zed/snippets/c++.json`.

Make sure your main boilerplate template has this name in your `cpp.json`.
