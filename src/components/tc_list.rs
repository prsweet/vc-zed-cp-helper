use ratatui::{Frame, crossterm::event::{Event, KeyCode, MouseEvent, MouseEventKind}, layout::{Constraint::Ratio, Layout, Rect}};

use crate::components::testcase::{ActiveBox, TestCase};

pub struct TestCaseList {
    pub testcases: Vec<TestCase>,
    pub scroll_offset: usize,
    pub active_area: usize,
    pub active_box: ActiveBox
}

impl TestCaseList {
    pub fn new() -> Self {
        Self {
            testcases: Vec::new(),
            scroll_offset: 0,
            active_area: 0,
            active_box: ActiveBox::None
        }
    }

    pub fn clear(&mut self) {
        self.testcases.clear();
        self.active_area = 0;
        self.scroll_offset = 0;
        self.active_box = ActiveBox::Input;
    }

    pub fn add_tc(&mut self) {
        self.testcases.push(TestCase::new("", ""));
        self.active_area = self.testcases.len().saturating_sub(1);
        self.active_box = ActiveBox::Input;
    }

    pub fn focus_first(&mut self) {
        if !self.testcases.is_empty() {
            self.active_area = 0;
            self.active_box = ActiveBox::Input;
        }
    }

    fn update_scroll(&mut self, is_editing: bool) {
        if is_editing {
            if self.active_area < self.scroll_offset {
                self.scroll_offset = self.active_area;
            } else if self.active_area >= self.scroll_offset + 3 /* because there are 3 tc visible at a time */ {
                self.scroll_offset = self.active_area.saturating_add(2);
            }
        }
    }

    pub fn draw(&mut self, frame: &mut Frame, area: Rect, is_editing: bool) {
        let total_tc = self.testcases.len();
        self.update_scroll(is_editing);

        let mx_offset = total_tc.saturating_sub(3);
        self.scroll_offset = self.scroll_offset.min(mx_offset);
        let draw_cases = 3.min(total_tc.saturating_sub(self.scroll_offset));

        if draw_cases > 0 {
            let constraints = vec![Ratio(1, draw_cases as u32); draw_cases];
            let rows = Layout::vertical(constraints).split(area);

            for (i, tc_area) in rows.iter().enumerate() {
                let idx = self.scroll_offset + i;
                let title = &format!("TestCase {} ", idx + 1);
                let active_box = if idx == self.active_area { self.active_box } else { ActiveBox::None };
                self.testcases[idx].draw_tc(frame, *tc_area, title, active_box, is_editing && idx == self.active_area);
            }
        }
    }

    pub fn handle_key(&mut self, event: Event) {
        if let Event::Key(key) = event {
            if key.code == KeyCode::Tab {
                match self.active_box {
                    ActiveBox::Input => {
                        self.active_box = ActiveBox::Expected;
                    },
                    ActiveBox::Expected => {
                        self.active_box = ActiveBox::Input;
                        self.active_area = (self.active_area + 1) % self.testcases.len();
                    },
                    _ => {}
                }
                return;
            }

            match self.active_box {
                ActiveBox::Expected => { self.testcases[self.active_area].exp_content.input(event); },
                ActiveBox::Input => { self.testcases[self.active_area].inp_content.input(event); },
                _ => {}
            }
        }
    }

    pub fn handle_mouse(&mut self, mouse: &MouseEvent) {
        let draw_cases = 3.min(self.testcases.len().saturating_sub(self.scroll_offset));
        let mut hovered = false;

        for i in 0..draw_cases {
            let idx = self.scroll_offset + i;
            if self.testcases[idx].handle_mouse(mouse) {
                hovered = true;
                break;
            }
        }

        if !hovered {
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
}