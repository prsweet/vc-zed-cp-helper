use std::{ops::Deref, path::PathBuf};
use derive_name::{Named, VariantName};
use ratatui::{Frame, crossterm::event::{Event, KeyCode}, style::{Color, Modifier, Style, Stylize}, widgets::{Block, BorderType, Borders, Padding}};

use crate::{components::{block, config::ConfigMenu, dir_terminal::DirTerminal, tc_list::TestCaseList, testcase::{Accepted::{self, Other}, TestCase}}, core::{ActiveProblem, HelperCommand, PassingCommand::{self, ToHelper, ToRunner}, ReceivingTestCase, RunnerCommand, UserConfig, Verdict, fs_ops::{find_source_code, load_config, save_config, write_code_file, write_tc_file}}};

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
            return Some(ToRunner(RunnerCommand::RunCode(problem.clone())));
        } else {
            self.dir_terminal.output = Some("Error: no active problem".to_string());
        }
        None
    }

    pub fn cmd_add(&mut self) {
        self.input_mode = InputMode::Editing;
        self.tc_list.add_tc();
    }

    pub fn update_tc(&mut self) {
        if let Some(problem) = &mut self.active_problem {
            let mut updated_test = Vec::new();
            for tc in &self.tc_list.testcases {
                updated_test.push(ReceivingTestCase {
                    input: tc.inp_content.lines().join("\n"),
                    expected_output: tc.exp_content.lines().join("\n")
                });
            }
            
            write_tc_file(&problem);
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
        self.tc_list.clear();
        let created = write_tc_file(&problem);
        if created {
            
        }

        for tc in problem.test_cases.iter() {
            self.tc_list.testcases.push(TestCase::new(&tc.input, &tc.expected_output));
        }

        self.input_mode = InputMode::Normal;
        let code_path = write_code_file(&problem, &self.dir_terminal.cur_dir);
        problem.code_file = code_path;
        self.active_problem = Some(problem.clone());
    }

    pub fn show_results(&mut self, results: Vec<Verdict>) {
        for (i, result) in results.into_iter().enumerate() {
            if let Some(tc) = self.tc_list.testcases.get_mut(i) {
                match result {
                    Verdict::Success { output, time } => {
                        let got_content = String::from_utf8_lossy(&output.stdout).to_string();
                        let exp_content = tc.exp_content.lines().join("\n");
                        tc.second_title = Some(format!(" {}ms",time));
                        tc.ac = if got_content == exp_content { Accepted::AC } else { Accepted::Other };
                        tc.got_content = Some(got_content);
                    },
                    a => {
                        tc.second_title = Some(format!(" {}", a.variant_name()));
                        tc.ac = Accepted::Other;
                    }
                }
                tc.collapsed = matches!(tc.ac, Accepted::AC);
            }
        }
        /*
         * all the things will be collapsed and showed on block title
         * except for success and WA along with title it will show in got content
         * and sucees will be shrinked by default
         */
    }

    pub fn handle_event(&mut self, event: Event) -> Option<PassingCommand> {
        if let Event::Key(key) = event {
            match self.input_mode {
                InputMode::Editing => {
                    if let KeyCode::Esc = key.code {
                        self.update_tc();
                        self.input_mode = InputMode::Normal;
                        return None;
                        // here i guess we have to use fs_ops.rs, will see for it
                    }
                    self.tc_list.handle_key(event);
                }
                InputMode::Normal => {
                    match key.code {
                        KeyCode::Char('q') => return Some(ToHelper(HelperCommand::Quit)),
                        KeyCode::Char('a') => return Some(ToHelper(HelperCommand::Add)),
                        KeyCode::Char('r') => return Some(ToHelper(HelperCommand::Run)),
                        KeyCode::Char('e') => return Some(ToHelper(HelperCommand::Edit)),
                        KeyCode::Char('h') => self.cmd_help(),
                        KeyCode::Char('c') => { self.input_mode = InputMode::Config }
                        KeyCode::Char('d') => { self.input_mode = InputMode::Directory; },
                        _ => {}
                    }
                },
                InputMode::Directory => {
                    let change_mode = self.dir_terminal.handle_event(key);
                    if change_mode { self.input_mode = InputMode::Normal; }
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