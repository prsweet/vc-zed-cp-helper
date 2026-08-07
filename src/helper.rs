use std::{fs, path::{PathBuf}};
use color_eyre::Result;
use ratatui::{Frame, crossterm::event::{Event, KeyCode}, style::{Color, Stylize}, widgets::{Block, BorderType, Borders, Padding}};

use crate::{components::{block, dir_terminal::DirTerminal, tc_list::TestCaseList, testcase::TestCase}, core::{ActiveProblem, ReceivingTestCase}};

pub enum InputMode {
    Normal,
    Editing,
    Directory
}

pub struct Helper {
    pub dir_terminal: DirTerminal,
    pub active_problem: Option<ActiveProblem>,
    pub input_mode: InputMode,
    pub tc_list: TestCaseList
}

impl Helper {
    pub fn new(intitial_dir: PathBuf) -> Self {
        Self {
            dir_terminal: DirTerminal::new(intitial_dir),
            active_problem: None,
            input_mode: InputMode::Normal,
            tc_list: TestCaseList::new()
        }
    }

    pub fn draw(&mut self, frame: &mut Frame) {
        let area = frame.area();

        let master_border = block(Some(" Zed CP Helper ")).border_style(Color::Yellow);
        let main_area = master_border.inner(area);
        frame.render_widget(master_border, area);

        let tc_list_area = self.dir_terminal.draw(frame, main_area, matches!(self.input_mode, InputMode::Directory));
        self.tc_list.draw(frame, tc_list_area, matches!(self.input_mode, InputMode::Editing));
    }

    pub fn cmd_run(&mut self) {
        
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
            self.write_tc_file(&updated_problem);
        }
    }

    pub fn write_tc_file(&self, problem: &ActiveProblem) {
        if let Ok(content) = serde_json::to_string_pretty(problem) {
            let file_name = problem.name.replace(" ", "_").replace(".", "");
            let file_path = self.dir_terminal.cur_dir.join(format!("{}.json", file_name));
            let _ = fs::write(file_path, content);
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

    pub fn wire_received_tc(&mut self, problem: ActiveProblem) {
        self.active_problem = Some(problem.clone());
        self.tc_list.clear();

        for tc in problem.test_cases.iter() {
            self.tc_list.testcases.push(TestCase::new(&tc.input, &tc.expected_output));
        }

        self.input_mode = InputMode::Normal;
        self.write_tc_file(&problem);
    }

    pub fn handle_event(&mut self, event: Event) -> Result<bool> {
        if let Event::Key(key) = event {
            match self.input_mode {
                InputMode::Editing => {
                    if let KeyCode::Esc = key.code {
                        self.update_tc();
                        self.input_mode = InputMode::Normal;
                        return Ok(false);
                    }
                    self.tc_list.handle_key(event);
                }
                InputMode::Normal => {
                    match key.code {
                        KeyCode::Char('q') => return Ok(true),
                        KeyCode::Char('r') => self.cmd_run(),
                        KeyCode::Char('a') => self.cmd_add(),
                        KeyCode::Char('s') => self.cmd_submit(),
                        KeyCode::Char('e') => self.cmd_edit(),
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
            };
        } else if let Event::Mouse(mouse) = event {
            self.tc_list.handle_mouse(&mouse);
        }
        Ok(false)
    }
}