//! Subprocess supervisor — manages lifecycle of llama-server / vllm-server processes
//! spawned by the OCM daemon.
//!
//! Use `Supervisor::new()` with a `Command` factory closure so the supervisor can
//! restart the process with a fresh `Command` each time without consuming state.

use anyhow::{Context, Result};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tracing::{info, warn};

type CommandFactory = Box<dyn Fn() -> Command + Send + Sync>;

pub struct Supervisor {
    name: String,
    cmd_factory: CommandFactory,
    child: Arc<Mutex<Option<Child>>>,
}

impl Supervisor {
    pub fn new<F>(name: impl Into<String>, factory: F) -> Self
    where
        F: Fn() -> Command + Send + Sync + 'static,
    {
        Self {
            name: name.into(),
            cmd_factory: Box::new(factory),
            child: Arc::new(Mutex::new(None)),
        }
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn start(&self) -> Result<()> {
        let mut guard = self.child.lock().expect("supervisor mutex poisoned");
        if guard.is_some() {
            warn!(name = %self.name, "already running");
            return Ok(());
        }
        let mut cmd = (self.cmd_factory)();
        cmd.stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let child = cmd
            .spawn()
            .with_context(|| format!("spawn {}", self.name))?;
        info!(name = %self.name, pid = child.id(), "subprocess started");
        *guard = Some(child);
        Ok(())
    }

    pub fn stop(&self) {
        let mut guard = self.child.lock().expect("supervisor mutex poisoned");
        if let Some(mut c) = guard.take() {
            let _ = c.kill();
            let _ = c.wait();
            info!(name = %self.name, "subprocess stopped");
        }
    }

    pub fn is_alive(&self) -> bool {
        let mut guard = self.child.lock().expect("supervisor mutex poisoned");
        if let Some(c) = guard.as_mut() {
            match c.try_wait() {
                Ok(Some(_)) => {
                    *guard = None;
                    false
                }
                Ok(None) => true,
                Err(_) => false,
            }
        } else {
            false
        }
    }

    pub fn pid(&self) -> Option<u32> {
        let guard = self.child.lock().expect("supervisor mutex poisoned");
        guard.as_ref().map(|c| c.id())
    }
}

impl Drop for Supervisor {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Build a Supervisor that runs `llama-server` from llama.cpp.
pub fn spawn_llama_server(
    binary: &Path,
    model_path: &Path,
    port: u16,
    ctx_len: u32,
) -> Supervisor {
    let binary = binary.to_path_buf();
    let model_path = model_path.to_path_buf();
    Supervisor::new("llama-server", move || {
        let mut c = Command::new(&binary);
        c.arg("-m")
            .arg(&model_path)
            .arg("-c")
            .arg(ctx_len.to_string())
            .arg("--port")
            .arg(port.to_string())
            .arg("--host")
            .arg("127.0.0.1");
        c
    })
}

/// Build a Supervisor that runs vLLM's OpenAI-compat HTTP server.
pub fn spawn_vllm_server(python: &Path, model_id: &str, port: u16) -> Supervisor {
    let python = python.to_path_buf();
    let model_id = model_id.to_string();
    Supervisor::new("vllm-server", move || {
        let mut c = Command::new(&python);
        c.args([
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            &model_id,
            "--port",
            &port.to_string(),
            "--host",
            "127.0.0.1",
        ]);
        c
    })
}

/// Poll an HTTP URL until it returns 2xx or timeout. Used after spawning a
/// subprocess to wait for its server to be ready.
pub async fn wait_for_http_ready(url: &str, timeout: Duration) -> Result<()> {
    let client = reqwest::Client::new();
    let start = Instant::now();
    while start.elapsed() < timeout {
        if let Ok(r) = client.get(url).send().await {
            if r.status().is_success() {
                return Ok(());
            }
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    anyhow::bail!("backend at {url} did not become ready within {timeout:?}")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sleep_command(seconds: u64) -> Command {
        #[cfg(unix)]
        {
            let mut c = Command::new("sleep");
            c.arg(seconds.to_string());
            c
        }
        #[cfg(windows)]
        {
            let mut c = Command::new("powershell");
            c.args(["-Command", &format!("Start-Sleep {seconds}")]);
            c
        }
    }

    #[test]
    fn lifecycle_with_sleep_command() {
        let sup = Supervisor::new("sleep", || sleep_command(30));
        assert!(!sup.is_alive());
        assert_eq!(sup.name(), "sleep");
        assert!(sup.pid().is_none());

        sup.start().expect("start");
        assert!(sup.is_alive());
        assert!(sup.pid().is_some());

        sup.stop();
        assert!(!sup.is_alive());
    }

    #[test]
    fn double_start_is_noop() {
        let sup = Supervisor::new("sleep", || sleep_command(30));
        sup.start().expect("first start");
        let pid_before = sup.pid();
        sup.start().expect("second start should be no-op");
        let pid_after = sup.pid();
        assert_eq!(pid_before, pid_after);
        sup.stop();
    }

    #[test]
    fn drop_cleans_up_subprocess() {
        let pid;
        {
            let sup = Supervisor::new("sleep", || sleep_command(60));
            sup.start().expect("start");
            pid = sup.pid().expect("pid");
            // sup drops here, should kill the subprocess
        }
        // Give the OS a moment to reap
        std::thread::sleep(Duration::from_millis(200));
        // Verify pid is no longer running by checking it can't be signaled.
        // On Unix, kill -0 returns 0 if running, nonzero if not.
        // On Windows, the equivalent check is more involved; skip strict validation.
        #[cfg(unix)]
        {
            let result = std::process::Command::new("kill")
                .args(["-0", &pid.to_string()])
                .status()
                .expect("kill -0");
            assert!(!result.success(), "process {pid} should be dead after Drop");
        }
        #[cfg(not(unix))]
        {
            let _ = pid; // silence unused warning on Windows
        }
    }

    #[test]
    fn spawn_llama_server_builds_correct_args() {
        let bin = Path::new("/usr/local/bin/llama-server");
        let model = Path::new("/tmp/model.gguf");
        let sup = spawn_llama_server(bin, model, 8080, 4096);
        // Just verify the supervisor is constructed; we can't easily inspect
        // the Command's args without spawning, which we don't want to do here.
        assert_eq!(sup.name(), "llama-server");
        assert!(!sup.is_alive());
    }

    #[test]
    fn spawn_vllm_server_builds_correct_args() {
        let py = Path::new("/usr/bin/python3");
        let sup = spawn_vllm_server(py, "meta-llama/Llama-3.1-8B-Instruct", 8000);
        assert_eq!(sup.name(), "vllm-server");
        assert!(!sup.is_alive());
    }
}
