use std::{env, io::stdout, sync::mpsc::channel, time::Duration};
use ratatui::{DefaultTerminal, crossterm::{event::{self, DisableMouseCapture, EnableMouseCapture}, execute}};
use crate::{core::{HelperCommand, PassingCommand::{self, ToHelper}, SubmitterCommand, fs_ops::FsOps, receiver::spawn_server, runner::spawn_runner}, helper::Helper};
mod helper;
mod components;
mod core;
mod error;

fn main() -> color_eyre::Result<()>
{
    let fs_ops = FsOps::new();
    let initial_dir = env::current_dir().unwrap_or_default();

    let mut terminal = ratatui::init();
    let mut helper = Helper::new(initial_dir, &fs_ops);

    let _ = execute!(stdout(), EnableMouseCapture);
    let result = run_app(&mut terminal, &mut helper);
    let _ = execute!(stdout(), DisableMouseCapture);

    ratatui::restore();
    result
}

fn run_app(terminal: &mut DefaultTerminal, helper: &mut Helper) -> color_eyre::Result<()>
{
    let (main_tx, main_rx) = channel::<PassingCommand>();
    let runner_tx = spawn_runner(main_tx.clone(), helper.fs_ops.clone());
    spawn_server(main_tx.clone());
    
    loop {
        terminal.draw(|frame| {
            helper.draw(frame);
        })?;
        
        if let Ok(send_to) = main_rx.try_recv() {
            match send_to {
                PassingCommand::ToRunner(msg) => { let _ = runner_tx.send(msg); },
                PassingCommand::ToSubmitter(msg) => {
                    match msg {
                        SubmitterCommand::SubmitCode(config) => {
                            // will do this later and code here will change
                        }
                    }
                },
                PassingCommand::ToHelper(msg) => {
                    match msg {
                        HelperCommand::New(problem) => { helper.wire_received_tc(problem); },
                        HelperCommand::Add => { helper.cmd_add(); },
                        HelperCommand::Edit => { helper.cmd_edit(); }
                        HelperCommand::ShowResult(results) => { helper.show_results(results); }
                        HelperCommand::Run => {
                            if let Some(cmd) = helper.cmd_run() {
                                let _ = main_tx.send(cmd);
                            }
                        },
                        _ => {}
                    }
                }
            }
        }
        
        if event::poll(Duration::from_millis(16))? {
            while event::poll(Duration::from_millis(0))? {
                let event = event::read()?;
                if let Some(passing_command) = helper.handle_event(event) {
                    if matches!(passing_command, ToHelper(HelperCommand::Quit)) { return Ok(()) }
                    let _ = main_tx.send(passing_command);
                }
            }
        }
    }
}

/*
 * main thread: UI,
 * 2nd thread: receiving server
 * 3rd thread: code runner
 */