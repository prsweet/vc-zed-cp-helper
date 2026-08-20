use ratatui::{Frame, crossterm::event::{Event, KeyCode}, layout::{Constraint::{Length, Percentage}, HorizontalAlignment::{Center, Right}, Layout, Rect}, style::{Color, Modifier, Style}, widgets::{Clear, Paragraph}};
use ratatui_textarea::TextArea;

use crate::{components::block, core::{Language::{self, Cpp}, UserConfig}};

pub struct ConfigMenu {
    pub language_area: Language,
    pub fallback_flags_area: TextArea<'static>,
    pub active_field: usize,
    pub user_config: UserConfig
}

impl ConfigMenu {
    pub fn new(config: UserConfig) -> Self {
        let mut fallback_flags = TextArea::default();
        fallback_flags.insert_str(if config.fallback_flags.len() > 0 { config.fallback_flags.join(" ") } else { "".to_string() });

        Self {
            language_area: config.language,
            fallback_flags_area: fallback_flags, 
            active_field: 0,
            user_config: config
        }
    }

    pub fn draw(&mut self, frame: &mut Frame, area: Rect) {
        let popup_area = area.centered(Percentage(50), Length(8));
        let popup_block = block(None).border_style(Color::Yellow).title_alignment(Center);
        let popup_inner = popup_block.inner(popup_area);
        frame.render_widget(Clear, popup_area);
        frame.render_widget(popup_block, popup_area);

        let divisions = Layout::vertical([
            Length(3),
            Length(3)
        ]).split(popup_inner);
        
        let lang_color = if self.active_field == 0 { Color::LightGreen } else { Color::Blue };
        let lang_text = format!("{:?}", self.language_area);
        let lang_panel = Paragraph::new(lang_text)
            .block(block(Some(" Language ")).border_style(lang_color).title_alignment(Right));
        frame.render_widget(lang_panel, divisions[0]);

        let (flag_color, flag_cursor) = if self.active_field == 1 { (Color::LightGreen, Style::default().add_modifier(Modifier::REVERSED)) } else { (Color::Blue, Style::default()) };
        self.fallback_flags_area.set_block(block(Some(" Fallback Flags ")).border_style(flag_color).title_alignment(Right));
        self.fallback_flags_area.set_cursor_style(flag_cursor);
        frame.render_widget(&self.fallback_flags_area, divisions[1]);
    }

    pub fn handle_key(&mut self, event: Event) -> bool {
        if let Event::Key(key) = event {
            match key.code {
                KeyCode::Tab => {
                    self.active_field += 1;
                    self.active_field %= 2;
                },
                // KeyCode::Right | KeyCode::Left if self.active_field == 0 => {
                //     self.language_area = match self.language_area {
                //         Cpp => Python,
                //         Python => Java,
                //         Java => Cpp
                //     };
                // },
                KeyCode::Esc => {
                    let flags_str = self.fallback_flags_area.lines().join("");
                    let flags = flags_str
                        .split_whitespace()
                        .map(|s| s.to_string())
                        .collect();
                    
                    self.user_config.fallback_flags = flags;
                    self.user_config.language = self.language_area;
                    return true;
                },
                _ => {
                    match self.active_field {
                        1 => { self.fallback_flags_area.input(key); },
                        _ => {}
                    };
                },
            }
        }
        false
    }
}