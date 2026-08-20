use std::{sync::mpsc::{Sender, channel}, thread, time::{Duration, Instant}};

use crate::core::{ActiveProblem, HelperCommand, Language::Cpp, PassingCommand::{self, ToHelper}, RunnerCommand, Verdict, fs_ops::FsOps};

// need a way to track time, for compilation and running

pub fn spawn_runner(main_tx: Sender<PassingCommand>, paths: FsOps) -> Sender<RunnerCommand> {
    let (tx, rx) = channel::<RunnerCommand>();
    thread::spawn(move || {
        while let Ok(command) = rx.recv() {
            match command {
                RunnerCommand::RunCode(problem) => {
                    // println!("compiling with");
                    let results = compile_and_run(&problem, &paths);
                    let _ = main_tx.send(ToHelper(HelperCommand::ShowResult(results)));
                }
            }
        }
    });
    tx
}

pub fn compile_and_run(problem: &ActiveProblem, fs_ops: &FsOps) -> Vec<Verdict> {
    let code_path = problem.code_file.to_string_lossy().to_string();
    let binary_path = fs_ops.binary_dir.join(&problem.name).to_string_lossy().to_string();
    let (config, _) = fs_ops.load_config();

    let _ = match config.language {
        Cpp => {
            let mut flags = config.fallback_flags;
            flags.push(code_path);
            flags.push("-o".to_string());
            flags.push(binary_path.clone());
            match duct::cmd("g++", flags).unchecked().read() { // unchecked so that if this command crash my server will not crash
                Ok(result) => result,
                Err(e) => { return vec![Verdict::CompilationError { error: e.to_string() }] }
            }
        },
    };

    let mut results = Vec::new();

    for tc in problem.test_cases.iter() {
        let executable = match config.language {
            Cpp => duct::cmd!(&binary_path),
        };
        
        let start = Instant::now();

        let execute = match executable
        .stdin_bytes(tc.input.as_bytes().to_vec())
        .stdout_capture()
        .stderr_capture()
        .unchecked()
        .start() {
            Ok(execute) => execute,
            Err(e) => {
                results.push(Verdict::CompilationError { error: e.to_string() });
                continue;
            }
        };

        let time_limit = Duration::from_millis(problem.time_limit);
        let mut final_output = None;

        while start.elapsed() < time_limit {
            if let Ok(Some(output)) = execute.try_wait() {
                final_output = Some(output).cloned();
                break;
            }
            thread::sleep(Duration::from_millis(2));
        }

        if let Some(output) = final_output {
            if output.status.success() {
                results.push(Verdict::Success { output, time: start.elapsed().as_millis() });
            } else {
                results.push(Verdict::RuntimeError { error: output.status.to_string() });
            }
        } else {
            let _ = execute.kill();
            results.push(Verdict::TimeLimitExceeded);
        }
    }

    results
}


