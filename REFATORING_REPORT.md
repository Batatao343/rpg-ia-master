# Refactoring Report — RPG Engine V8.0

This review focuses on robustness, state hygiene, cohesion, and RPG fidelity. Each item references the current code and proposes concrete refactors.

## Critical Fixes (Crash/Stability)

1. **Preserve world/quest data on engine updates**
   - `apply_state_update` returns only messages, player, enemies, party, and NPCs, discarding `world`, `next`, and other keys. Any node that calls it wipes quest plans and location metadata on the next turn.
   - **Fix:** Merge the update deltas back into the existing state instead of rebuilding a partial dict (e.g., start from `new_state = {**state}` and override changed sections), or explicitly include `world`/`next` in the return payload.
   - Evidence: `apply_state_update` return block omits `world` entirely.【F:engine_utils.py†L178-L184】

2. **Guard message assumptions in combat/storyteller**
   - `combat_node` assumes `state["messages"][-1]` exists and is a `HumanMessage`/`AIMessage`; an empty history or non-human tail will crash before the router short-circuits. `storyteller_node` also early-returns if the last message is not human, but still indexes `messages[-1]` earlier.
   - **Fix:** Protect reads with `if not messages: ...` and branch before indexing; ensure combat can emit a friendly message and route back to storyteller when invoked without human input.
   - Evidence: direct `messages[-1]` access in `combat_node` and `storyteller_node` without preceding emptiness check.【F:agents/combat.py†L33-L47】【F:agents/storyteller.py†L19-L29】

3. **Harden LLM/RAG calls with retries/fallbacks**
   - Router and RAG calls fail open: router catches any exception and silently routes to storyteller without logging; RAG queries in storyteller/combat are not guarded. A temporary vector-store issue will yield confusing narratives.
   - **Fix:** Add structured logging and a retry policy around router and RAG calls; surface a short AI message explaining the fallback when confidence/lookup fails.
   - Evidence: router exception handler returns storyteller with no log; storyteller/combat call `query_rag` without try/except.【F:agents/router.py†L69-L90】【F:agents/storyteller.py†L32-L49】【F:agents/combat.py†L62-L71】

4. **Quest plan consumption can underflow**
   - Storyteller pops the first quest step every turn without checking length; if the plan is already empty (e.g., failed generation), `quest_plan[0]` will raise.
   - **Fix:** Guard accesses with `if quest_plan:` and regenerate/retain when empty; avoid removing steps when generation fails.
   - Evidence: `active_step = quest_plan[0]` executed even if list may be empty after location change logic.【F:agents/storyteller.py†L30-L43】

## Architectural Tweaks (Cohesion/State Hygiene)

1. **Introduce a validated `GameStateModel`**
   - State is a `TypedDict` with no runtime enforcement; nodes freely mutate keys and types. Adopt a Pydantic `GameStateModel` (with nested models for player/world/messages) to validate inputs/outputs at graph boundaries and supply defaults.
   - Evidence: current `GameState` is a loose `TypedDict` lacking validation/defaults for quest plan, messages, or NPC schema.【F:state.py†L6-L77】

2. **Centralize history trimming in the graph**
   - `sanitize_history` is only called in the CLI loop; nodes invoked via other runners/tests can still accumulate unbounded histories.
   - **Fix:** Apply sanitization inside the LangGraph supervisor (after each turn) or in a middleware node so every entry point benefits from rolling-window summaries.
   - Evidence: CLI loop calls sanitizer once per invoke; no equivalent in graph/state utilities.【F:app.py†L39-L59】

3. **Maintain quest metadata alongside world state**
   - Router and storyteller depend on `quest_plan`, but engine updates do not carry forward `world`. Refactor node outputs to merge rather than replace state slices, and consider incrementing a `turn_count` to drive periodic planner refreshes.
   - Evidence: `apply_state_update` drops `world`; storyteller refreshes plan on location change but lacks turn tracking.【F:engine_utils.py†L178-L184】【F:agents/storyteller.py†L30-L44】

4. **Deterministic routing with confidence plus actionable fallback**
   - Router currently asks for clarification when confidence < 0.4 but does not persist any hint for downstream nodes (e.g., intended NPC). Capture the last inferred target and store it in state for re-try after user clarification; log confidence to aid debugging.
   - Evidence: router returns only a clarification message and storyteller route on low confidence.【F:agents/router.py†L75-L90】

## RPG Polish (Fidelity/Mechanics)

1. **Enforce dice/tool mediation on damage**
   - `execute_engine` allows LLM-crafted `hp_updates` even if no dice tool was called (when `last_tool` exists). Add a check to reject/clip damage updates when no `roll_dice` observation precedes them, or require a tool call in the same turn before applying HP changes.
   - Evidence: damage updates are applied regardless of whether a tool was invoked in this turn.【F:engine_utils.py†L86-L107】【F:engine_utils.py†L151-L169】

2. **Separate player intent from mechanics in combat prompts**
   - Boss Tree-of-Thoughts output is injected directly into the system message without verifying compatibility with rules or dice outcomes. Consider asking the LLM to propose actions, then run mechanics via tools/validators before applying effects.
   - Evidence: `_tree_of_thoughts_strategy` returns narrative directives merged into combat prompt without tool gating.【F:agents/combat.py†L72-L111】【F:agents/combat.py†L113-L150】

3. **Keep storyteller aligned to quest plan**
   - Storyteller removes the active step but doesn’t store completed steps or revalidate when the player diverges. Track `quest_plan_completed` and prompt the planner when steps stall, keeping arcs coherent.
   - Evidence: quest steps are popped with no record of completion; location change triggers full reset only.【F:agents/storyteller.py†L36-L50】

4. **Trim NPC aggression side effects**
   - When converting NPCs to enemies, their social memory is dropped. Preserve a link (e.g., `origin_npc`) so post-combat consequences can reference prior relationships and avoid lore breaks.
   - Evidence: NPC removal on hostility doesn’t keep prior persona/relationship details beyond copied template fields.【F:agents/combat.py†L41-L69】

---
These changes aim to prevent runtime crashes, preserve narrative state, and reinforce tabletop-like mechanics while keeping LLM outputs bounded and auditable.
