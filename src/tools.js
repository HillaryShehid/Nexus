export class ToolRegistry {
  constructor(permissionManager) {
    this.permissionManager = permissionManager;
    this.tools = new Map();
  }

  register(name, handler, metadata = {}) {
    if (this.tools.has(name)) throw new Error(`Tool already registered: ${name}`);
    this.tools.set(name, { handler, metadata });
  }

  list() {
    return [...this.tools.entries()].map(([name, tool]) => ({
      name,
      description: tool.metadata.description ?? "",
      risk: this.permissionManager.classify(name)
    }));
  }

  async execute(name, args = {}, options = {}) {
    const tool = this.tools.get(name);
    if (!tool) throw new Error(`Unknown tool: ${name}`);

    const decision = this.permissionManager.canRun(name, options);
    if (!decision.allowed) {
      return { ok: false, error: decision.reason, tool: name };
    }

    try {
      const result = await tool.handler(args);
      return { ok: true, tool: name, result };
    } catch (error) {
      return {
        ok: false,
        tool: name,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }
}
