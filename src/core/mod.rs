use std::{path::PathBuf, process::Output};

use derive_name::VariantName;
use serde::{Deserialize, Serialize};

pub mod receiver;
pub mod runner;
pub mod submitter;
pub mod fs_ops;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ReceivingTestCase {
    pub input: String,
    #[serde(rename = "output")]
    pub expected_output: String
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ActiveProblem {
    pub name: String,
    pub url: String,
    #[serde(rename = "timeLimit")]
    pub time_limit: u64,
    #[serde(rename = "tests")]
    pub test_cases: Vec<ReceivingTestCase>,
    #[serde(default)]
    pub code_file: PathBuf
}

#[derive(Debug, Serialize, Clone, Copy, Deserialize)]
pub enum Language {
    Cpp,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UserConfig {
    pub language: Language,
    pub fallback_flags: Vec<String>
}

pub struct SubmitConfig {
    language_code: String,
    question_id: String,
    url: String,
    file_path: String
}

pub enum RunnerCommand {
    RunCode(ActiveProblem), // file_path we will get through $(ZED_FILE)
}

#[derive(Debug, VariantName)]
pub enum Verdict {
    Success {
        output: Output,
        time: u128
    },
    TimeLimitExceeded,
    CompilationError,
    RuntimeError,
}

pub enum HelperCommand {
    New(ActiveProblem),
    Run,
    Edit,
    ShowResult(Vec<Verdict>),
    Add,
    Error(String),
    Quit,
}

pub enum SubmitterCommand {
    SubmitCode(SubmitConfig)
}

pub enum PassingCommand {
    ToHelper(HelperCommand),
    ToRunner(RunnerCommand),
    ToSubmitter(SubmitterCommand)
}

/*
 * these are the command based on what i am telling the actor to do
 * runner: runnercommand,
 * receiver: receivercommand,
 * helper: helpercommand
 * 
 * but to avoid polluting the either enum or receiving transmitter by giving all tx to receiver
 * we can use envelope enums
 */