use ratatui::{crossterm::event::MouseEvent, layout::Rect, style::{Color, Stylize}, widgets::{Block, BorderType, Borders, Padding}};

pub mod dir_terminal;
pub mod splash;
pub mod testcase;
pub mod tc_list;
pub mod config;

pub fn block(title: Option<&str>) -> Block<'static> {
    let if_title = title.unwrap_or("");
    Block::default()
        .title(if_title.to_string())
        .borders(Borders::ALL)
        .bold()
        .title_style(Color::Reset)
        .border_type(BorderType::Rounded)
        .padding(Padding::symmetric(1, 0))
}

pub struct VisualState {
    pub rect: Rect,
    pub scroll: (u16, u16)
}

impl VisualState {
    pub fn new() -> Self {
        Self {
            rect: Rect::default(),
            scroll: (0, 0)
        }
    }

    pub fn check_hover(&self, mouse: &MouseEvent) -> bool {
        mouse.column >= self.rect.x && mouse.column < self.rect.x + self.rect.width && mouse.row >= self.rect.y && mouse.row < self.rect.y + self.rect.height
    }
}