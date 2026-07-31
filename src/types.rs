use std::{env::current_dir, path::PathBuf};
use color_eyre::Result;

use crossterm::event::{self, Event, KeyCode};
use ratatui::{Frame, layout::{Alignment::{Center, Left, Right}, Constraint::{self, Percentage}, Direction::{Horizontal, Vertical}, Layout}, style::{Color, Style}, widgets::{Block, BorderType, Borders, Padding, Paragraph}};
use tui_textarea::{Input, TextArea};

pub struct TestCase {
    pub input: String,
    pub expected_output: String
}

pub struct ActiveProblem {
    pub name: String,
    group: String,
    url: String,
    time_limit: u8,
    test_cases: Vec<TestCase>
}

pub enum InputMode {
    Normal,
    Editing // for editing the testcase
}

pub struct Helper {
    pub receiving_dir: PathBuf,
    pub active_problem: Option<ActiveProblem>,
    pub input_mode: InputMode,
    pub case_areas: Vec<TextArea<'static>>,
    pub active_area: usize
}

impl Helper {
    pub fn new() -> Self {
        Self {
            receiving_dir: current_dir().unwrap_or_default(),
            active_problem: None,
            input_mode: InputMode::Normal,
            case_areas: Vec::new(),
            active_area: 0
        }
    }

    pub fn draw(&self, frame: &mut Frame) {
        let input_block = Block::default().title(" Input ").title_alignment(Right).borders(Borders::ALL).padding(Padding::symmetric(1, 0));
        let expected_block = Block::default().title(" Expected ").title_alignment(Right).borders(Borders::ALL).padding(Padding::symmetric(1, 0));
        let got_block = Block::default().title(" Got ").title_alignment(Right).borders(Borders::ALL).padding(Padding::symmetric(1, 0));
        
        let area = frame.area();
        let outer_most_block = Block::default()
            .title(" Zed CP Helper ")
            .title_alignment(Center)
            .border_style(Color::Yellow)
            .borders(Borders::ALL)
            .padding(Padding::symmetric(1, 0));
        
        let app_inner_area = outer_most_block.inner(area);
        frame.render_widget(outer_most_block, area);

        let mut constraints = Vec::new();
        let testcase = 2;
        for _ in 0..testcase {
            constraints.push(Constraint::Length(15));
        }

        let testcase_block = Layout::default()
            .direction(Vertical)
            .constraints(constraints)
            .split(app_inner_area);

        for i in 0..testcase {
            let tc_area = testcase_block[i];

            let outer_block = Block::default()
                .title(format!(" TestCase: {} ", i + 1));
                // .borders(Borders::ALL)

            let inner_block = outer_block.inner(tc_area);
            frame.render_widget(outer_block, tc_area);

            let vertical_blocks = Layout::default()
                .direction(Vertical)
                .constraints([
                    Constraint::Percentage(50),
                    Constraint::Percentage(50)
                ]).split(inner_block);

            let bottom_blocks = Layout::default()
                .direction(Horizontal)
                .constraints([
                    Constraint::Percentage(50),
                    Constraint::Percentage(50)
                ]).split(vertical_blocks[1]);

            match self.input_mode {
                InputMode::Editing => {
                    let input_area = &self.case_areas[i * 2];
                    let expected_area = &self.case_areas[i * 2 + 1];

                    frame.render_widget(input_area, vertical_blocks[0]);
                    frame.render_widget(expected_area, bottom_blocks[0]);

                    let got_panel = Paragraph::new("got")
                        .block(got_block.clone());
                    frame.render_widget(got_panel, bottom_blocks[1]);
                },
                InputMode::Normal => {
                    let input_panel = Paragraph::new("input")
                        .block(input_block.clone());
                    let expected_panel = Paragraph::new("expected")
                        .block(expected_block.clone());
                    let got_panel = Paragraph::new("got")
                        .block(got_block.clone());

                    frame.render_widget(input_panel, vertical_blocks[0]);
                    frame.render_widget(expected_panel, bottom_blocks[0]);
                    frame.render_widget(got_panel, bottom_blocks[1]);
                }
            }
        }
    }

    pub fn cmd_run(&mut self) {
        
    }

    pub fn cmd_add(&mut self) {
        
    }

    pub fn cmd_submit(&mut self) {
        
    }

    pub fn cmd_edit(&mut self) {
        self.input_mode = InputMode::Editing;
        self.case_areas.clear();
        self.active_area = 0;

        let input_block = Block::default().title(" Input ").borders(Borders::ALL);
        let expected_block = Block::default().title(" Expected ").borders(Borders::ALL);

        let test_cases = 2;
        for _ in 0..test_cases {
            let mut input = TextArea::default();
            input.set_block(input_block.clone());
            self.case_areas.push(input);

            let mut expected = TextArea::default();
            expected.set_block(expected_block.clone());
            self.case_areas.push(expected);
        }
        self.update_style();
        // todo: first get the existing testcase in buffer and then edit it using handleediting
        // todo: taking the edit and pasting the thing in the actual testcase file
    }

    pub fn cmd_help(&self) {
        
    }

    pub fn update_style(&mut self) {
        
    }

    pub fn handle_event(&mut self, event: Event) -> Result<bool> {
        if let Event::Key(key) = event {
            match self.input_mode {
                InputMode::Editing => {
                    match key.code {
                        KeyCode::Esc => {
                            self.case_areas.clear();
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
                        _ => {}
                    }
                }
            };
        }
        Ok(false)
    }
}