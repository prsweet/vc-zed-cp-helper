use derive_name::VariantName;
use ratatui::{Frame, crossterm::event::{MouseButton, MouseEvent, MouseEventKind}, layout::{Constraint::Percentage, HorizontalAlignment::Right, Layout, Rect}, style::{Color, Modifier, Style, Stylize}, text::Line, widgets::{BorderType, Borders, Padding, Paragraph}};
use ratatui_textarea::{TextArea};

use crate::{components::{VisualState, block}, core::Verdict};

#[derive(Debug, Clone, Copy)]
pub enum ActiveBox {
    Input,
    Expected,
    None
}

pub enum Accepted {
    AC,
    None,
    Other
}

pub struct TestCase {
    pub inp_content: TextArea<'static>,
    pub exp_content: TextArea<'static>,
    pub got_content: Option<String>,
    pub input_box: VisualState,
    pub expected_box: VisualState,
    pub got_box: VisualState,
    pub collapse_toggle_area: VisualState,
    pub second_title: Option<String>,
    pub ac: Accepted,
    pub collapsed: bool,
}

impl TestCase {
    pub fn new(input_str: &str, expected_str: &str) -> Self {
        let mut inp_content = TextArea::default();
        inp_content.insert_str(input_str);

        let mut exp_content = TextArea::default();
        exp_content.insert_str(expected_str);

        Self {
            inp_content,
            exp_content,
            got_content: None,
            got_box: VisualState::new(),
            expected_box: VisualState::new(),
            input_box: VisualState::new(),
            collapse_toggle_area: VisualState::new(),
            second_title: None,
            ac: Accepted::None,
            collapsed: false,
        }
    }

    pub fn row_height(&self) -> usize {
        if self.collapsed { 2 } else { 18 }
    }

    pub fn draw_tc(&mut self, frame: &mut Frame, area: Rect, title: &str, active_box: ActiveBox, is_editing: bool) {
        self.collapse_toggle_area.rect = Rect {
            x: area.x,
            y: area.y,
            width: area.width,
            height: 2
        };
        
        let format_title = format!("{} {}", if self.collapsed { "▶" } else { "▼" }, title);
        let mut tc_block = block(Some(&format_title)).borders(Borders::TOP).padding(Padding::ZERO).border_type(BorderType::LightDoubleDashed);
        if let Some(second_title) = &self.second_title {
            tc_block = tc_block.title(Line::from(second_title.as_str()).alignment(Right));
        };

        tc_block = match self.ac {
            Accepted::AC => tc_block.border_style(Color::Green).title_style(Color::Green),
            Accepted::Other => tc_block.border_style(Color::Red).title_style(Color::Red),
            Accepted::None => tc_block.border_style(Color::Reset).title_style(Color::Reset),
        };
        
        if !self.collapsed {
            let tc_inner = tc_block.inner(area);
            let v = Layout::vertical([Percentage(50), Percentage(50)]).split(tc_inner);
            let h = Layout::horizontal([Percentage(50), Percentage(50)]).split(v[1]);
    
            self.input_box.rect = v[0];
            self.expected_box.rect = h[0];
            self.got_box.rect = h[1];
    
            Self::render_pane(frame, &mut self.inp_content, &self.input_box, " Input ", matches!(active_box, ActiveBox::Input) && is_editing, is_editing, &self.ac);
            Self::render_pane(frame, &mut self.exp_content, &self.expected_box, " Expected ", matches!(active_box, ActiveBox::Expected) && is_editing, is_editing, &self.ac);
    
            let got_text = self.got_content.clone().unwrap_or(format!("run the test to get the results"));
            let got_panel = Paragraph::new(got_text)
                .block(block(Some(" Got ")).border_style(Color::Blue).title_alignment(Right))
                .scroll(self.got_box.scroll);
            frame.render_widget(got_panel, self.got_box.rect);
        } else {
            self.input_box.rect = Rect::default();
            self.expected_box.rect = Rect::default();
            self.got_box.rect = Rect::default();
        }
        
        frame.render_widget(tc_block, area);
    }

    pub fn render_pane(frame: &mut Frame, textarea: &mut TextArea<'static>, state: &VisualState, title: &str, is_active: bool, is_editing: bool, ac: &Accepted) {
        let (border_color, cursor_style) = if is_active && is_editing {
            (Color::LightGreen, Style::default().add_modifier(Modifier::REVERSED))
        } else if matches!(ac, Accepted::AC)  {
            (Color::Green, Style::default())
        } else {
            (Color::Blue, Style::default())
        };

        let pane_block = block(Some(title)).border_style(border_color).title_alignment(Right);

        if is_editing {
            textarea.set_cursor_style(cursor_style);
            textarea.set_block(pane_block);
            frame.render_widget(textarea as &TextArea, state.rect);
        } else {
            let text = textarea.lines().join("\n");
            let panel = Paragraph::new(text).block(pane_block).scroll(state.scroll);
            frame.render_widget(panel, state.rect);
        }
    }

    pub fn handle_mouse(&mut self, mouse: &MouseEvent) -> bool {
        if let MouseEventKind::Down(MouseButton::Left) = mouse.kind {
            if self.collapse_toggle_area.check_hover(mouse) {
                self.collapsed = !self.collapsed;
                return true;
            }
        }
        
        let (state, v_lines, h_chars) = if self.input_box.check_hover(mouse) {
            (
                &mut self.input_box,
                self.inp_content.lines().len() as u16,
                self.inp_content.lines().iter().map(|l| l.len()).max().unwrap_or(0) as u16
            )
        } else if self.expected_box.check_hover(mouse) {
            (
                &mut self.expected_box,
                self.exp_content.lines().len() as u16,
                self.exp_content.lines().iter().map(|l| l.len()).max().unwrap_or(0) as u16
            )
        } else if self.got_box.check_hover(mouse) {
            match &self.got_content {
                Some(text) => (
                    &mut self.got_box,
                    text.lines().count() as u16,
                    text.lines().map(|s| s.len()).max().unwrap_or(0) as u16
                ),
                None => (&mut self.got_box, 0, 0)
            }
        } else {
            return false;
        };

        match mouse.kind {
            MouseEventKind::ScrollDown => {
                if state.scroll.0 < v_lines.saturating_sub(state.rect.height.saturating_sub(2)) {
                    state.scroll.0 += 1;
                } /* else { return false; } */
            },
            MouseEventKind::ScrollUp => {
                if state.scroll.0 > 0 {
                    state.scroll.0 -= 1;
                } /* else { return false; } */
            },
            MouseEventKind::ScrollLeft => {
                if state.scroll.1 > 0 {
                    state.scroll.1 -= 1;
                }
            },
            MouseEventKind::ScrollRight => {
                let mx_h = h_chars.saturating_sub(state.rect.width.saturating_sub(4));
                if state.scroll.1 < mx_h {
                    state.scroll.1 += 1;
                }
            },
            _ => {}
        };
        
        true
    }
}
