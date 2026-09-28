const RISK = Object.freeze({
  READ: "read",
  LOW: "low",
  APPROVAL: "approval",
  BLOCKED: "blocked"
});

export class PermissionManager {
  constructor() {
    this.policies = new Map([
      ["memory.read", RISK.READ],
      ["memory.write", RISK.LOW],
      ["research.read", RISK.READ],
      ["code.test", RISK.LOW],
      ["code.edit", RISK.APPROVAL],
      ["github.write", RISK.APPROVAL],
      ["cloudflare.deploy", RISK.APPROVAL],
      ["financial.action", RISK.APPROVAL],
      ["credential.access", RISK.BLOCKED]
    ]);
  }

  classify(toolName) {
    return this.policies.get(toolName) ?? RISK.APPROVAL;
  }

  canRun(toolName, { approved = false } = {}) {
    const risk = this.classify(toolName);
    if (risk === RISK.BLOCKED) return { allowed: false, reason: "blocked" };
    if (risk === RISK.APPROVAL && !approved) return { allowed: false, reason: "approval_required" };
    return { allowed: true, reason: risk };
  }
}

export { RISK };
