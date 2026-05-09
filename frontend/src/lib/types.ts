// Shared types between the OCM daemon's HTTP API and the frontend.
// Keep these aligned with crates/ocm-api/src/openai.rs — the daemon is the
// source of truth for the wire format.

export type Role = 'system' | 'user' | 'assistant';

export interface ChatMessage {
	role: Role;
	content: string;
}

export interface ModelEntry {
	id: string;
	object: 'model';
	created: number;
	owned_by: string;
}

export interface ModelsResponse {
	object: 'list';
	data: ModelEntry[];
}

export interface ChatCompletionResponse {
	id: string;
	object: 'chat.completion';
	created: number;
	model: string;
	choices: Array<{
		index: number;
		message: { role: 'assistant'; content: string };
		finish_reason: string;
	}>;
}
