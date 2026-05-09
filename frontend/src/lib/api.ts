import type { ChatCompletionResponse, ChatMessage, ModelsResponse } from './types';

// In dev, Vite proxies /v1/* to the daemon at 127.0.0.1:7300 (see
// vite.config.ts). In Tauri prod, the webview shares localhost origin
// with the daemon so direct fetches against /v1/* resolve naturally.
const BASE = '';

export async function listModels(): Promise<string[]> {
	const r = await fetch(`${BASE}/v1/models`);
	if (!r.ok) {
		throw new Error(`models endpoint returned ${r.status}: ${await r.text()}`);
	}
	const body = (await r.json()) as ModelsResponse;
	return body.data.map((m) => m.id);
}

export async function chat(model: string, messages: ChatMessage[]): Promise<string> {
	const r = await fetch(`${BASE}/v1/chat/completions`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ model, messages, stream: false })
	});
	if (!r.ok) {
		throw new Error(`chat endpoint returned ${r.status}: ${await r.text()}`);
	}
	const body = (await r.json()) as ChatCompletionResponse;
	const content = body.choices?.[0]?.message?.content;
	if (typeof content !== 'string') {
		throw new Error(`chat response missing choices[0].message.content`);
	}
	return content;
}

/**
 * Stream a chat completion using SSE. Each `data: {...}` chunk is parsed and
 * the assistant token is appended via onToken. Resolves when the stream
 * emits `data: [DONE]` or the underlying connection closes.
 */
export async function chatStream(
	model: string,
	messages: ChatMessage[],
	onToken: (token: string) => void,
	signal?: AbortSignal
): Promise<void> {
	const r = await fetch(`${BASE}/v1/chat/completions`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ model, messages, stream: true }),
		signal
	});
	if (!r.ok || !r.body) {
		throw new Error(`stream endpoint returned ${r.status}: ${r.ok ? 'no body' : await r.text()}`);
	}

	const reader = r.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';
	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		// SSE messages are separated by blank lines. Process complete frames
		// from the buffer head; carry the incomplete tail forward.
		let idx: number;
		while ((idx = buffer.indexOf('\n\n')) !== -1) {
			const frame = buffer.slice(0, idx);
			buffer = buffer.slice(idx + 2);
			for (const line of frame.split('\n')) {
				if (!line.startsWith('data:')) continue;
				const payload = line.slice(5).trim();
				if (payload === '[DONE]') return;
				try {
					const evt = JSON.parse(payload);
					const delta = evt?.choices?.[0]?.delta?.content;
					if (typeof delta === 'string' && delta.length > 0) {
						onToken(delta);
					}
				} catch {
					// ignore malformed frames; the daemon may emit keepalives
				}
			}
		}
	}
}
