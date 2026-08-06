use std::{env, io::stdout, path::PathBuf, time::Duration};
use ratatui::{DefaultTerminal, crossterm::{event::{self, DisableMouseCapture, EnableMouseCapture}, execute}};
use std::{sync::mpsc, thread};
use tiny_http::{Response, Server};

use crate::helper::*;
mod helper;
mod components;

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
    let receiver = spawn_server();
    
    loop {
        terminal.draw(|frame| {
            helper.draw(frame);
        })?;
        
        if let Ok(new_problem) = receiver.try_recv() {
            helper.active_problem = Some(new_problem.clone());
            helper.handle_receving(new_problem);
        }
        
        if event::poll(Duration::from_millis(16))? {
            let event = event::read()?;
            let should_quit = helper.handle_event(event)?;
            if should_quit { break; }
        }
    }
    Ok(())
}



pub fn spawn_server() -> mpsc::Receiver<ActiveProblem>
{
    let (tx, rx) = mpsc::channel();

    thread::spawn(move || {
        let server = Server::http("127.0.0.1:10043")
            .expect("Could not connect to the port");

        for mut request in server.incoming_requests() {
            let mut content = String::new();

            if request.as_reader().read_to_string(&mut content).is_ok() {
                let problem = serde_json::from_str::<ActiveProblem>(&content);

                match problem {
                    Ok(send_problem) => { let _ = tx.send(send_problem); },
                    Err(e) => eprintln!("Failed to parse JSON: {}", e)
                }
            }

            let _ = request.respond(Response::empty(200));
        }
    });
    rx
}