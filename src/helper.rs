use std::{fs, path::PathBuf};
use color_eyre::Result;
use ratatui::{Frame, crossterm::event::{Event, KeyCode, MouseEventKind}, layout::{Constraint::{self}, Direction::{Horizontal, Vertical}, HorizontalAlignment::{Center, Left, Right}, Layout, Rect}, style::{Color, Modifier, Style, Stylize}, widgets::{Block, BorderType, Borders, Padding, Paragraph, Wrap}};

use serde::{Deserialize, Serialize};
use crate::components::{dir_terminal::DirTerminal, testcase::{ActiveBox, TestCase}};

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ReceivingTestCase {
    pub input: String,
    #[serde(rename = "output")]
    pub expected_output: String
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ActiveProblem {
    pub name: String,
    url: String,
    #[serde(rename = "timeLimit")]
    time_limit: u32,
    #[serde(rename = "tests")]
    test_cases: Vec<ReceivingTestCase>
}

pub enum InputMode {
    Normal,
    Editing, // for editing the testcase
    Directory
}

pub fn block(title: Option<&str>) -> Block<'static> {
    let if_title = title.unwrap_or("");
    Block::default()
        .title(if_title.to_string())
        .borders(Borders::ALL)
        .bold()
        .title_style(Color::White)
        .border_type(BorderType::Rounded)
        .padding(Padding::symmetric(1, 0))
}

pub struct Helper {
    pub scroll_offset: usize,
    pub dir_terminal: DirTerminal,
    pub active_problem: Option<ActiveProblem>,
    pub input_mode: InputMode,
    pub active_area: usize,
    pub testcases: Vec<TestCase>,
    pub active_box: ActiveBox
}

impl Helper {
    pub fn new(intitial_dir: PathBuf) -> Self {
        Self {
            scroll_offset: 0,
            dir_terminal: DirTerminal::new(intitial_dir),
            active_problem: None,
            input_mode: InputMode::Normal,
            active_area: 0,
            testcases: Vec::new(),
            active_box: ActiveBox::None
        }
    }

    pub fn draw_cal(&mut self) {
        if matches!(self.input_mode, InputMode::Editing) {
            if self.active_area < self.scroll_offset {
                self.scroll_offset = self.active_area;
            } else if self.active_area >= self.scroll_offset + 3 /* 3 is the testcase visible at a time */ {
                self.scroll_offset = self.active_area - 2;
            }
        }
    }

    pub fn draw(&mut self, frame: &mut Frame) {
        let area = frame.area();

        let master_border = block(Some(" Zed CP Helper "))
            .border_style(Color::Yellow);
        let main_area = master_border.inner(area);
        frame.render_widget(master_border, area);
        
        let msg = self.dir_terminal.output.clone().unwrap_or_default();
        
        let msg_height = if msg.is_empty() { 0 } else {
            let w = main_area.width.saturating_sub(2).max(1);
            let required = (msg.len() as u16/ w) + 1;
            required + 2
        };

        let divisions = Layout::default()
            .direction(Vertical)
            .constraints([
                Constraint::Length(3),
                Constraint::Length(msg_height),
                Constraint::Min(0)
            ]).split(main_area);

        let cur_dir_str = self.dir_terminal.cur_dir.to_string_lossy();

        let dir_area = divisions[0];

        let dir_block = block(None);

        match self.input_mode {
            InputMode::Directory => {
                let mut dir_box = self.dir_terminal.input_area.clone();
                let prompt = format!(" {} > ", cur_dir_str);
                    
                dir_box.set_block(dir_block.title(prompt).border_style(Color::Magenta).title_alignment(Right));
                frame.render_widget(&dir_box, dir_area);
            },
            _ => {
                let display_str = if msg.is_empty() { cur_dir_str.to_string() } else {
                    format!(" {} > ", cur_dir_str)
                };
                let dir_panel = Paragraph::new(display_str)
                    .block(dir_block.title(" Working Directory ").title_alignment(Right).border_style(Color::Magenta))
                    .wrap(Wrap { trim: false });
                frame.render_widget(dir_panel, dir_area);
            }
        }

        let msg_block = block(None)
            .border_style(Color::Cyan);
        
        if !msg.is_empty() {
            let msg_panel = Paragraph::new(msg.clone())
                .block(msg_block)
                .wrap(Wrap { trim: false });
            frame.render_widget(msg_panel, divisions[1]);
        }

        let testcase_area = divisions[2];
        let num_testcase = self.testcases.len();
        let visible_cases = 3;
        self.draw_cal();

        let max_offset = num_testcase.saturating_sub(visible_cases);
        self.scroll_offset = self.scroll_offset.min(max_offset);
        let cur_offset = self.scroll_offset.min(max_offset);
        let draw_cases = visible_cases.min(num_testcase - cur_offset);

        if draw_cases > 0 {
            let constraints = vec![Constraint::Ratio(1, draw_cases as u32); draw_cases];
            let rows = Layout::vertical(constraints).split(testcase_area);

            for (i, tc_area) in rows.iter().copied().enumerate() {
                let idx = self.scroll_offset + i;
                let title = &format!("TestCase {} ", idx + 1);
                let active_box = if idx == self.active_area { self.active_box } else { ActiveBox::None };
                let is_editing = matches!(self.input_mode, InputMode::Editing) && idx == self.active_area;
                self.testcases[idx].draw_tc(frame, tc_area, title, active_box, is_editing);
            }
        }
    }

    pub fn cmd_run(&mut self) {
        
    }

    pub fn cmd_add(&mut self) {
        self.testcases.push(TestCase::new("", ""));
        self.active_area = self.testcases.len().saturating_sub(1);
        self.input_mode = InputMode::Editing;
        self.active_box = ActiveBox::Input;
        self.scroll_offset += 1;
    }

    pub fn save_testcases(&self) {
        if let Some(problem) = &self.active_problem {
            let mut updated_problem = problem.clone();
            
            let mut updated_test = Vec::new();
            for tc in &self.testcases {
                updated_test.push(ReceivingTestCase {
                    input: tc.inp_content.lines().join("\n"),
                    expected_output: tc.exp_content.lines().join("\n")
                });
            }
            
            updated_problem.test_cases = updated_test;

            if let Ok(json_str) = serde_json::to_string_pretty(&updated_problem) {
                let file_name = problem.name.replace(" ", "_").replace(".", "");
                let file_path = self.dir_terminal.cur_dir.join(format!("{}.json", file_name));
                let _ = fs::write(file_path, json_str);
            }
        }
    }

    pub fn cmd_submit(&mut self) {
        
    }

    pub fn cmd_edit(&mut self) {
        if !self.testcases.is_empty() {
            self.input_mode = InputMode::Editing;
            self.active_area = 0;
            self.active_box = ActiveBox::Input;
        }
        // todo: first get the existing testcase in buffer and then edit it using handleediting
        // todo: taking the edit and pasting the thing in the actual testcase file
    }

    pub fn cmd_help(&mut self) {
        let help_text = "KEYBINDINGS: [r] Run | [e] Edit | [a] Add | [d] Directory | [q] Quit";
        self.dir_terminal.output = Some(help_text.to_string());
    }

    pub fn handle_receving(&mut self, problem: ActiveProblem) {
        self.active_problem = Some(problem.clone());
        self.testcases.clear();
        self.active_area = 0;
        self.scroll_offset = 0;

        for tc in problem.test_cases.iter() {
            self.testcases.push(TestCase::new(&tc.input, &tc.expected_output));
        }

        self.input_mode = InputMode::Normal;
        self.save_testcases();
    }

    pub fn handle_event(&mut self, event: Event) -> Result<bool> {
        if let Event::Key(key) = event {
            match self.input_mode {
                InputMode::Editing => {
                    match key.code {
                        KeyCode::Esc => {
                            self.save_testcases();
                            self.input_mode = InputMode::Normal;
                            return Ok(false);
                        },
                        KeyCode::Tab => {
                            match self.active_box {
                                ActiveBox::Expected => {
                                    self.active_area = (self.active_area + 1) % self.testcases.len();
                                    self.active_box = ActiveBox::Input;
                                },
                                ActiveBox::Input => {
                                    self.active_box = ActiveBox::Expected;
                                },
                                _ => {}
                            }
                            return Ok(false);
                        }
                        _ => {}
                    }

                    match self.active_box {
                        ActiveBox::Input => {
                            self.testcases[self.active_area].inp_content.input(event);
                        },
                        ActiveBox::Expected => {
                            self.testcases[self.active_area].exp_content.input(event);
                        },
                        _ => {}
                    }
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
            let draw_cases = 3.min(self.testcases.len().saturating_sub(self.scroll_offset));
            let mut hovered_inside = false;

            for i in 0..draw_cases {
                let idx = self.scroll_offset + i;
                if self.testcases[idx].handle_triggers(&mouse) {
                    hovered_inside = true;
                    break;
                }
            }

            if !hovered_inside {
                match mouse.kind {
                    MouseEventKind::ScrollDown => {
                        if self.scroll_offset + 1 < self.testcases.len() {
                            self.scroll_offset += 1;
                        }
                    },
                    MouseEventKind::ScrollUp => {
                        if self.scroll_offset > 0 {
                            self.scroll_offset -= 1;
                        }
                    },
                    _ => {}
                }
            }
        }
        Ok(false)
    }
}