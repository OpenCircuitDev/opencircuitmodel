//! Backend selector — auto-detect platform and pick the right backend.
//!
//! Decision rules per spec v0.3:
//! - macOS  -> llama.cpp + Metal (default), MLX-LM opt-in (TBD)
//! - Linux + CUDA detected -> vLLM
//! - Linux without CUDA -> llama.cpp (CPU)
//! - Windows -> llama.cpp
//! - everything else -> llama.cpp (safest fallback)

use crate::{llamacpp::LlamaCpp, vllm::Vllm, InferenceBackend};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BackendKind {
    LlamaCpp,
    Vllm,
}

impl BackendKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            BackendKind::LlamaCpp => "llama.cpp",
            BackendKind::Vllm => "vLLM",
        }
    }
}

pub fn detect_backend_kind() -> BackendKind {
    if cfg!(target_os = "macos") {
        BackendKind::LlamaCpp
    } else if cfg!(target_os = "linux") && has_cuda() {
        BackendKind::Vllm
    } else {
        BackendKind::LlamaCpp
    }
}

#[cfg(target_os = "linux")]
fn has_cuda() -> bool {
    use std::path::Path;
    Path::new("/usr/lib/x86_64-linux-gnu/libcuda.so.1").exists()
        || Path::new("/usr/lib64/libcuda.so.1").exists()
        || Path::new("/usr/lib/aarch64-linux-gnu/libcuda.so.1").exists()
}

#[cfg(not(target_os = "linux"))]
fn has_cuda() -> bool {
    false
}

pub fn make_backend(base_url: String) -> Box<dyn InferenceBackend> {
    match detect_backend_kind() {
        BackendKind::Vllm => Box::new(Vllm::new(base_url)),
        BackendKind::LlamaCpp => Box::new(LlamaCpp::new(base_url)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detect_returns_one_of_two_kinds() {
        let kind = detect_backend_kind();
        assert!(matches!(kind, BackendKind::LlamaCpp | BackendKind::Vllm));
    }

    #[test]
    fn macos_picks_llamacpp() {
        if cfg!(target_os = "macos") {
            assert_eq!(detect_backend_kind(), BackendKind::LlamaCpp);
        }
    }

    #[test]
    fn windows_picks_llamacpp() {
        if cfg!(target_os = "windows") {
            assert_eq!(detect_backend_kind(), BackendKind::LlamaCpp);
        }
    }

    #[test]
    fn cpu_only_linux_picks_llamacpp() {
        // On Linux with no CUDA libraries (the GitHub Actions ubuntu runner case),
        // detect_backend_kind() must NOT pick vLLM.
        if cfg!(target_os = "linux") && !has_cuda() {
            assert_eq!(detect_backend_kind(), BackendKind::LlamaCpp);
        }
    }

    #[test]
    fn make_backend_returns_correct_name() {
        let backend = make_backend("http://localhost:8080".to_string());
        let expected = match detect_backend_kind() {
            BackendKind::LlamaCpp => "llama.cpp",
            BackendKind::Vllm => "vLLM",
        };
        assert_eq!(backend.name(), expected);
    }

    #[test]
    fn backend_kind_as_str_matches_name() {
        assert_eq!(BackendKind::LlamaCpp.as_str(), "llama.cpp");
        assert_eq!(BackendKind::Vllm.as_str(), "vLLM");
    }
}
