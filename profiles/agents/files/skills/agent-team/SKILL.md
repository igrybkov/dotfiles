---
name: agent-team
description: Launch a Claude Code agent team shaped like a standard engineering org (PM, BA, UX, tech lead, architect, engineers, QA, security, devops). Lead runs discovery first, then sizes the team. Use when a task would benefit from parallel exploration, multiple perspectives, or cross-role collaboration.
allowed-tools:
  - Read
  - Glob
  - Grep
  - AskUserQuestion
  - TaskCreate
  - TaskUpdate
  - TaskList
  - Bash(git:*)
  - Bash(gh:*)
---

# Engineering Agent Team Skill

Launch an agent team modeled after a standard engineering org. You (the current session) become the **team lead**: you run discovery, clarify requirements, and only then decide how big the team needs to be.

## Prerequisites

Agent teams must be enabled. They require:
- Claude Code v2.1.32 or later
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in env or settings.json
- `--teammate-mode tmux` (or run inside tmux so `auto` picks split panes)

If the env var isn't set, tell the user to enable it and stop.

## Input

The user provides a task description as the skill argument (`$ARGUMENTS`). If empty, use `AskUserQuestion` to ask what problem they want the team to tackle.

Treat the input as the **problem statement** — not a prescription of the team. You decide the team shape based on the problem.

## Roles available

Each role is backed by a subagent definition in `profiles/agents/files/agents/` (symlinked to `~/.claude/agents/`). When spawning a teammate, reference the subagent by name — its tools allowlist, default model, and philosophy get loaded automatically. The definition body is *appended* to the teammate's system prompt, not substituted for it, so your spawn instructions still drive the task.

| Role | Subagent | Default model | When to spawn |
|------|----------|---------------|---------------|
| **Product Manager** | `product-manager` | sonnet | Almost always — fuzzy requirements or unclear goals |
| **Business Analyst** | `business-analyst` | sonnet | Early, for any task with non-trivial domain logic or stakeholder context |
| **UX Designer** | `ux-designer` | sonnet | Any task that touches a user-facing surface (CLI output, command args, config shape, API responses, docs, GUI) |
| **UI Specialist** | `ui-specialist` | sonnet | Only when the task involves a graphical UI. Skip for CLI/API work — UX Designer covers those. |
| **Tech Lead** | `tech-lead` | opus | **Almost always.** Hands-on breadth role; owns team capacity planning. |
| **System Architect** | `system-architect` | opus | Design-heavy work: new systems, cross-component changes, security/reliability concerns, or when the team needs a vetted design doc before writing code. |
| **Software Engineer** | `software-engineer` | opus or sonnet *(per task)* | Implementation. Model is picked per task: `opus` for gnarly problems (algorithms, correctness, perf, subtle debugging), `sonnet` for well-scoped implementation. Clone the role for parallel tracks (`engineer-1`, `engineer-2`, ...). |
| **QA Engineer** | `qa-automation-engineer` | sonnet | Anything with meaningful test surface |
| **Security Specialist** | `security-specialist` | sonnet | **After** implementation, for any code that handles user input, authn/authz, data storage/egress, external integrations, or secrets. Skip for pure internal refactors. |
| **DevOps Engineer** | `devops-engineer` | opus | **Mandatory** for any task involving deployment topology, CI/CD, k8s/Helm, cloud infra, networking, autoscaling, secrets/IAM, multi-tenancy, IaC, container builds, observability. Bring them in during discovery, not post-hoc. |

When spawning, **name teammates by role** (e.g. `pm`, `ba`, `ux`, `ui`, `tech-lead`, `architect`, `engineer`, `qa`, `security`, `devops`) so you can message them by name later. Clone engineers with suffixes when parallel tracks warrant it (`engineer-1`, `engineer-2`).

**Tech Lead vs System Architect — don't conflate them:**
- **Tech Lead** is hands-on and broad: codebase archaeology, estimates, pairing with BA, breaking down work, unblocking implementers. Present on almost every task.
- **System Architect** is a specialist who goes deep on design and produces documentation (sequence diagrams, component wiring, security model, trade-off analysis) before the team implements. Only brought in when the task justifies thorough up-front design.
- On small/simple tasks, the Tech Lead covers design decisions without needing an Architect. On large/novel tasks, both are present — Architect produces the design, Tech Lead shepherds the team through executing it.

**UX vs UI — don't conflate them:**
- **UX** is about the whole interaction: flag names, command order, error copy, confirmation prompts, output legibility, flow, defaults. Applies even if there's zero GUI.
- **UI** is about the visual layer when there *is* a GUI. If the task is CLI-only, spawn UX, skip UI.

**Picking engineer model per task:** Match model to difficulty. Tricky algorithms, perf-critical paths, correctness-critical code, subtle debugging → `opus`. Well-scoped implementation of clear specs → `sonnet`. Straightforward parallelizable work like scaffolding or mechanical changes → `sonnet`. Don't spin up opus engineers for easy tasks, and don't starve hard tasks on sonnet.

## Workflow

### 1. Discovery phase (small team)

Start with a **minimal discovery team**. Don't spawn the full roster yet.

Default discovery team:
- **BA** (`business-analyst`) — analyzes the domain: entities, business rules, data flows, stakeholders, acceptance criteria, compliance constraints
- **PM** (`product-manager`) — drafts requirements, open questions, success criteria, priorities
- **UX Designer** (`ux-designer`) — maps out the user-facing surface (CLI flags, error states, output formats, GUI flows, docs) and names friction points. Spawn whenever the task touches any user interaction, which is most of the time.
- **Tech Lead** (`tech-lead`) — investigates the existing codebase/system relevant to the task, estimates feasibility and effort, pairs with BA to ground domain analysis in what the code actually does, identifies risks and unknowns. Always present in discovery.

**Add the System Architect** (`system-architect`) **to discovery when:**
- The task spans multiple components or services
- There are competing design approaches that need trade-off analysis
- Security, reliability, or data integrity concerns are material
- The team would benefit from sequence diagrams, component diagrams, or a written design doc before implementation
- The Tech Lead flags during initial discovery that design-level thinking is needed

**Add the DevOps Engineer** (`devops-engineer`) **to discovery when** the task touches any infra concern (see roster table). DevOps joins discovery, not post-hoc — networking, load management, and data isolation are designed in, not retrofitted.

For a small, well-understood task, Tech Lead alone is enough. For a novel or cross-cutting task, spawn the specialists from the start.

Spawn instruction template for discovery (standard case):

> Spawn four teammates to run discovery on this task: **"<task>"**
> - `ba` — use the `business-analyst` subagent type. Analyze the domain: entities, business rules, data flows, stakeholders, compliance/policy constraints. Produce draft acceptance criteria and flag any domain ambiguity.
> - `pm` — use the `product-manager` subagent type. Draft requirements, success criteria, priorities, and explicit open questions for the user. Do not invent scope — flag ambiguity.
> - `ux` — use the `ux-designer` subagent type. Map the user-facing surface this task touches (CLI args, output, errors, flows, docs, or GUI) and flag UX issues, inconsistencies, and unanswered interaction questions.
> - `tech-lead` — use the `tech-lead` subagent type. Investigate the existing codebase/system relevant to this task (prior art, constraints, what's unclear), ground-truth the BA's domain analysis against the code, estimate effort, flag risks. Recommend whether a System Architect is needed.
>
> Each teammate reports back when done. Do not start implementation.

Add an architect to discovery when the task is clearly design-heavy from the outset:

> - `architect` — use the `system-architect` subagent type. Weigh 2–3 design approaches with pros/cons, produce sequence/component diagrams, plan component integration, cover security architecture, and write a design doc the team can execute against. Coordinate with `tech-lead` to keep the design grounded in the existing system. No implementation.

Add a devops engineer to discovery when the task has any infra touchpoint:

> - `devops` — use the `devops-engineer` subagent type. Design networking, load management, and data isolation for this task. Identify the IaC surface, CI/CD changes, observability needs, and cost/ops impact. Coordinate with `architect` and `tech-lead` on integration points.

Drop the UX teammate from discovery only for pure internal refactors with no observable behavior change. Drop the BA only for tasks with no meaningful domain/business logic (e.g. pure infra or refactors).

### 2. Clarify with the user

Once discovery teammates report back, synthesize their findings and present to the user:
- What the task actually is (as understood)
- Open questions from PM
- Technical options/trade-offs from tech lead
- Any blockers or missing info from BA

Use `AskUserQuestion` for concrete decisions. Don't proceed to build the rest of the team until the user has confirmed direction.

### 3. Size the team

**This is the Tech Lead's job to recommend.** After discovery, ask the `tech-lead` explicitly:

> Based on discovery, recommend the capacity needed to deliver this effectively. Count engineers and justify parallelism. Specify the model (`opus` or `sonnet`) for each engineer based on the difficulty of their assigned track. If the work splits into N independent tracks, propose N engineers (clone with suffixes like `engineer-1`, `engineer-2`). If the work is sequential or small, propose a smaller team.

The Tech Lead should think about:
- **Parallelism available**: how many independent tracks/modules/concerns can genuinely run in parallel without file conflicts?
- **Dependencies**: if work is sequential, more engineers add coordination cost without speeding delivery.
- **Complexity**: match model to task. Tricky algorithms, correctness-critical code, perf, or subtle debugging → `opus`. Well-scoped implementation → `sonnet`.
- **Review load**: one QA can reasonably cover 2–3 engineers; more needs a second QA.

**Cloning engineers is explicitly allowed** — spawn multiple `software-engineer` teammates with distinguishing suffixes (`engineer-1`, `engineer-2`, `qa-1`, `qa-2`) and different models per teammate as the Tech Lead recommends.

Present the Tech Lead's proposed team shape (including per-engineer model choices) to the user and get confirmation before spawning.

Conservative default heuristics (use when Tech Lead hasn't recommended otherwise):

- **Tiny scope (1-2 hrs of work)**: Tech Lead + lead can handle it. No Architect, no extra engineers.
- **Medium scope (multi-file change, single concern)**: Tech Lead + 1 `software-engineer` (sonnet) + QA. Add Architect only if design trade-offs are non-obvious.
- **Large scope (multi-component, parallel work)**: Tech Lead + Architect + multiple `software-engineer` teammates (mix of opus for hard tracks and sonnet for well-scoped ones) + QA.
- **Design-heavy, low-implementation**: Tech Lead + Architect, produce a design doc, then re-size for implementation.
- **GUI work confirmed**: add the **UI Specialist** (`ui-specialist`) and keep them in close contact with UX. Skip if the task is CLI/API/backend-only.
- **CLI or API ergonomics work**: no UI Specialist needed — UX Designer stays on through implementation to review flag names, error copy, output formats.
- **Security-sensitive work** (auth, input handling, data storage, external integrations, secrets): Security Specialist is **mandatory** in the post-implementation phase. For especially sensitive work, also bring the Architect in upfront to cover security architecture before code is written.
- **DevOps / infra work**: DevOps Engineer is **mandatory** — bring them in during discovery. For production-grade changes, also pair with Security Specialist and Architect.

Explain the team shape to the user and get confirmation before spawning.

### 4. Assign work

Create tasks in the shared task list (one self-contained unit per task, sized so each teammate has ~5–6 tasks). Assign explicitly to avoid file conflicts — two teammates should not own the same file.

Tell teammates to:
- Check in when blocked instead of guessing
- Not mark tasks complete until work is actually done and verified
- Ping QA when a unit is ready for review

### 5. Monitor and synthesize

- Wait for teammates to finish before starting work yourself.
- If a teammate stalls, redirect or respawn.
- Synthesize findings across teammates for the user.

### 6. Post-implementation security review

Once implementation is done (or a significant reviewable slice is), spawn the Security Specialist to audit the new code **before** declaring the work complete:

> Spawn `security` — use the `security-specialist` subagent type. Review the implementation produced by this team for vulnerabilities and alignment with established security practices. Focus on auth, input validation, injection vectors, secrets handling, authz boundaries, data exposure, dependency CVEs. Reference OWASP Top 10 and any project-specific policy docs (e.g. CLAUDE.md, SECURITY.md). Do not implement fixes — produce a findings report with severity ratings and specific file/line references. Flag anything that should block shipping.

After the Security Specialist reports, feed findings back to the implementation team for remediation, or escalate to the user if a finding changes scope. Re-run the Security Specialist on the fixes if findings were material.

Skip this phase only for pure internal refactors with no change in attack surface.

### 7. Cleanup

When all tasks are done (including security remediation), run cleanup: `Clean up the team`.

## Spawn command for the lead (you)

After reading the user's task, issue a spawn instruction like:

```
Create an agent team for this task: "<user's task>"

Start with discovery only. Spawn:
- ba — use the `business-analyst` subagent. Analyze the domain: entities, business rules, data flows, stakeholders, constraints. Draft acceptance criteria and flag domain ambiguity.
- pm — use the `product-manager` subagent. Draft requirements, success criteria, priorities, and explicit open questions. Flag ambiguity rather than inventing scope.
- ux — use the `ux-designer` subagent. Map the user-facing surface (CLI args, output, errors, flows, docs, GUI if any) and flag UX issues and interaction questions.
- tech-lead — use the `tech-lead` subagent. Investigate the existing codebase/system, ground-truth BA's analysis against the code, estimate effort, flag risks. Recommend whether a System Architect is needed.

Each teammate reports back to me when done. Do not start implementation. I will decide the rest of the team shape (including whether to bring in a System Architect and how many engineers at what model) after reviewing their reports and clarifying with the user.
```

Add `architect` (use the `system-architect` subagent) to the initial spawn when the task is obviously design-heavy, cross-component, or security/reliability-critical. Add `devops` (use the `devops-engineer` subagent) when the task has any infra touchpoint. Drop `ux` only for pure internal refactors.

## Important notes

- **Use subagent types**: always reference a subagent definition by name when spawning. This loads the role's philosophy, tools, and default model. Your spawn instructions get appended on top.
- **Override model when needed**: for `software-engineer` especially, specify `opus` or `sonnet` per teammate in your spawn prompt based on the Tech Lead's recommendation. The definition's default model can be overridden at spawn time.
- **Names matter**: use the role names above so the user and you can message teammates predictably. Add numeric suffixes when cloning.
- **File conflicts**: never give two teammates overlapping file ownership.
- **Token cost**: agent teams use significantly more tokens than a single session. For trivial tasks, skip the skill and just do the work.
- **Cleanup**: always clean up the team when done. Don't leave orphan teammates.

## Anti-patterns

- Don't spawn the full roster upfront — discovery first, then size.
- Don't skip the PM for "obvious" tasks — user goals are rarely as obvious as they look.
- Don't have the lead implement while teammates are still running. Wait for them.
- Don't leave engineer model selection implicit. The Tech Lead picks per task; state it at spawn.
- Don't skip the subagent reference when spawning. Without it, teammates get none of the role philosophy.
