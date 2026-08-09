use ratatui::{style::{Color, Stylize}, widgets::{Block, BorderType, Borders, Padding}};

pub mod dir_terminal;
mod splash;
pub mod testcase;
pub mod tc_list;

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