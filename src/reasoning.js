function safeArithmetic(expression) {
  const cleaned = String(expression)
    .replaceAll("×", "*")
    .replaceAll("÷", "/")
    .replaceAll("−", "-")
    .trim();

  if (!/^[0-9+\-*/%.()\s]+$/.test(cleaned)) return null;

  try {
    // This expression is intentionally limited to arithmetic characters only.
    const value = Function('"use strict"; return (' + cleaned + ')')();
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

export function reason(input, context = {}) {
  const text = String(input ?? "").trim();
  const lower = text.toLowerCase();

  const arithmeticCandidate = lower
    .replace(/^(calculate|calc|solve|what is|what's)\s*/i, "")
    .trim();

  if (/[0-9][0-9+\-*/%.()\s×÷−]*[0-9]/.test(arithmeticCandidate)) {
    const value = safeArithmetic(arithmeticCandidate);
    if (value !== null) {
      return {
        type: "calculation",
        confidence: 0.99,
        reply: String(value),
        plan: ["parse arithmetic", "evaluate locally", "return verified result"]
      };
    }
  }

  if (/^(remember|don't forget)\b/i.test(text)) {
    return { type: "memory_write", confidence: 0.98, plan: ["extract memory", "store with user approval policy"] };
  }

  if (/\b(research|look up|find out|investigate)\b/i.test(lower)) {
    return { type: "research", confidence: 0.95, plan: ["search available sources", "inspect results", "rank evidence", "store useful knowledge"] };
  }

  if (/\b(fix|broken|error|bug|not working)\b/i.test(lower)) {
    return { type: "debug", confidence: 0.9, plan: ["inspect failure", "identify cause", "propose fix", "test", "verify"] };
  }

  if (/\b(build|make|create|code|website|project)\b/i.test(lower)) {
    return { type: "build", confidence: 0.88, plan: ["understand requirements", "plan implementation", "edit", "test", "verify"] };
  }

  return {
    type: "conversation",
    confidence: 0.35,
    context,
    plan: ["use available memory and context", "answer without inventing facts"]
  };
}
