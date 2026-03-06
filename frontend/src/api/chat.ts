import api from './client';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
}

export const sendMessage = (
  messages: ChatMessage[],
  systemPrompt?: string,
  requestType?: string,
): Promise<ChatResponse> =>
  api.post('/chat', {
    messages,
    system_prompt: systemPrompt ?? '',
    ...(requestType ? { request_type: requestType } : {}),
  }).then((r) => r.data);
