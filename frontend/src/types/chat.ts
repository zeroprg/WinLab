export type Role = "user" | "assistant";

export type CardType = "text" | "onboarding_plan" | "quick_replies" | "kb_result";

export type KBSource = {
  document_id: string;
  title: string;
  source_url?: string | null;
  excerpt: string;
};

export type OnboardingTask = {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "done";
  due_date?: string | null;
};

export type MessageMetadata = {
  choices?: string[];
  sources?: KBSource[];
  plan_id?: string;
  stage?: string;
  progress?: number;
  done?: number;
  total?: number;
  tasks?: OnboardingTask[];
  quick_replies?: string[];
  [key: string]: unknown;
};

export type Message = {
  id: string;
  role: Role;
  content: string;
  timestamp: number;
  card_type?: CardType;
  metadata?: MessageMetadata;
};

export const COLOR_PRIMARY = "#58d2e4ff"; 

/**
 * Generate a stable UUID-like ID for a message.
 * Uses timestamp + random suffix for uniqueness.
 */
export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}