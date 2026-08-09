use std::path::PathBuf;

use serde::{Deserialize, Serialize};

pub mod receiver;
pub mod runner;
pub mod submitter;
pub mod fs_ops;
pub mod editor;

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
    pub time_limit: u32,
    #[serde(rename = "tests")]
    pub test_cases: Vec<ReceivingTestCase>
}

#[derive(Debug)]
pub enum Language {
    Cpp,
    Python,
    Java,
}

#[derive(Debug)]
pub struct UserConfig {
    root_dir: PathBuf,
    language: Language,
    // flags,
    // version,
    // language_code,
}

pub struct SubmitConfig {
    language_code: String,
    question_id: String,
    url: String,
    file_path: String
}

pub enum RunnerCommand {
    RunCode(String), // file_path we will get through $(ZED_FILE)
}

pub enum HelperCommand {
    NewProblem(ActiveProblem),
    RunResult(Vec<String>), // from runner to helper
    EditTestCase, // from 
    AddTestCase,
    ChangeDirectory,
    Error(String),
    UpdateConfig(UserConfig),
    Quit,
}

pub enum SubmitterCommand {
    SubmitCode(SubmitConfig) // its (url, file_path)
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