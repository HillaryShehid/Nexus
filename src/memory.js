const MAX_MEMORIES = 1000;

function normalize(text) {
  return String(text ?? "").trim().toLowerCase();
}

export class MemoryStore {
  constructor(seed = []) {
    this.items = Array.isArray(seed) ? [...seed] : [];
  }

  remember(text, metadata = {}) {
    const value = String(text ?? "").trim();
    if (!value) return null;

    const item = {
      id: metadata.id ?? crypto.randomUUID(),
      text: value,
      importance: Number.isFinite(metadata.importance) ? metadata.importance : 0.5,
      tags: Array.isArray(metadata.tags) ? metadata.tags : [],
      createdAt: metadata.createdAt ?? new Date().toISOString(),
      lastUsedAt: metadata.lastUsedAt ?? null
    };

    const duplicate = this.items.find(x => normalize(x.text) === normalize(value));
    if (duplicate) {
      duplicate.lastUsedAt = new Date().toISOString();
      duplicate.importance = Math.max(duplicate.importance, item.importance);
      return duplicate;
    }

    this.items.push(item);
    if (this.items.length > MAX_MEMORIES) this.items.splice(0, this.items.length - MAX_MEMORIES);
    return item;
  }

  search(query, limit = 8) {
    const q = normalize(query);
    if (!q) return [];

    const tokens = q.split(/\s+/).filter(Boolean);
    return this.items
      .map(item => {
        const haystack = normalize(item.text);
        const hits = tokens.reduce((n, token) => n + (haystack.includes(token) ? 1 : 0), 0);
        const recency = item.lastUsedAt ? 0.1 : 0;
        return { item, score: hits / Math.max(tokens.length, 1) + item.importance * 0.25 + recency };
      })
      .filter(x => x.score > 0.25)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(x => x.item);
  }

  forget(query) {
    const q = normalize(query);
    const before = this.items.length;
    this.items = this.items.filter(x => normalize(x.text) !== q);
    return before !== this.items.length;
  }

  export() {
    return JSON.parse(JSON.stringify(this.items));
  }
}
