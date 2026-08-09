use std::{fs, path::{Path, PathBuf}};

use crate::core::{ActiveProblem, Language, UserConfig};

pub fn write_tc_file(problem: &ActiveProblem) {
    let root_dir = load_config().root_dir;
    let tc_dir = root_dir.join(".testcase");
    let _ = fs::create_dir(&tc_dir);
    if let Ok(content) = serde_json::to_string_pretty(problem) {
        let file_path = tc_dir.join(format!("{}.json", problem.name));
        let _ = fs::write(file_path, content);
    }
}

pub fn read_tc_file(file_path: &Path) -> Option<ActiveProblem> {
    if let Ok(content) = fs::read_to_string(file_path) {
        return serde_json::from_str(&content).ok()
    }
    None
}

pub fn find_source_code(problen_name: &str) -> Option<PathBuf> {
    let root_dir = load_config().root_dir;
    let tc_dir = root_dir.join(".testcase");
    let extensions = ["cpp", "rs", "py", "c"];
    for e in extensions {
        let file_path = tc_dir.join(format!("{}.{}", problen_name, e));
        if file_path.exists() {
            return Some(file_path)
        }
    }
    None
}

pub fn load_config() -> UserConfig {
    let root_dir = PathBuf::from("hehe");
    UserConfig { root_dir: root_dir, language: Language::Cpp }
}

pub fn save_config(config: UserConfig) {
    
}