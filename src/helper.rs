use std::path::PathBuf;
use ratatui::{Frame, crossterm::event::{Event, KeyCode}, style::{Color, Modifier, Style, Stylize}, widgets::{Block, BorderType, Borders, Padding}};

use crate::{components::{block, config::ConfigMenu, dir_terminal::DirTerminal, tc_list::TestCaseList, testcase::TestCase}, core::{ActiveProblem, HelperCommand, PassingCommand::{self, ToHelper, ToRunner}, ReceivingTestCase, RunnerCommand, UserConfig, fs_ops::{find_source_code, load_config, save_config, write_code_file, write_tc_file}}};

pub enum InputMode {
    Normal,
    Editing,
    Directory,
    Config
}

pub struct Helper {
    pub dir_terminal: DirTerminal,
    pub active_problem: Option<ActiveProblem>,
    pub input_mode: InputMode,
    pub tc_list: TestCaseList,
    pub config_menu: ConfigMenu
}

impl Helper {
    pub fn new(intitial_dir: PathBuf) -> Self {
        Self {
            dir_terminal: DirTerminal::new(intitial_dir),
            active_problem: None,
            input_mode: InputMode::Normal,
            tc_list: TestCaseList::new(),
            config_menu: ConfigMenu::new()
        }
    }

    pub fn draw(&mut self, frame: &mut Frame) {
        let area = frame.area();

        let master_border = block(Some(" Zed CP Helper ")).border_style(Color::Yellow);
        let main_area = master_border.inner(area);
        frame.render_widget(master_border, area);

        let tc_list_area = self.dir_terminal.draw(frame, main_area, matches!(self.input_mode, InputMode::Directory));
        self.tc_list.draw(frame, tc_list_area, matches!(self.input_mode, InputMode::Editing));

        if matches!(self.input_mode, InputMode::Config) {
            let dim_bg = Block::default().style(Style::default().add_modifier(Modifier::DIM));
            frame.render_widget(dim_bg, area);
            self.config_menu.draw(frame, area);
        }
    }

    pub fn cmd_run(&mut self) -> Option<PassingCommand> {
        if let Some(problem) = &self.active_problem {
            if let Some(path) = find_source_code(&problem.name) {
                let path_str = path.to_string_lossy().to_string();
                return Some(ToRunner(RunnerCommand::RunCode(path_str)));
            } else {
                self.dir_terminal.output = Some("Error: Source file not found".to_string());
            }
        } else {
            self.dir_terminal.output = Some("Error: no active problem".to_string());
        }
        None
    }

    pub fn cmd_add(&mut self) {
        self.input_mode = InputMode::Editing;
        self.tc_list.add_tc();
    }

    pub fn update_tc(&self) {
        if let Some(problem) = &self.active_problem {
            let mut updated_problem = problem.clone();
            
            let mut updated_test = Vec::new();
            for tc in &self.tc_list.testcases {
                updated_test.push(ReceivingTestCase {
                    input: tc.inp_content.lines().join("\n"),
                    expected_output: tc.exp_content.lines().join("\n")
                });
            }
            
            updated_problem.test_cases = updated_test;
            write_tc_file(&updated_problem);
        }
    }

    pub fn cmd_submit(&mut self) {
        
    }

    pub fn cmd_edit(&mut self) {
        self.input_mode = InputMode::Editing;
        self.tc_list.focus_first();
        // todo: first get the existing testcase in buffer and then edit it using handleediting
        // todo: taking the edit and pasting the thing in the actual testcase file
    }

    pub fn cmd_help(&mut self) {
        let help_text = "KEYBINDINGS: [r] Run | [e] Edit | [a] Add | [d] Directory | [q] Quit";
        self.dir_terminal.output = Some(help_text.to_string());
    }

    pub fn wire_received_tc(&mut self, mut problem: ActiveProblem) {
        problem.name = problem.name.replace(".", "").replace(" ", "_");
        self.active_problem = Some(problem.clone());
        self.tc_list.clear();

        for tc in problem.test_cases.iter() {
            self.tc_list.testcases.push(TestCase::new(&tc.input, &tc.expected_output));
        }

        self.input_mode = InputMode::Normal;
        write_tc_file(&problem);
        write_code_file(&problem);
    }

    pub fn handle_event(&mut self, event: Event) -> Option<PassingCommand> {
        if let Event::Key(key) = event {
            match self.input_mode {
                InputMode::Editing => {
                    if let KeyCode::Esc = key.code {
                        self.update_tc();
                        self.input_mode = InputMode::Normal;
                        return None;
                        // return Some(ToHelper(HelperCommand::EditTestCase));
                        // here i guess we have to use fs_ops.rs, will see for it
                    }
                    self.tc_list.handle_key(event);
                }
                InputMode::Normal => {
                    match key.code {
                        KeyCode::Char('q') => return Some(ToHelper(HelperCommand::Quit)),
                        KeyCode::Char('r') => return self.cmd_run(),
                        KeyCode::Char('a') => self.cmd_add(),
                        KeyCode::Char('s') => self.cmd_submit(),
                        KeyCode::Char('e') => self.cmd_edit(),
                        KeyCode::Char('c') => { self.input_mode = InputMode::Config }
                        KeyCode::Char('h') => self.cmd_help(),
                        KeyCode::Char('d') => { self.input_mode = InputMode::Directory; },
                        _ => {}
                    }
                },
                InputMode::Directory => {
                    let change_mode = self.dir_terminal.handle_event(key);
                    if change_mode {
                        self.input_mode = InputMode::Normal;
                    }
                }
                InputMode::Config => {
                    let saved = self.config_menu.handle_key(event);
                    if saved { self.input_mode = InputMode::Normal; }
                }
            };
        } else if let Event::Mouse(mouse) = event {
            self.tc_list.handle_mouse(&mouse);
        }
        None
    }
}