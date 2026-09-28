import test from "node:test";
import assert from "node:assert/strict";
import { NexusCore, PermissionManager, ToolRegistry, verifyResult, claimFromVerification } from "../src/index.js";

test("memory stores and retrieves useful context", () => {
  const nexus = new NexusCore();
  nexus.remember("Hilal is building Nexus as a personal AI companion.", { importance: 1 });
  const result = nexus.think("What am I building?");
  assert.equal(result.type, "conversation");
  assert.equal(result.context.relevantMemory.length, 1);
});

test("reasoning performs arithmetic locally", () => {
  const nexus = new NexusCore();
  const result = nexus.think("calculate (12 + 8) * 3");
  assert.equal(result.type, "calculation");
  assert.equal(result.reply, "60");
});

test("permission gates risky tools", async () => {
  const permissions = new PermissionManager();
  const tools = new ToolRegistry(permissions);
  tools.register("github.write", async () => "changed");
  const blocked = await tools.execute("github.write");
  assert.equal(blocked.ok, false);
  assert.equal(blocked.error, "approval_required");
  const allowed = await tools.execute("github.write", {}, { approved: true });
  assert.equal(allowed.ok, true);
});

test("verification prevents fake success claims", () => {
  const failed = verifyResult("done", { tested: false });
  assert.equal(failed.verified, false);
  assert.match(claimFromVerification("the deployment", failed), /haven't verified/i);

  const passed = verifyResult("done", { tested: true, confirmed: true });
  assert.equal(passed.verified, true);
});
