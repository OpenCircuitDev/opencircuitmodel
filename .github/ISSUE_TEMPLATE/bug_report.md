---
name: Bug report
about: Daemon crashes, wrong output, OS-level error, etc.
title: "[bug] "
labels: bug
---

**Environment**
- OCM version (or commit SHA): 
- OS + arch (e.g. macOS 14.5 aarch64, Windows 11 x86_64, Ubuntu 24.04 x86_64): 
- Inference backend (llama.cpp / vLLM / other): 
- Mem0 setup (running locally / via OpenMemory MCP / not running): 

**Describe the bug**
A clear and concise description of what went wrong.

**To reproduce**
Steps to reproduce. Minimal reproduction is the most valuable thing you can include.

1. Start daemon with `...`
2. Send `...` to `/v1/chat/completions`
3. Observe `...`

**Expected behavior**
What you expected to happen.

**Actual behavior + logs**
What actually happened. Include relevant output from `~/.ocm/data/logs/` if you can find it.

```
paste daemon logs here
```

**Additional context**
Anything else relevant — model size, recent config changes, hardware specifics.
