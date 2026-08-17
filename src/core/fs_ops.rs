use std::{fs, path::{Path, PathBuf}};

use crate::{core::{ActiveProblem, Language, UserConfig}};

pub struct PathManager {
    pub home_dir: PathBuf,
    pub root_dir: PathBuf,
    pub tc_dir: PathBuf,
    pub binary_dir: PathBuf
}

impl PathManager {
    pub fn new() -> (Self, bool) {
        let home = dirs::home_dir().expect("Could not find home directory");
        let root_dir = home.join(".zed-cp-helper");
        let exists = root_dir.exists();
        
        let _ = fs::create_dir_all(&root_dir);
        let _ = fs::create_dir_all(&root_dir.join(".binaries"));
        let _ = fs::create_dir(&root_dir.join(".testcases"));
        
        (Self {
            home_dir: home,
            root_dir: root_dir.clone(),
            tc_dir: root_dir.join(".testcases"),
            binary_dir: root_dir.join(".binaries")
        }, exists)
    }
}

pub fn write_tc_file(problem: &ActiveProblem) -> bool {
    let paths = PathManager::new().0;
    let tc_dir = paths.root_dir.join(".testcases");
    let _ = fs::create_dir(&tc_dir);
    if let Ok(content) = serde_json::to_string_pretty(problem) {
        let file_path = tc_dir.join(format!("{}.json", problem.name));
        if !file_path.exists() {
            let _ = fs::write(file_path, content);
            return true;
        }
    }
    false
}

pub fn write_code_file(problem: &ActiveProblem, code_path: &PathBuf) -> PathBuf {
    let (config, _) = load_config();
    let (ext, template) = match &config.language {
        Language::Cpp => (
            "cpp",
            "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    // your code goes here\n    return 0;\n}\n"
        )
    };

    let file_path = code_path.join(format!("{}.{}", problem.name, ext));
    if !file_path.exists() {
        let _ = fs::write(&file_path, template);
    }
    file_path
}

pub fn read_tc_file(file_path: &Path) -> Option<ActiveProblem> {
    if let Ok(content) = fs::read_to_string(file_path) {
        return serde_json::from_str(&content).ok()
    }
    None
}

pub fn find_source_code(problen_name: &str) -> Option<PathBuf> {
    let paths = PathManager::new().0;
    let tc_dir = paths.tc_dir;
    let extensions = ["cpp", "rs", "py", "c"];
    for e in extensions {
        let file_path = tc_dir.join(format!("{}.{}", problen_name, e));
        if file_path.exists() {
            return Some(file_path)
        }
    }
    None
}

pub fn load_config() -> (UserConfig, bool) {
    let paths = PathManager::new().0;
    let mut exists = true;
    let file_path = paths.root_dir.join("config.json");
    if !file_path.exists() { exists = false; };
    
    if let Ok(file) = fs::read_to_string(file_path) {
        if let Ok(parsed_config) = serde_json::from_str::<UserConfig>(&file) {
            return (parsed_config, exists);
        }
    }

    (UserConfig {
        language: Language::Cpp,
        fallback_flags: vec!["-std=c++23".to_string()]
    }, false)
}

pub fn save_config(config: &UserConfig) {
    let paths = PathManager::new().0;
    let file_path = paths.root_dir.join("config.json");
    if let Ok(parsed_config) = serde_json::to_string_pretty(config) {
        match fs::write(file_path, parsed_config) {
            Ok(_) => {},
            Err(e) => { eprintln!("{:#?}", e)}
        }
    }
}