use std::{boxed, fs, path::PathBuf, process::id};
use color_eyre::Result;
use ratatui::{Frame, crossterm::event::{Event, KeyCode, MouseEventKind}, layout::{Constraint::{self}, Direction::{Horizontal, Vertical}, HorizontalAlignment::{Center, Right}, Layout, Rect}, style::{Color, Modifier, Style, Stylize}, widgets::{Block, Borders, Padding, Paragraph, Wrap}};

use ratatui_textarea::{TextArea};
use serde::{Deserialize, Serialize};

use crate::dir_terminal::DirTerminal;

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct TestCase {
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
    test_cases: Vec<TestCase>
}

pub enum InputMode {
    Normal,
    Editing, // for editing the testcase
    Directory
}

fn block(title: Option<&str>) -> Block<'static> {
    let if_title = title.unwrap_or("");
    Block::default()
        .title(if_title.to_string())
        .borders(Borders::ALL)
        .padding(Padding::symmetric(1, 0))
}

pub struct Helper {
    pub scroll_offset: usize,
    pub dir_terminal: crate::dir_terminal::DirTerminal,
    pub active_problem: Option<ActiveProblem>,
    pub input_mode: InputMode,
    pub case_areas: Vec<TextArea<'static>>,
    pub active_area: usize,
    pub click_zones: Vec<Rect>,
    pub inner_scrolls: Vec<u16>,
}

impl Helper {
    pub fn new(intitial_dir: PathBuf) -> Self {
        Self {
            scroll_offset: 0,
            dir_terminal: DirTerminal::new(intitial_dir),
            active_problem: None,
            input_mode: InputMode::Normal,
            case_areas: Vec::new(),
            active_area: 0,
            click_zones: Vec::new(),
            inner_scrolls: Vec::new()
        }
    }

    pub fn draw_cal(&mut self) {
        if matches!(self.input_mode, InputMode::Editing) {
            let active_tc = self.active_area/2;

            if active_tc < self.scroll_offset {
                self.scroll_offset = active_tc;
            } else if active_tc >= self.scroll_offset + 3 /* 3 is the testcase visible at a time */ {
                self.scroll_offset = active_tc - 2;
            }
        }
    }

    pub fn draw(&mut self, frame: &mut Frame) {
        let area = frame.area();

        let master_border = block(Some(" Zed CP Helper "))
            .title_alignment(Center)
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
                    
                dir_box.set_block(dir_block.title(prompt).border_style(Color::Green));
                frame.render_widget(&dir_box, dir_area);
            },
            _ => {
                let display_str = if msg.is_empty() { cur_dir_str.to_string() } else {
                    format!(" {} > ", cur_dir_str)
                };
                let dir_panel = Paragraph::new(display_str)
                    .block(dir_block.title(" Working Directory (press d to edit) "))
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
        let num_testcase = self.case_areas.len()/2;
        let visible_cases = 3;
        self.draw_cal();

        let max_offset = num_testcase.saturating_sub(visible_cases);
        self.scroll_offset = self.scroll_offset.min(max_offset);
        let cur_offset = self.scroll_offset.min(max_offset);
        let draw_cases = visible_cases.min(num_testcase - cur_offset);

        self.click_zones.clear();

        let mut constratints = Vec::new();
        for _ in 0..draw_cases {
            constratints.push(Constraint::Ratio(1, draw_cases as u32));
        }

        let testcases_card = Layout::default()
            .direction(Vertical)
            .constraints(constratints)
            .split(testcase_area);

        for i in 0..draw_cases {
            let idx = cur_offset + i;
            let tc_area = testcases_card[i];
            let tc_block = Block::default()
                .borders(Borders::TOP)
                .title(format!("TestCase: {} ", idx + 1));
            let tc_inner = tc_block.inner(tc_area);
            frame.render_widget(tc_block, tc_area);

            let input_division = Layout::default()
                .direction(Vertical)
                .constraints([
                    Constraint::Percentage(50),
                    Constraint::Percentage(50)
                ]).split(tc_inner);

            let result_division = Layout::default()
                .direction(Horizontal)
                .constraints([
                    Constraint::Percentage(50),
                    Constraint::Percentage(50)
                ]).split(input_division[1]);

            self.click_zones.push(input_division[0]);
            self.click_zones.push(result_division[0]);
            self.click_zones.push(result_division[1]);

            let input_block = block(Some(" Input ")).title_alignment(Right);
            let expected_block = block(Some(" Expected ")).title_alignment(Right);
            let got_block = block(Some(" Got ")).title_alignment(Right);

            match self.input_mode {
                InputMode::Editing => {
                    let input_area = &self.case_areas[idx*2];
                    let expected_area = &self.case_areas[idx*2 + 1]; // will see there's & required

                    frame.render_widget(input_area, input_division[0]);
                    frame.render_widget(expected_area, result_division[0]);

                    let got_panel = Paragraph::new("got").block(got_block).wrap(Wrap { trim: false });
                    frame.render_widget(got_panel, result_division[1]);
                },
                _ => {
                    let input_text = self.case_areas[idx*2].lines().join("\n");
                    let expected_text = self.case_areas[idx*2 + 1].lines().join("\n");

                    let in_lines = self.case_areas[idx*2].lines().len() as u16;
                    let exp_lines = self.case_areas[idx*2+1].lines().len() as u16;

                    self.inner_scrolls[idx*3] = self.inner_scrolls[idx * 3].min(in_lines);
                    self.inner_scrolls[idx*3 + 1] = self.inner_scrolls[idx * 3 + 1].min(exp_lines);

                    let input_scroll = self.inner_scrolls[idx * 3];
                    let expected_scroll = self.inner_scrolls[idx * 3 + 1];
                    let got_scroll = self.inner_scrolls[idx * 3 + 2];
                    
                    let input_panel = Paragraph::new(input_text).block(input_block).wrap(Wrap { trim: false }).scroll((input_scroll, 0));
                    frame.render_widget(input_panel, input_division[0]);
                    let expected_panel = Paragraph::new(expected_text).block(expected_block).wrap(Wrap { trim: false }).scroll((expected_scroll, 0));
                    frame.render_widget(expected_panel, result_division[0]);
                    let got_panel = Paragraph::new("Run the case to get the results").block(got_block).wrap(Wrap { trim: false }).scroll((got_scroll, 0));
                    frame.render_widget(got_panel, result_division[1]);
                }
            }
            
        }
    }

    pub fn cmd_run(&mut self) {
        
    }

    pub fn cmd_add(&mut self) {
        let mut input = TextArea::default();
        input.set_block(block(Some(" Input ")));
        self.case_areas.push(input);

        let mut expected = TextArea::default();
        expected.set_block(block(Some(" Expected ")));
        self.case_areas.push(expected);

        self.active_area = self.case_areas.len() - 2;
        self.input_mode = InputMode::Editing;
        self.update_style();
        self.inner_scrolls.push(0);
        self.inner_scrolls.push(0);
        self.inner_scrolls.push(0);
    }

    pub fn save_testcases(&self) {
        if let Some(problem) = &self.active_problem {
            let mut updated_problem = problem.clone();
            
            let mut updated_test = Vec::new();
            let num_testcases = self.case_areas.len()/2;

            for i in 0..num_testcases {
                updated_test.push(TestCase {
                    input: self.case_areas[i*2].lines().join("\n") + "\n",
                    expected_output: self.case_areas[i*2 + 1].lines().join("\n") + "\n"
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
        if !self.case_areas.is_empty() {
            self.input_mode = InputMode::Editing;
            self.active_area = 0;
            self.update_style();
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
        self.case_areas.clear();
        self.active_area = 0;
        self.inner_scrolls = vec![0; problem.test_cases.len() * 3];

        for tc in problem.test_cases.iter() {
            let mut input = TextArea::default();
            input.insert_str(&tc.input);
            input.set_block(block(Some(" Input ")));
            self.case_areas.push(input);

            let mut expected = TextArea::default();
            expected.insert_str(&tc.expected_output);
            expected.set_block(block(Some(" Expected ")));
            self.case_areas.push(expected);
        }

        self.update_style();
        self.input_mode = InputMode::Normal;
        self.save_testcases();
    }

    pub fn update_style(&mut self) {
        for (i, area) in self.case_areas.iter_mut().enumerate() {
            let border_color = if i == self.active_area {
                Color::Green
            } else { 
                Color::Reset
            };

            let title = if i % 2 == 0 { " Input " } else { " Expected " };
            
            let cursor_style = if i == self.active_area {
                Style::default().add_modifier(Modifier::REVERSED)
            } else {
                Style::default()
            };
            area.set_cursor_style(cursor_style);

            area.set_block(
                block(Some(title))
                    .title_alignment(Right)
                    .border_style(border_color)
            );
        }
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
                            self.active_area = (self.active_area + 1) % self.case_areas.len();
                            self.update_style();
                            return Ok(false);
                        }
                        _ => {}
                    }

                    self.case_areas[self.active_area].input(event);
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
            let mut hovered_box_id = None;

            for (i, rect) in self.click_zones.iter().enumerate() {
                if mouse.column >= rect.x && mouse.column < rect.x + rect.width && mouse.row >= rect.y && mouse.row < rect.y + rect.height {
                    let tc_idx = i/3;
                    let box_type = i % 3;
                    let idx = self.scroll_offset + tc_idx;

                    hovered_box_id = Some(idx * 3 + box_type);
                    break;
                }
            }
            
            match mouse.kind {
                MouseEventKind::ScrollDown => {
                    if let Some(box_id) = hovered_box_id {
                        self.inner_scrolls[box_id] += 1;
                    } else if self.scroll_offset + 1 < self.case_areas.len() {
                        self.scroll_offset += 1;
                    }
                },
                MouseEventKind::ScrollUp => {
                    if let Some(box_id) = hovered_box_id && self.inner_scrolls[box_id] > 0 {
                        self.inner_scrolls[box_id] -= 1;
                    } else if self.scroll_offset > 0 {
                        self.scroll_offset -= 1;
                    }
                },
                _ => {}
            }
        }
        Ok(false)
    }
}