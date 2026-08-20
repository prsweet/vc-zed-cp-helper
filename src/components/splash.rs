use ratatui::{Frame, layout::{HorizontalAlignment::Center, Rect}, style::{Style, Stylize}};
use tui_big_text::{BigText, PixelSize::Full};

pub fn render(frame: &mut Frame, area: Rect)
{
    let big_text = BigText::builder()
        .pixel_size(Full)
        .style(Style::new().blue())
        .alignment(Center)
        .lines([
            "Welcome".red().into(),
            "To".blue().into(),
            "Z-C-H".white().into()
        ]).build();

    frame.render_widget(big_text, area);
}