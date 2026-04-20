---
name: agent-team
description: Launch a Claude Code agent team shaped like a standard engineering org (PM, BA, staff engineers, architect, junior, QA). Lead runs discovery first, then sizes the team. Use when a task would benefit from parallel exploration, multiple perspectives, or cross-role collaboration.
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

Launch an agent team modeled after a standard engineering org in a large company. You (the current session) become the **team lead**: you run discovery, clarify requirements, and only then decide how big the team needs to be.

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

Spawn teammates from this roster as needed. Not every task needs all roles — default to the smallest team that covers the work.

| Role | Model | Purpose | When to spawn |
|------|-------|---------|---------------|
| **Product Manager (PM)** | sonnet | Clarifies user needs, business value, success criteria, scope | Almost always — fuzzy requirements or unclear goals |
| **Business Analyst (BA)** | sonnet | Domain & business logic analysis — entities, data flows, business rules, stakeholders, acceptance criteria, compliance/policy constraints. Translates fuzzy business intent into concrete specs. | Early, for any task with non-trivial domain logic or stakeholder context |
| **UX Designer** | sonnet | User experience across **all** surfaces — GUI, CLI, API ergonomics, error messages, flag naming, output formatting, prompts, docs. Thinks in user flows, not pixels. | Any task that touches a user-facing surface (CLI output, command args, config shape, API responses, docs, GUI) |
| **UI Specialist** | sonnet | Visual/GUI implementation — components, layout, styling, accessibility, interaction states | Only when the task involves a graphical UI (web, desktop, mobile). Skip for CLI/API work — UX Designer covers those. |
| **Tech Lead** | opus | Breadth-of-responsibility hands-on role. Investigates the existing codebase, estimates work, helps BA analyze domain, breaks tasks down, coordinates the implementation team, guides reviews. Less about deep design, more about getting the team moving in the right direction. **Owns team capacity planning** — decides how many teammates (and of which roles) are actually needed, and can clone roles when the work splits into parallel tracks (e.g. 3 independent modules → 3 engineers). | **Almost always.** The go-to technical presence during discovery and throughout the task. |
| **System Architect** | opus | Design specialist. Weighs trade-offs between competing approaches, draws sequence and component diagrams, plans component integration, covers security architecture and cross-cutting concerns, produces thorough design docs **before** implementation starts. Does not implement. | Design-heavy work: new systems, cross-component changes, anything with security/reliability implications, or when the team needs a vetted design doc before writing code. |
| **Staff Engineer (Opus)** | opus | Deep IC for gnarly problems — tricky algorithms, correctness-critical code, subtle debugging, perf | Hard technical problems during implementation |
| **Staff Engineer (Sonnet)** | sonnet | Senior IC focused on fast, reliable implementation of well-scoped work | Most implementation tasks |
| **Junior Engineer** | sonnet | Straightforward implementation, well-specified tasks, scaffolding | When there's parallelizable grunt work |
| **QA Engineer** | sonnet | Test strategy, edge cases, writing tests, adversarial review | Anything with meaningful test surface |
| **Security Specialist** | sonnet | Post-implementation vulnerability discovery and security review — auth, input handling, injection, secrets, dependency CVEs, authz boundaries, data exposure. Audits against established security practices (OWASP Top 10, project-specific policies). Does not implement. | **After** implementation is done (or a significant slice is), for any code that handles user input, authn/authz, data storage/egress, external integrations, or secrets. Skip for pure internal refactors with no change in attack surface. |
| **DevOps Engineer** | opus | Broad cloud + Kubernetes expertise with an automation-first mindset. Owns networking (ingress/egress, service mesh, VPC/VPN, DNS), load management (autoscaling, load balancers, rate limiting, backpressure, SLOs), and data isolation (tenancy, RBAC/IAM, secrets management, namespace/boundary discipline, data residency). Pushes for IaC, pipelines, and reproducibility over manual operations. **Consulted on any devops work to enforce best practices.** | **Mandatory** for any task involving: deployment topology, CI/CD, k8s manifests/Helm, cloud infra (AWS/GCP/Azure), networking config, autoscaling/HPA/load balancers, secrets/IAM, multi-tenancy, infra-as-code (Terraform/Pulumi/Ansible), container builds, observability pipelines. Skip only for pure application-layer work with no infra touchpoints. |

When spawning, **name teammates by role** (e.g. `pm`, `ba`, `ux`, `ui`, `tech-lead`, `architect`, `staff-opus`, `staff-sonnet`, `junior`, `qa`, `security`, `devops`) so you can message them by name later.

**Tech Lead vs System Architect — don't conflate them:**
- **Tech Lead** is hands-on and broad: codebase archaeology, estimates, pairing with BA, breaking down work, unblocking implementers. Present on almost every task.
- **System Architect** is a specialist who goes deep on design and produces documentation (sequence diagrams, component wiring, security model, trade-off analysis) before the team implements. Only brought in when the task justifies thorough up-front design.
- On small/simple tasks, the Tech Lead covers design decisions without needing an Architect. On large/novel tasks, both are present — Architect produces the design, Tech Lead shepherds the team through executing it.

**UX vs UI — don't conflate them:**
- **UX** is about the whole interaction: flag names, command order, error copy, confirmation prompts, output legibility, flow, defaults. Applies even if there's zero GUI.
- **UI** is about the visual layer when there *is* a GUI. If the task is CLI-only, spawn UX, skip UI.

## Workflow

### 1. Discovery phase (small team)

Start with a **minimal discovery team**. Don't spawn the full roster yet.

Default discovery team:
- **BA** — analyzes the domain: entities, business rules, data flows, stakeholders, acceptance criteria, compliance constraints
- **PM** — drafts requirements, open questions, success criteria, priorities
- **UX Designer** — maps out the user-facing surface (CLI flags, error states, output formats, GUI flows, docs) and names friction points. Spawn whenever the task touches any user interaction, which is most of the time.
- **Tech Lead** — investigates the existing codebase/system relevant to the task, estimates feasibility and effort, pairs with BA to ground domain analysis in what the code actually does, identifies risks and unknowns. Always present in discovery.

**Add the System Architect to discovery when:**
- The task spans multiple components or services
- There are competing design approaches that need trade-off analysis
- Security, reliability, or data integrity concerns are material
- The team would benefit from sequence diagrams, component diagrams, or a written design doc before implementation
- The Tech Lead flags during initial discovery that design-level thinking is needed

For a small, well-understood task, Tech Lead alone is enough. For a novel or cross-cutting task, spawn both from the start.

Spawn instruction template for discovery (standard case):

> Spawn four teammates to run discovery on this task: **"<task>"**
> - `ba` (Business Analyst, sonnet): analyze the domain — entities, business rules, data flows, stakeholders, compliance/policy constraints. Produce draft acceptance criteria and flag any domain ambiguity.
> - `pm` (Product Manager, sonnet): draft requirements, success criteria, priorities, and explicit open questions for the user. Do not invent scope — flag ambiguity.
> - `ux` (UX Designer, sonnet): map the user-facing surface this task touches (CLI args, output, errors, flows, docs, or GUI) and flag UX issues, inconsistencies, and unanswered interaction questions.
> - `tech-lead` (Tech Lead, opus): investigate the existing codebase/system relevant to this task (prior art, constraints, what's unclear), ground-truth the BA's domain analysis against the code, estimate effort, flag risks. Recommend whether a System Architect is needed.
>
> Each teammate reports back when done. Do not start implementation.

Spawn instruction template when the task is clearly design-heavy from the outset — add a fifth teammate:

> - `architect` (System Architect, opus): weigh 2–3 design approaches with pros/cons, produce sequence/component diagrams, plan component integration, cover security architecture, and write a design doc the team can execute against. Coordinate with `tech-lead` to keep the design grounded in the existing system. No implementation.

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

> Based on discovery, recommend the capacity needed to deliver this effectively. Count roles and justify parallelism. If the work splits into N independent tracks, propose N engineers (clone roles as needed — e.g. `staff-sonnet-1`, `staff-sonnet-2`, `junior-1`, `junior-2`). If the work is sequential or small, propose a smaller team.

The Tech Lead should think about:
- **Parallelism available**: how many independent tracks/modules/concerns can genuinely run in parallel without file conflicts?
- **Dependencies**: if work is sequential, more engineers add coordination cost without speeding delivery.
- **Complexity**: harder tracks may justify a Staff (Opus) over a Junior or Staff (Sonnet).
- **Review load**: one QA can reasonably cover 2–3 engineers; more needs a second QA.

**Cloning roles is explicitly allowed** — when the Tech Lead proposes multiple teammates of the same role, spawn them with distinguishing suffixes (`staff-sonnet-1`, `staff-sonnet-2`, `junior-1`, `junior-2`, `qa-1`, `qa-2`) so they can be messaged individually.

Present the Tech Lead's proposed team shape to the user and get confirmation before spawning.

Conservative default heuristics (use when Tech Lead hasn't recommended otherwise):

- **Tiny scope (1-2 hrs of work)**: Tech Lead + lead can handle it. No Architect, no Staff Engineers.
- **Medium scope (multi-file change, single concern)**: keep Tech Lead, add 1 Staff Engineer (Sonnet) + QA. Add Architect only if design trade-offs are non-obvious.
- **Large scope (multi-component, parallel work)**: Tech Lead + Architect + both Staff Engineers + QA + Junior for parallelizable grunt work.
- **Design-heavy, low-implementation**: Tech Lead + Architect, produce a design doc, then re-size for implementation. Skip Junior and QA until implementation starts.
- **GUI work confirmed**: add the **UI Specialist** and keep them in close contact with UX. Skip if the task is CLI/API/backend-only.
- **CLI or API ergonomics work**: no UI Specialist needed — UX Designer stays on through implementation to review flag names, error copy, output formats.
- **Security-sensitive work** (auth, input handling, data storage, external integrations, secrets): Security Specialist is **mandatory** in the post-implementation phase. For especially sensitive work, also bring the Architect in upfront to cover security architecture before code is written.
- **DevOps / infra work** (k8s manifests, Helm, CI/CD, cloud infra, networking, autoscaling, IAM/secrets, multi-tenancy, IaC, container builds, observability): DevOps Engineer is **mandatory** — bring them in during discovery (not post-hoc) so networking, load management, and data isolation are designed in, not retrofitted. For production-grade changes, also pair with Security Specialist and Architect.

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

> Spawn `security` (Security Specialist, sonnet): review the implementation produced by this team for vulnerabilities and alignment with established security practices. Focus on auth, input validation, injection vectors, secrets handling, authz boundaries, data exposure, dependency CVEs. Reference OWASP Top 10 and any project-specific policy docs (e.g. CLAUDE.md, SECURITY.md). Do not implement fixes — produce a findings report with severity ratings and specific file/line references. Flag anything that should block shipping.

After the Security Specialist reports, feed findings back to the implementation team for remediation, or escalate to the user if a finding changes scope. Re-run the Security Specialist on the fixes if findings were material.

Skip this phase only for pure internal refactors with no change in attack surface.

### 7. Cleanup

When all tasks are done (including security remediation), run cleanup: `Clean up the team`.

## Spawn command for the lead (you)

After reading the user's task, issue a spawn instruction like:

```
Create an agent team for this task: "<user's task>"

Start with discovery only. Spawn:
- ba (Business Analyst, sonnet): analyze the domain — entities, business rules, data flows, stakeholders, constraints. Draft acceptance criteria and flag domain ambiguity.
- pm (Product Manager, sonnet): draft requirements, success criteria, priorities, and explicit open questions. Flag ambiguity rather than inventing scope.
- ux (UX Designer, sonnet): map the user-facing surface (CLI args, output, errors, flows, docs, GUI if any) and flag UX issues and interaction questions.
- tech-lead (Tech Lead, opus): investigate the existing codebase/system, ground-truth BA's analysis against the code, estimate effort, flag risks. Recommend whether a System Architect is needed.

Each teammate reports back to me when done. Do not start implementation. I will decide the rest of the team shape (including whether to bring in a System Architect) after reviewing their reports and clarifying with the user.
```

Add `architect` (System Architect, opus) to the initial spawn when the task is obviously design-heavy, cross-component, or security/reliability-critical. Drop `ux` only for pure internal refactors.

## Important notes

- **Models matter**: explicitly specify `opus` or `sonnet` per teammate in your spawn prompt. Don't leave model selection implicit.
- **Names matter**: use the role names from the roster so the user and you can message teammates predictably.
- **File conflicts**: never give two teammates overlapping file ownership.
- **Token cost**: agent teams use significantly more tokens than a single session. For trivial tasks, skip the skill and just do the work.
- **Cleanup**: always clean up the team when done. Don't leave orphan teammates.

## Anti-patterns

- Don't spawn all 7 teammates upfront — discovery first, then size.
- Don't skip the PM for "obvious" tasks — user goals are rarely as obvious as they look.
- Don't have the lead implement while teammates are still running. Wait for them.
- Don't rely on natural-language model hints like "use a fast model" — say `sonnet` or `opus` explicitly.
