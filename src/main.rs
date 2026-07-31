use std::time::Duration;

use crossterm::event;
use ratatui::DefaultTerminal;

use crate::types::*;

mod types;

fn main() -> color_eyre::Result<()>
{
    color_eyre::install()?;
    let mut terminal = ratatui::init();
    let mut helper = Helper::new();
    let result = run_app(&mut terminal, &mut helper);

    ratatui::restore();
    result
}

fn run_app(terminal: &mut DefaultTerminal, helper: &mut Helper) -> color_eyre::Result<()>
{
    loop {
        terminal.draw(|frame| {
            helper.draw(frame);
        })?;

        if event::poll(Duration::from_millis(16))? {
            let event = event::read()?;
            let should_quit = helper.handle_event(event)?;
            if should_quit { break; }
        }
    }
    Ok(())
}