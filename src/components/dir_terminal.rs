use std::{fs, path::PathBuf};

use ratatui::{Frame, crossterm::event::{KeyCode, KeyEvent}, layout::{Constraint::{Length, Min}, HorizontalAlignment::Right, Layout, Rect}, style::Color, widgets::{Paragraph, Wrap}};
use ratatui_textarea::TextArea;

use crate::components::block;

pub struct DirTerminal {
    pub cur_dir: PathBuf,
    pub input_area: TextArea<'static>,
    pub output: Option<String>
}

impl DirTerminal {
    pub fn new(initial_dir: PathBuf) -> Self {
        Self {
            cur_dir: initial_dir,
            input_area: TextArea::default(),
            output: None
        }
    }

    pub fn draw(&mut self, frame: &mut Frame, main_area: Rect, is_active: bool) -> Rect {
        let cur_dir_str = self.cur_dir.to_string_lossy();
        let msg = self.output.clone().unwrap_or_default();
        let msg_height = if msg.is_empty() { 0 } else {
            let w = main_area.width.saturating_sub(2).max(1);
            let required = (msg.len() as u16 / w) + 1;
            required + 2
        };

        let divisions = Layout::vertical([
            Length(3),
            Length(msg_height),
            Min(0)
        ]).split(main_area);
        
        let dir_block = block(None).border_style(Color::Magenta).title_alignment(Right);

        if is_active {
            let prompt = format!(" {} > ", cur_dir_str);
            self.input_area.set_block(dir_block.title(prompt));
            frame.render_widget(&self.input_area, divisions[0]);
        } else {
            let display_text = if msg.is_empty() { cur_dir_str.to_string() } else { format!(" {} > ", cur_dir_str) };
            let dir_panel = Paragraph::new(display_text)
                .block(dir_block.title(" Working Directory "))
                .wrap(Wrap { trim: false });
            frame.render_widget(dir_panel, divisions[0]);
        }

        if !msg.is_empty() {
            let msg_block = block(None).border_style(Color::Cyan);
            let msg_panel = Paragraph::new(msg)
                .block(msg_block)
                .wrap(Wrap { trim: false });
            frame.render_widget(msg_panel, divisions[1]);
        }

        divisions[2]
    } 

    pub fn handle_event(&mut self, key: KeyEvent) -> bool {
        match key.code {
            KeyCode::Enter => {
                let cmd = self.input_area.lines().join(" ").trim().to_string();

                self.input_area = TextArea::default();
                self.output = None;

                if cmd.starts_with("cd ") {
                    let target = cmd.trim_start_matches("cd ").trim();
                    let new_path = self.cur_dir.join(target);

                    if let Ok(canonical) = new_path.canonicalize() {
                        if canonical.is_dir() {
                            self.cur_dir = canonical;
                        } else {
                            self.output = Some(format!("cd: Not a Directory"));
                        }
                    } else {
                        self.output = Some(format!("cd: No such File or Directory: {}", target));
                    }
                } else if cmd == "ls" {
                    if let Ok(entries) = fs::read_dir(&self.cur_dir) {
                        let mut names = Vec::new();
                        for entry in entries.flatten() {
                            let name = entry.file_name().to_string_lossy().to_string();
                            if entry.path().is_dir() {
                                names.push(format!("{}/", name));
                            } else {
                                names.push(name);
                            }
                        }
                        self.output = Some(names.join("  "));
                    }
                } else if !cmd.is_empty() {
                    self.output = Some(format!("Command not found: {}", cmd));
                }
            }
            KeyCode::Tab => {
                self.autocomplete();
            },
            KeyCode::Esc => {
                self.output = None;
                return true;
            }
            _ => {
                self.input_area.input(key);
            }
        }
        false
    }

    pub fn autocomplete(&mut self) {
        let line = self.input_area.lines().join("");

        if line.starts_with("cd ") {
            let prefix = line.trim_start_matches("cd ");

            if let Ok(entries) = fs::read_dir(&self.cur_dir) {
                let mut matches = Vec::new();
                for entry in entries.flatten() {
                    if entry.path().is_dir() {
                        let name = entry.file_name().to_string_lossy().to_string();
                        if name.starts_with(prefix) {
                            matches.push(name);
                        }
                    }
                }

                if matches.len() == 1 {
                    self.input_area = TextArea::default();
                    self.input_area.insert_str(format!("cd {}/", matches[0]));
                    self.output = None;
                } else if matches.len() > 1 {
                    self.output = Some(matches.join("  "));
                }
            }
        }
    }
}