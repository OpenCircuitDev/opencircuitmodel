//! Streaming SHA256-verified model downloader.
//!
//! Refuses to download entries whose registry sha256 is empty — we never
//! distribute unverified weights. Existing files are verified in-place
//! before being re-downloaded; a hash mismatch deletes the file and aborts.

use crate::ModelEntry;
use anyhow::{anyhow, Context, Result};
use futures::StreamExt;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use tokio::io::AsyncWriteExt;

/// Progress callback signature. Called repeatedly with (bytes_downloaded, total_bytes_or_none).
/// `total_bytes_or_none` is None when the upstream response omits Content-Length
/// (some HuggingFace mirrors do this for large files).
pub type ProgressFn = dyn Fn(u64, Option<u64>) + Send + Sync + 'static;

pub async fn download_model(
    entry: &ModelEntry,
    dest_dir: &Path,
    on_progress: Option<Box<ProgressFn>>,
) -> Result<PathBuf> {
    if !entry.is_verifiable() {
        return Err(anyhow!(
            "registry entry {} has empty/invalid sha256 — refusing to download unverified weights",
            entry.id
        ));
    }

    tokio::fs::create_dir_all(dest_dir)
        .await
        .context("create models dir")?;
    let dest = dest_dir.join(format!("{}.gguf", entry.id));

    if dest.exists() {
        tracing::info!(path = %dest.display(), "model file already exists; verifying");
        if verify_sha256(&dest, &entry.sha256).await? {
            tracing::info!(id = %entry.id, "existing model passed sha256 verification");
            return Ok(dest);
        }
        tracing::warn!(path = %dest.display(), "existing model failed verification; redownloading");
        tokio::fs::remove_file(&dest).await.ok();
    }

    tracing::info!(id = %entry.id, url = %entry.url, "starting model download");
    let resp = reqwest::get(&entry.url)
        .await
        .with_context(|| format!("GET {}", entry.url))?
        .error_for_status()
        .with_context(|| format!("upstream rejected {}", entry.url))?;
    let total = resp.content_length();
    let mut hasher = Sha256::new();
    let mut downloaded: u64 = 0;
    let mut file = tokio::fs::File::create(&dest).await?;
    let mut stream = resp.bytes_stream();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("read upstream chunk")?;
        hasher.update(&chunk);
        file.write_all(&chunk).await?;
        downloaded += chunk.len() as u64;
        if let Some(cb) = on_progress.as_deref() {
            cb(downloaded, total);
        }
    }
    file.flush().await?;
    drop(file);

    let actual = hex::encode(hasher.finalize());
    if !actual.eq_ignore_ascii_case(&entry.sha256) {
        tokio::fs::remove_file(&dest).await.ok();
        return Err(anyhow!(
            "sha256 mismatch on {}: expected {}, got {}",
            entry.id,
            entry.sha256,
            actual
        ));
    }
    tracing::info!(id = %entry.id, bytes = downloaded, "model download verified");
    Ok(dest)
}

/// Compute SHA256 over a file on disk and compare to the expected hex string.
/// Returns Err if the file can't be opened; Ok(false) if hashes don't match.
pub async fn verify_sha256(path: &Path, expected: &str) -> Result<bool> {
    use tokio::io::AsyncReadExt;
    let mut file = tokio::fs::File::open(path)
        .await
        .with_context(|| format!("open {}", path.display()))?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 1024 * 1024];
    loop {
        let n = file.read(&mut buf).await?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    let actual = hex::encode(hasher.finalize());
    Ok(actual.eq_ignore_ascii_case(expected))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn verify_sha256_returns_err_when_file_missing() {
        let dir = tempdir().unwrap();
        let p = dir.path().join("nonexistent.bin");
        assert!(verify_sha256(&p, "deadbeef").await.is_err());
    }

    #[tokio::test]
    async fn verify_sha256_matches_known_hash() {
        let dir = tempdir().unwrap();
        let p = dir.path().join("hello.txt");
        tokio::fs::write(&p, b"hello").await.unwrap();
        // sha256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
        let expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";
        assert!(verify_sha256(&p, expected).await.unwrap());
        assert!(!verify_sha256(&p, "0000").await.unwrap());
    }

    #[tokio::test]
    async fn download_refuses_entry_without_sha256() {
        let dir = tempdir().unwrap();
        let entry = ModelEntry {
            id: "no-hash".into(),
            display_name: "test".into(),
            size_mb: 1,
            min_ram_gb: 1,
            url: "http://127.0.0.1:1/will-not-be-fetched".into(),
            sha256: "".into(),
            tier: "default".into(),
        };
        let r = download_model(&entry, dir.path(), None).await;
        assert!(r.is_err());
        let err = format!("{}", r.unwrap_err());
        assert!(err.contains("empty/invalid sha256"), "{err}");
    }
}
