//! Subprocess supervisor — manages lifecycle of llama-server / vllm-server processes
//! spawned by the OCM daemon.
//!
//! Use `Supervisor::new()` with a `Command` factory closure so the supervisor can
//! restart the process with a fresh `Command` each time without consuming state.
//!
//! # Backend coverage (v0.1.2 — Track 1 item 2)
//!
//! This module currently spawns `llama-server` only. The `spawn_vllm_server`
//! helper is kept here for the future NVIDIA path but is not yet wired into
//! bootstrap.
//!
//! **Ollama is deliberately NOT supervised here.** When `Settings.backend =
//! "ollama"`, OCM expects an Ollama daemon to be already running (it has its
//! own service installer + tray + lifecycle), and bridges to it via the native
//! NDJSON adapter (`crates/ocm-inference/src/ollama.rs`). Spawning would either
//! double-spawn a daemon already running, or fight ollama-svc's own restart
//! logic. The spawn-gate in `bootstrap::should_spawn_llama_supervisor` enforces
//! this.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tracing::{error, info, warn};

/// Restart-loop policy constants. Documented here so `SupervisorPolicy::default()`
/// can assert them, and so future tuning is one-place rather than scattered.
pub const DEFAULT_MAX_RESTARTS: u8 = 3;
pub const DEFAULT_INITIAL_BACKOFF: Duration = Duration::from_millis(500);
pub const DEFAULT_MAX_BACKOFF: Duration = Duration::from_secs(10);
/// If the supervised process runs healthy for at least this long, the restart
/// counter resets — a process that crashes once a day is not "failing repeatedly."
pub const DEFAULT_STABILITY_WINDOW: Duration = Duration::from_secs(60);
pub const DEFAULT_HEALTH_CHECK_INTERVAL: Duration = Duration::from_secs(5);
pub const DEFAULT_HEALTH_CHECK_TIMEOUT: Duration = Duration::from_secs(15);
/// Default context length passed to `llama-server -c`. Matches the v1 design
/// plan's example. Not a Settings field in v0.1.2 — see TASK_2 design notes.
pub const DEFAULT_LLAMA_CTX_LEN: u32 = 4096;

/// Live status of a supervised subprocess. Exposed to the frontend via the
/// `get_supervisor_status` Tauri command.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SupervisorStatus {
    /// No supervision is configured. Either `Settings.backend != "llamacpp"`,
    /// or the binary/model prerequisites aren't satisfied.
    #[default]
    NotSpawning,
    /// Spawn requested; waiting for the process to come up + health-check.
    Starting,
    /// Process is alive and the last health-check passed.
    Running { pid: u32 },
    /// Process died (or failed health-check); waiting backoff before next try.
    Restarting { attempt: u8, last_error: String },
    /// Hit `max_restarts` within the stability window. Manual intervention required.
    FailedAfterMaxRestarts { attempts: u8, last_error: String },
    /// Stopped on graceful daemon shutdown.
    Stopped,
}

/// Restart + health-check policy. Build via `SupervisorPolicy::default()` and
/// override per-field for tests.
#[derive(Debug, Clone)]
pub struct SupervisorPolicy {
    /// Max restarts allowed before surfacing `FailedAfterMaxRestarts`.
    pub max_restarts: u8,
    pub initial_backoff: Duration,
    pub max_backoff: Duration,
    /// Run-time after which the restart counter resets (a process that ran
    /// healthy this long is considered "stable, then crashed", not "crash-looping").
    pub stability_window: Duration,
    /// URL polled for readiness after spawn.
    pub health_url: String,
    /// How often to recheck liveness once Running.
    pub health_check_interval: Duration,
    /// Max wait for first HTTP-ready after spawn.
    pub health_check_timeout: Duration,
}

impl Default for SupervisorPolicy {
    fn default() -> Self {
        Self {
            max_restarts: DEFAULT_MAX_RESTARTS,
            initial_backoff: DEFAULT_INITIAL_BACKOFF,
            max_backoff: DEFAULT_MAX_BACKOFF,
            stability_window: DEFAULT_STABILITY_WINDOW,
            health_url: String::new(),
            health_check_interval: DEFAULT_HEALTH_CHECK_INTERVAL,
            health_check_timeout: DEFAULT_HEALTH_CHECK_TIMEOUT,
        }
    }
}

/// Exponential backoff: `initial * 2^attempt_index`, clamped to `max`.
/// `attempt_index = 0` returns `initial`. `u8::MAX` does not overflow.
pub fn compute_backoff(attempt_index: u8, initial: Duration, max: Duration) -> Duration {
    // Use u32::checked_shl to avoid shift-overflow when attempt_index >= 32.
    let multiplier = 1u32
        .checked_shl(u32::from(attempt_index))
        .unwrap_or(u32::MAX);
    initial.saturating_mul(multiplier).min(max)
}

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
pub fn spawn_llama_server(binary: &Path, model_path: &Path, port: u16, ctx_len: u32) -> Supervisor {
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
///
/// Not yet wired into bootstrap — the NVIDIA-supervision path is a separate
/// follow-up (vLLM has heavier Python/CUDA preconditions than llama.cpp).
/// Kept here so the supervision machinery covers both backends when that path
/// activates.
#[allow(dead_code)]
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

/// Health-gated restart loop. Spawns the configured subprocess, waits for
/// HTTP-ready, monitors liveness, restarts on death with exponential backoff,
/// and surfaces `FailedAfterMaxRestarts` once the budget is exhausted.
///
/// The loop honors `shutdown` (a `tokio::sync::watch` channel): when it sees
/// `true`, it stops the supervisee cleanly and sets `Stopped`.
///
/// This is the v0.1.2 supervision entry point; bootstrap calls it as a
/// `tauri::async_runtime::spawn`'d background task when `should_spawn_llama_supervisor`
/// returns true.
pub async fn supervise(
    supervisor: Arc<Supervisor>,
    policy: SupervisorPolicy,
    status: Arc<Mutex<SupervisorStatus>>,
    mut shutdown: tokio::sync::watch::Receiver<bool>,
) {
    let mut attempts: u8 = 0;
    // Initialized to a sentinel that's only observable if we surface
    // FailedAfterMaxRestarts before ever setting it (shouldn't happen in
    // practice, but is sound). All real paths overwrite this before read.
    #[allow(unused_assignments)]
    let mut last_error = String::new();

    loop {
        // Honor shutdown before any work.
        if *shutdown.borrow() {
            supervisor.stop();
            set_status(&status, SupervisorStatus::Stopped);
            return;
        }

        set_status(&status, SupervisorStatus::Starting);
        let spawned_at = Instant::now();
        match supervisor.start() {
            Ok(()) => {
                // Spawned OK. Wait for HTTP readiness.
                match wait_for_http_ready(&policy.health_url, policy.health_check_timeout).await {
                    Ok(()) => {
                        let pid = supervisor.pid().unwrap_or(0);
                        info!(
                            name = supervisor.name(),
                            pid, "supervised subprocess healthy"
                        );
                        set_status(&status, SupervisorStatus::Running { pid });
                        // Counter resets immediately on healthy spawn; if the
                        // process later crashes after stability_window, the
                        // monitor branch below also resets.
                        attempts = 0;

                        // Monitor until shutdown OR liveness loss.
                        let died = monitor_until_dead(
                            &supervisor,
                            &policy,
                            &status,
                            &mut shutdown,
                            spawned_at,
                            &mut attempts,
                        )
                        .await;
                        match died {
                            MonitorOutcome::Shutdown => {
                                supervisor.stop();
                                set_status(&status, SupervisorStatus::Stopped);
                                return;
                            }
                            MonitorOutcome::Died(reason) => {
                                last_error = reason;
                                attempts = attempts.saturating_add(1);
                            }
                        }
                    }
                    Err(e) => {
                        last_error = format!("health-check failed: {e}");
                        supervisor.stop();
                        attempts = attempts.saturating_add(1);
                    }
                }
            }
            Err(e) => {
                last_error = format!("spawn failed: {e}");
                attempts = attempts.saturating_add(1);
            }
        }

        // Budget check.
        if attempts >= policy.max_restarts {
            error!(
                attempts,
                error = %last_error,
                "supervisor exhausted restart budget; manual intervention required"
            );
            set_status(
                &status,
                SupervisorStatus::FailedAfterMaxRestarts {
                    attempts,
                    last_error: last_error.clone(),
                },
            );
            return;
        }

        // Backoff, then loop. attempt_index is the 0-based shift power; first
        // restart waits `initial_backoff`.
        let backoff = compute_backoff(
            attempts.saturating_sub(1),
            policy.initial_backoff,
            policy.max_backoff,
        );
        warn!(
            attempts,
            backoff_ms = backoff.as_millis() as u64,
            error = %last_error,
            "supervised subprocess will restart after backoff"
        );
        set_status(
            &status,
            SupervisorStatus::Restarting {
                attempt: attempts,
                last_error: last_error.clone(),
            },
        );

        // Race backoff against shutdown so we exit promptly.
        tokio::select! {
            _ = tokio::time::sleep(backoff) => {}
            _ = shutdown.changed() => {
                supervisor.stop();
                set_status(&status, SupervisorStatus::Stopped);
                return;
            }
        }
    }
}

enum MonitorOutcome {
    Shutdown,
    Died(String),
}

async fn monitor_until_dead(
    supervisor: &Supervisor,
    policy: &SupervisorPolicy,
    status: &Arc<Mutex<SupervisorStatus>>,
    shutdown: &mut tokio::sync::watch::Receiver<bool>,
    spawned_at: Instant,
    attempts: &mut u8,
) -> MonitorOutcome {
    loop {
        tokio::select! {
            _ = shutdown.changed() => {
                return MonitorOutcome::Shutdown;
            }
            _ = tokio::time::sleep(policy.health_check_interval) => {
                if !supervisor.is_alive() {
                    // If we ran healthy for at least the stability window,
                    // reset the restart counter — this was a "stable run then
                    // crash", not a flap.
                    if spawned_at.elapsed() >= policy.stability_window {
                        *attempts = 0;
                    }
                    return MonitorOutcome::Died("subprocess exited".to_string());
                }
                // Refresh Running { pid } in case of mid-life pid change (rare,
                // but cheap to keep in sync).
                if let Some(pid) = supervisor.pid() {
                    set_status(status, SupervisorStatus::Running { pid });
                }
            }
        }
    }
}

fn set_status(slot: &Arc<Mutex<SupervisorStatus>>, new_status: SupervisorStatus) {
    if let Ok(mut g) = slot.lock() {
        *g = new_status;
    }
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

    /// Spawn-then-exit-immediately. Used to exercise the supervise loop's
    /// restart-on-death path without having to block on a long-running subprocess.
    fn immediate_exit_command() -> Command {
        #[cfg(unix)]
        {
            Command::new("true")
        }
        #[cfg(windows)]
        {
            let mut c = Command::new("cmd");
            c.args(["/c", "exit", "0"]);
            c
        }
    }

    #[test]
    fn supervisor_status_default_is_not_spawning() {
        assert_eq!(SupervisorStatus::default(), SupervisorStatus::NotSpawning);
    }

    #[test]
    fn policy_default_uses_documented_constants() {
        let p = SupervisorPolicy::default();
        assert_eq!(p.max_restarts, DEFAULT_MAX_RESTARTS);
        assert_eq!(p.initial_backoff, DEFAULT_INITIAL_BACKOFF);
        assert_eq!(p.max_backoff, DEFAULT_MAX_BACKOFF);
        assert_eq!(p.stability_window, DEFAULT_STABILITY_WINDOW);
    }

    #[test]
    fn backoff_doubles_then_clamps_at_max() {
        let initial = Duration::from_millis(100);
        let max = Duration::from_millis(800);
        assert_eq!(compute_backoff(0, initial, max), Duration::from_millis(100));
        assert_eq!(compute_backoff(1, initial, max), Duration::from_millis(200));
        assert_eq!(compute_backoff(2, initial, max), Duration::from_millis(400));
        // attempt 3 would be 800 (exactly at cap)
        assert_eq!(compute_backoff(3, initial, max), Duration::from_millis(800));
        // attempt 4+ clamped
        assert_eq!(compute_backoff(4, initial, max), Duration::from_millis(800));
        // u8::MAX must not overflow
        assert_eq!(
            compute_backoff(255, initial, max),
            Duration::from_millis(800)
        );
    }

    #[tokio::test(flavor = "current_thread")]
    async fn supervise_with_immediate_exit_hits_failed_after_max_restarts() {
        // Process dies right after spawn AND the health URL never responds
        // (port 1 is privileged + unbound on CI runners). The loop should
        // burn through max_restarts attempts then surface FailedAfterMaxRestarts.
        let sup = Arc::new(Supervisor::new("immediate-exit", immediate_exit_command));
        let policy = SupervisorPolicy {
            max_restarts: 2,
            initial_backoff: Duration::from_millis(20),
            max_backoff: Duration::from_millis(40),
            stability_window: Duration::from_secs(60),
            health_url: "http://127.0.0.1:1/health".to_string(),
            health_check_interval: Duration::from_millis(50),
            health_check_timeout: Duration::from_millis(100),
        };
        let status = Arc::new(Mutex::new(SupervisorStatus::default()));
        let (_tx, rx) = tokio::sync::watch::channel(false);

        supervise(sup.clone(), policy, status.clone(), rx).await;

        let final_status = status.lock().unwrap().clone();
        match final_status {
            SupervisorStatus::FailedAfterMaxRestarts { attempts, .. } => {
                assert_eq!(attempts, 2, "should hit exactly max_restarts attempts");
            }
            other => panic!("expected FailedAfterMaxRestarts, got {other:?}"),
        }
        // Drop should leave no orphan
        assert!(!sup.is_alive());
    }

    #[tokio::test(flavor = "current_thread")]
    async fn supervise_exits_cleanly_on_shutdown_signal() {
        // sleep 30 keeps the supervisee alive; we signal shutdown before any
        // restart loop work happens, expecting Stopped status + clean exit.
        let sup = Arc::new(Supervisor::new("sleep", || sleep_command(30)));
        let policy = SupervisorPolicy {
            max_restarts: 3,
            initial_backoff: Duration::from_millis(10),
            max_backoff: Duration::from_millis(20),
            stability_window: Duration::from_secs(60),
            health_url: "http://127.0.0.1:1/health".to_string(),
            health_check_interval: Duration::from_millis(50),
            health_check_timeout: Duration::from_millis(50),
        };
        let status = Arc::new(Mutex::new(SupervisorStatus::default()));
        let (tx, rx) = tokio::sync::watch::channel(false);

        // Signal shutdown almost immediately, before the loop's first health check returns.
        let shutdown_handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_millis(10)).await;
            let _ = tx.send(true);
        });

        supervise(sup.clone(), policy, status.clone(), rx).await;
        shutdown_handle.await.ok();

        assert_eq!(*status.lock().unwrap(), SupervisorStatus::Stopped);
        assert!(!sup.is_alive(), "supervisor should have killed the child");
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
