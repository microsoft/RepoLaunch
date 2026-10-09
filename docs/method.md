# Method

Change2Task accepts a normalized historical change and reconstructs an
executable task on a healthy modern revision of the same repository.

## Escalation policy

1. **L1 Patch Reversal** reverse-applies the historical forward maintenance
   patch to the modern revision.
2. **L2 Code Mapping** maps unique historical post-change blocks to their
   pre-change forms. Ambiguous mappings and pure additions/deletions fail
   explicitly.
3. **L3 Agent Reconstruction** asks a pluggable construction agent to recreate
   the unresolved behavior. Failed gates produce structured feedback for the
   next attempt. The published protocol permits at most four L3 attempts.

L1 and L2 are deterministic. L3 is reached only after both deterministic
routes fail.

## Shared gates

Every candidate, regardless of level, passes the same gates:

1. clean patch application on the pinned modern commit;
2. `git diff --check`, basic reparsing, and optional qualification commands;
3. task-family scope enforcement and explicit allowed paths;
4. six-component source-to-modern fidelity;
5. repeated healthy/challenge/restored lifecycle validation.

The lifecycle contract is:

- target checks: pass on healthy, fail on challenge, pass on restored;
- regression checks: pass in all three states;
- repeated observations: stable return code and timeout state.

Infrastructure errors, timeouts, empty patches, and exhausted attempts remain
explicit failures.

## Task families

- **Bug Fix:** reconstruct the historical defect.
- **Feature Addition:** remove or disable the requested capability.
- **Test Generation:** construct an implementation failure while evaluation is
  restricted to tests.
- **API Migration:** reintroduce the obsolete API usage.
- **Security Repair:** reconstruct the vulnerable behavior without weakening
  the oracle or adjacent safeguards.

## Fidelity

The fidelity gate compares the historical forward patch with the modern
restoration patch across changed files, hunks, changed lines, symbols, target
checks, and regression checks. It rejects underspecified or excessively broad
modern reconstructions.
