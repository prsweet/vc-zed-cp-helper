use std::{sync::mpsc::Sender, thread};

use tiny_http::{Response, Server};

use crate::core::{ActiveProblem, HelperCommand, PassingCommand::{self, ToHelper, ToRunner}, RunnerCommand};

pub fn spawn_server(tx:Sender<PassingCommand>)
{
    thread::spawn(move || {
        let server = Server::http("127.0.0.1:10043")
            .expect("Could not connect to the port");

        for mut request in server.incoming_requests() {
            let path = &request.url().to_string();
            let mut content = String::new();

            if request.as_reader().read_to_string(&mut content).is_ok() {
                match path.as_str() {
                    "/cmd/r" => {
                        let _ = tx.send(ToRunner(RunnerCommand::RunCode(content)));
                    },
                    "/cmd/e" => {
                        let _ = tx.send(ToHelper(HelperCommand::EditTestCase));
                    },
                    _ => {
                        let problem = serde_json::from_str::<ActiveProblem>(&content);
                        match problem {
                            Ok(problem) => { let _ = tx.send(ToHelper(HelperCommand::NewProblem(problem))); },
                            Err(e) => { eprintln!("Failed to parse JSON!, {}", e); }
                        }
                    }
                }
            }

            let _ = request.respond(Response::empty(200));
        }
    });
}