use std::{sync::mpsc::{Sender, channel}, thread};

use crate::core::{PassingCommand, RunnerCommand, fs_ops::load_config};

// need a way to track time, for compilation and running

pub fn spawn_runner(main_tx: Sender<PassingCommand>) -> Sender<RunnerCommand> {
    let (tx, rx) = channel::<RunnerCommand>();
    thread::spawn(move || {
        while let Ok(command) = rx.recv() {
            match command {
                RunnerCommand::RunCode(file_path) => {
                    println!("compiling with");
                    // will write the logic for running later         
                    // get the testcases
                    // it will contain the loop of all testcases i guess
                },
                _ => {}
            }
        }
    });
    tx
}

pub fn get_tc() -> String {
    "tc".to_string()
}

pub fn compile_and_run() -> String {
    let config = load_config();
    // will write the logic later
    "1".to_string()
}