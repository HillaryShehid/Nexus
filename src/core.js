import { MemoryStore } from "./memory.js";
import { reason } from "./reasoning.js";
import { PermissionManager } from "./permissions.js";
import { ToolRegistry } from "./tools.js";

export class NexusCore {
  constructor({ memory = [], lessons = [] } = {}) {
    this.memory = new MemoryStore(memory);
    this.lessons = Array.isArray(lessons) ? [...lessons] : [];
    this.permissions = new PermissionManager();
    this.tools = new ToolRegistry(this.permissions);
    this.conversation = [];
  }

  remember(text, metadata = {}) {
    return this.memory.remember(text, metadata);
  }

  learnLesson(lesson) {
    const value = String(lesson ?? "").trim();
    if (!value) return null;
    const item = { id: crypto.randomUUID(), lesson: value, createdAt: new Date().toISOString() };
    this.lessons.push(item);
    return item;
  }

  think(input) {
    const memory = this.memory.search(input, 6);
    const context = {
      recentConversation: this.conversation.slice(-8),
      relevantMemory: memory,
      lessons: this.lessons.slice(-8)
    };
    const decision = reason(input, context);
    this.conversation.push({ role: "user", text: String(input), at: new Date().toISOString() });
    return decision;
  }

  snapshot() {
    return {
      version: "0.4.1",
      memory: this.memory.export(),
      lessons: [...this.lessons],
      conversation: [...this.conversation]
    };
  }
}
