use std::{fs, path::{Path, PathBuf}};

use crate::{core::{ActiveProblem, Language, UserConfig}};

#[derive(Debug, Clone)]
pub struct FsOps {
    pub home_dir: PathBuf,
    pub root_dir: PathBuf,
    pub tc_dir: PathBuf,
    pub binary_dir: PathBuf
}

impl FsOps {
    pub fn new() -> Self {
        let home = dirs::home_dir().expect("Could not find home directory");
        let root_dir = home.join(".zed-cp-helper");
        
        let _ = fs::create_dir_all(&root_dir.join(".binaries"));
        let _ = fs::create_dir(&root_dir.join(".testcases"));
        
        Self {
            home_dir: home,
            root_dir: root_dir.clone(),
            tc_dir: root_dir.join(".testcases"),
            binary_dir: root_dir.join(".binaries")
        }
    }

    pub fn write_tc_file(&self, problem: &ActiveProblem) -> bool {
        if let Ok(content) = serde_json::to_string_pretty(problem) {
            let file_path = self.tc_dir.join(format!("{}.json", problem.name));
            if !file_path.exists() {
                let _ = fs::write(file_path, content);
                return true;
            }
        }
        false
    }

    pub fn write_code_file(&self, problem: &ActiveProblem, code_path: &PathBuf) -> PathBuf {
        let (config, _) = self.load_config();
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
    
    pub fn load_config(&self) -> (UserConfig, bool) {
        let mut exists = true;
        let file_path = self.root_dir.join("config.json");
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
    
    pub fn save_config(&self, config: &UserConfig) {
        let file_path = self.root_dir.join("config.json");
        if let Ok(parsed_config) = serde_json::to_string_pretty(config) {
            match fs::write(file_path, parsed_config) {
                Ok(_) => {},
                Err(e) => { eprintln!("{:#?}", e)}
            }
        }
    }
}