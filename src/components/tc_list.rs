use ratatui::{Frame, crossterm::event::{Event, KeyCode, MouseEvent, MouseEventKind}, layout::{Constraint::{self, Length, Percentage, Ratio}, Layout, Rect}, style::Color, widgets::{Scrollbar, ScrollbarState}};

use crate::components::testcase::{ActiveBox, TestCase};

pub struct TestCaseList {
    pub testcases: Vec<TestCase>,
    pub available_height: usize,
    pub scroll_row: usize,
    pub active_area: usize,
    pub active_box: ActiveBox,
    pub is_dragging: bool
}

impl TestCaseList {
    pub fn new() -> Self {
        Self {
            testcases: Vec::new(),
            available_height: 0,
            scroll_row: 0,
            active_area: 0,
            active_box: ActiveBox::None,
            is_dragging: false
        }
    }

    fn total_rows(&self) -> usize {
        self.testcases.iter().map(|tc| { tc.row_height() }).sum()
    }

    pub fn clear(&mut self) {
        self.testcases.clear();
        self.active_area = 0;
        self.available_height = 0;
        self.active_box = ActiveBox::Input;
    }

    pub fn add_tc(&mut self) {
        self.testcases.push(TestCase::new("", ""));
        self.active_area = self.testcases.len().saturating_sub(1);
        self.active_box = ActiveBox::Input;
        self.update_scroll();
    }

    pub fn row_offset_of(&self, active_area: usize) -> usize {
        self.testcases[0..active_area].iter().map(|tc| tc.row_height()).sum()
    }

    pub fn focus_first(&mut self) {
        if !self.testcases.is_empty() {
            self.active_area = 0;
            self.active_box = ActiveBox::Input;
            self.update_scroll();
        }
    }

    pub fn update_scroll(&mut self) {
        if self.testcases.is_empty() || self.available_height == 0 { return; }
        let active_top = self.row_offset_of(self.active_area);
        let active_bottom = active_top + self.testcases[self.active_area].row_height();

        if active_top < self.scroll_row {
             self.scroll_row = active_top;
        } else if active_bottom > self.scroll_row + self.available_height {
            self.scroll_row = active_bottom.saturating_sub(self.available_height);
        }
    }

    pub fn draw(&mut self, frame: &mut Frame, area: Rect, is_editing: bool) {
        let division = Layout::horizontal([
            Percentage(100),
            Length(2)
        ]).split(area);

        let tc_list_area = division[0];
        let scrollbar_area = division[1];
        
        let scroll_bar = Scrollbar::new(ratatui::widgets::ScrollbarOrientation::VerticalRight)
            .style(Color::DarkGray)
            .begin_symbol(Some("-"))
            .end_symbol(Some("-"));
        
        self.available_height = tc_list_area.height as usize;
        let total = self.total_rows();
        self.scroll_row = self.scroll_row.min(total.saturating_sub(self.available_height));

        let start_row = self.scroll_row;
        let end_row = (start_row + self.available_height).min(total);
        let mut current_row: usize = 0;

        for (idx, tc) in self.testcases.iter_mut().enumerate() {
            let tc_height = tc.row_height();
            let tc_top = current_row;
            let tc_bottom = tc_top + tc_height;

            if tc_bottom <= start_row { current_row = tc_bottom; continue; }
            if tc_top >= end_row { break; }

            let clip_top = start_row.saturating_sub(tc_top);
            let clip_bottom = (end_row - tc_top).min(tc_height);
            let visible_height = clip_bottom.saturating_sub(clip_top);

            let tc_y = tc_list_area.y as usize + (tc_top.saturating_sub(start_row));
            let tc_area = Rect {
                x: tc_list_area.x,
                y: tc_y as u16,
                width: tc_list_area.width,
                height: visible_height as u16
            };

            let title = format!("TestCase {} ", idx + 1);
            let active_box = if idx == self.active_area { self.active_box } else { ActiveBox::None };
            tc.draw_tc(frame, tc_area, &title, active_box, is_editing && idx == self.active_area);
            current_row = tc_bottom;
        }

        let mut scroll_state = ScrollbarState::new((total.saturating_sub(self.available_height) + 1) as usize).position(self.scroll_row as usize);
        frame.render_stateful_widget(scroll_bar, scrollbar_area, &mut scroll_state);
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
                self.update_scroll();
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
        let mut hovered = false;

        for tc in self.testcases.iter_mut() {
            if tc.handle_mouse(mouse) {
                hovered = true;
                break;
            }
        }

        if !hovered {
            let max_scroll = self.total_rows().saturating_sub(self.available_height);
            match mouse.kind {
                MouseEventKind::ScrollDown => {
                    self.scroll_row = self.scroll_row.saturating_add(1).min(max_scroll);
                },
                MouseEventKind::ScrollUp => {
                    self.scroll_row = self.scroll_row.saturating_sub(1);
                },
                _ => {}
            }
        }
    }
}