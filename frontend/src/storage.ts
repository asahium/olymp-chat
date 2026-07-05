// Chat helpers. Persistence now lives server-side (see api.getChats/saveChats)
// so recent chats follow the participant across devices.
export const MAX_CHATS = 2;

export function newChatId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}
