export type Role = "user" | "assistant";

export type Message = {
  id: string;
  role: Role;
  content: string;
  timestamp: number;
};

export const COLOR_PRIMARY = "#58d2e4ff"; 

/**
 * Generate a stable UUID-like ID for a message.
 * Uses timestamp + random suffix for uniqueness.
 */
export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}