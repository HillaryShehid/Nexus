export function verifyResult(result, evidence = {}) {
  const checks = [];

  if (result === undefined) checks.push({ name: "result_exists", pass: false });
  else checks.push({ name: "result_exists", pass: true });

  if (evidence.tested !== undefined) {
    checks.push({ name: "tested", pass: evidence.tested === true });
  }

  if (evidence.source !== undefined) {
    checks.push({ name: "source_present", pass: Boolean(evidence.source) });
  }

  if (evidence.confirmed !== undefined) {
    checks.push({ name: "confirmed", pass: evidence.confirmed === true });
  }

  return {
    verified: checks.every(check => check.pass),
    checks
  };
}

export function claimFromVerification(action, verification) {
  if (!verification.verified) {
    return `I haven't verified that I completed ${action} yet.`;
  }
  return `Verified: ${action}.`;
}
