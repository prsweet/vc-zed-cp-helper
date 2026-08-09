use std::env;

enum Editor {
    Zed,
    VsCode,
    NeoVim,
    Unknown
}

pub fn detect_editor() -> Editor {
    match env::var("TERM_PROGRAM").as_deref() {
        Ok("zed") => return Editor::Zed,
        Ok("vscode") => return Editor::VsCode,
        _ => {}
    }
    
    if env::var("NVIM").is_ok() {
        return Editor::NeoVim
    }

    Editor::Unknown
}

pub fn open_in_editor(editor: &Editor, file_path: &str) {
    match editor {
        Editor::Zed => {
            
        },
        Editor::NeoVim => {
            
        },
        Editor::VsCode => {
            
        },
        Editor::Unknown => {
            
        }
    }
}