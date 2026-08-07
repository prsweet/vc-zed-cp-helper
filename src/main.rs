use std::{env, io::stdout, path::PathBuf, time::Duration};
use ratatui::{DefaultTerminal, crossterm::{event::{self, DisableMouseCapture, EnableMouseCapture}, execute}};

use crate::{core::receiver, helper::Helper};
mod helper;
mod components;
mod core;

fn main() -> color_eyre::Result<()>
{
    let mut terminal = ratatui::init();

    let _ = execute!(stdout(), EnableMouseCapture);

    let initial_dir = match env::args().nth(1) {
        Some(path) => PathBuf::from(path),
        None => env::current_dir().unwrap_or_default()
    };
    
    let mut helper = Helper::new(initial_dir);
    let result = run_app(&mut terminal, &mut helper);

    let _ = execute!(stdout(), DisableMouseCapture);

    ratatui::restore();
    result
}

fn run_app(terminal: &mut DefaultTerminal, helper: &mut Helper) -> color_eyre::Result<()>
{
    let receiver = receiver::spawn_server();
    
    loop {
        terminal.draw(|frame| {
            helper.draw(frame);
        })?;
        
        if let Ok(new_problem) = receiver.try_recv() {
            helper.active_problem = Some(new_problem.clone());
            helper.wire_received_tc(new_problem);
        }
        
        if event::poll(Duration::from_millis(16))? {
            let event = event::read()?;
            let should_quit = helper.handle_event(event)?;
            if should_quit { break; }
        }
    }
    Ok(())
}