# Eval run `baseline-v1`

- Passed: `True`
- Product SHA: `cadbdd1013022c98f506ee335fa9072efcc9df6c`
- Product tree hash: `sha256:37501dc7b23f5da682fb9252add29e9761763ba4a183ef3dc6ed4faf34dd10c7`
- Dirty worktree: `True`
- Evaluator: `1.6.0`
- Eligible cases: `86`
- Dataset hashes: `{"datasets/regression/governance.jsonl": "sha256:70495f46b2487a95bda9c5863cfa3d57ae384a2199e072b409f3e1a89f3fdd69", "datasets/regression/harness.jsonl": "sha256:6d0ec855914693e20fcd5bc7ae356ea984164f45b0b779d657fe7dc8d00ad2b4", "datasets/regression/memory_context.jsonl": "sha256:d355382c5017045da223613867275c5b1136b2173e60ce2c700e064a7e79cc7b", "datasets/regression/narrative_npc.jsonl": "sha256:30e96c262d5cadd2a3c5810044e44eb15d75d2d7b96824bf385639269d99f892", "datasets/regression/routing_actions.jsonl": "sha256:ad6f48be2a66f1e5f5b55c5f61bdd9f457dcb611c2568fa0008d35fbf2596bb4", "datasets/regression/state_rules.jsonl": "sha256:4d465f9b7b5e365e9883f243aee2e14a9a1ac78e5f81b93d5350a6a8cf2b2733"}`
- Ruler hashes: `{"__main__.py": "sha256:eb2ed6ea5aece574c9f0804c02806617aefddbd8faf9c236dab244b85c836643", "core/__init__.py": "sha256:d5815280b433f039fbf05976bb50d84f6e75c6ca07dcf7c89d19296824d86077", "core/adapters.py": "sha256:52d869beab838bc6b589214c153438ff9eaf6e690070d9ba499eedf08e857784", "core/compare.py": "sha256:3baeff2f0297ef7fbb9e3bf161a251ff66088ac1b2c99440d0b38e2f215853ef", "core/governance.py": "sha256:7d349216ac55315fb823a01b9a562493c372a9fea121b85b7b6a8b26d6994300", "core/hashing.py": "sha256:2f5cdff5235b59f94a94eb39a76e1114adbb4256917ee5533e3b7853ead6b620", "core/runner.py": "sha256:4f282f8e356b9e4aaa5ce5c9876815acec9b717074f7376292fa7d6caa703540", "core/schemas.py": "sha256:077bd7bee5a3b3a82304fe8996fd14ace4915de97d0d305f03902c7a8ab05014", "evaluators/__init__.py": "sha256:2871832a03e160d238fd7342c53a3bb342639c10b553c579b8974ec55e0cd6b3", "evaluators/exact.py": "sha256:21c39d7a5bb19819115a4073c87d6c1d8471c15830120ab0cfd85be6a0f54e29", "evaluators/memory.py": "sha256:be0cd0bff8396bd8470bdc824ab9f30a984bc7a4156309a998625b95e4802a2d", "evaluators/narrative.py": "sha256:3a2979dfc81b0569ebaea27ea5e5d83cf8c6e7bdd57f22c8f6c80df5397abc5b", "evaluators/projection.py": "sha256:a4946dfc918115811f2419eeedf177afd34d3290094f6c24e7e3712d18870985", "evaluators/routing.py": "sha256:f5d18a68bef529fe270e73ec69e8bd8c74dde0db9caee290d9eb3abb0633b7ee"}`

## Metrics

- `context_forbidden_leak_rate`: `0.000000`
- `context_recall_at_5`: `1.000000`
- `context_token_budget_violation`: `0.000000`
- `exact_match`: `1.000000`
- `memory_mrr`: `0.833333`
- `memory_recall_at_1`: `0.583333`
- `memory_recall_at_3`: `1.000000`
- `memory_recall_at_5`: `1.000000`
- `memory_write_precision`: `1.000000`
- `narrative_claim_accuracy`: `1.000000`
- `narrative_hard_contradictions`: `0.000000`
- `npc_identity_errors`: `0.000000`
- `route_accuracy`: `1.000000`
- `secret_leak_count`: `0.000000`
- `state_transition_pass_rate`: `1.000000`
- `target_accuracy`: `1.000000`

## Aggregates

```json
{
  "layer_outcomes": {
    "context": {
      "error": 0,
      "failed": 0,
      "passed": 8
    },
    "generate": {
      "error": 0,
      "failed": 0,
      "passed": 1
    },
    "retrieve": {
      "error": 0,
      "failed": 0,
      "passed": 7
    },
    "store": {
      "error": 0,
      "failed": 0,
      "passed": 11
    }
  },
  "narrative_reason_matrix": {
    "accepted": {
      "accepted": 14
    },
    "action_incompatible": {
      "action_incompatible": 2
    },
    "current_location": {
      "current_location": 1
    },
    "entity_out_of_scene": {
      "entity_out_of_scene": 2
    },
    "inventory_possession": {
      "inventory_possession": 1
    },
    "lifecycle_contradiction": {
      "lifecycle_contradiction": 2
    },
    "location_region": {
      "location_region": 1
    },
    "npc_identity": {
      "npc_identity": 1
    },
    "player_death": {
      "player_death": 1
    },
    "reward_delta": {
      "reward_delta": 1
    },
    "unrevealed_secret": {
      "unrevealed_secret": 1
    }
  },
  "route_confusion_matrix": {
    "combat_agent": {
      "combat_agent": 5
    },
    "loot": {
      "loot": 7
    },
    "npc_actor": {
      "npc_actor": 3
    },
    "storyteller": {
      "storyteller": 6
    }
  }
}
```

## Cases

- `context.budget.discards-low-score`: **PASS**
- `context.budget.global-cap`: **PASS**
- `context.include.cross-sections`: **PASS**
- `context.memory.expiration`: **PASS**
- `context.trace.unknown-section`: **PASS**
- `context.trace.visibility-reason`: **PASS**
- `context.visibility.hidden-allowed`: **PASS**
- `context.visibility.secret-filtered`: **PASS**
- `memory.generate.boundary`: **PASS**
- `memory.retrieve.exact-top1`: **PASS**
- `memory.retrieve.hidden-allowed`: **PASS**
- `memory.retrieve.multiple-required`: **PASS**
- `memory.retrieve.only-secret`: **PASS**
- `memory.retrieve.relevant-rank2`: **PASS**
- `memory.retrieve.secret-filtered`: **PASS**
- `memory.retrieve.stable-tie`: **PASS**
- `memory.write.canonical-event`: **PASS**
- `memory.write.confirmed-without-source`: **PASS**
- `memory.write.false-player-death`: **PASS**
- `memory.write.inference`: **PASS**
- `memory.write.negated-death`: **PASS**
- `memory.write.npc-identity`: **PASS**
- `memory.write.npc-report`: **PASS**
- `memory.write.player-possession`: **PASS**
- `memory.write.secret-revealed`: **PASS**
- `memory.write.secret-unrevealed`: **PASS**
- `memory.write.supersession`: **PASS**
- `narrative.action.active-travel`: **PASS**
- `narrative.action.death-pending`: **PASS**
- `narrative.action.unconscious-attack`: **PASS**
- `narrative.action.unconscious-recovery`: **PASS**
- `narrative.death.canonical`: **PASS**
- `narrative.death.false`: **PASS**
- `narrative.death.negated`: **PASS**
- `narrative.death.reported`: **PASS**
- `narrative.inventory.actual-possession`: **PASS**
- `narrative.inventory.false-possession`: **PASS**
- `narrative.lifecycle.captive-consistent`: **PASS**
- `narrative.lifecycle.captive-escaped`: **PASS**
- `narrative.lifecycle.dead-consistent`: **PASS**
- `narrative.lifecycle.dead-revived`: **PASS**
- `narrative.location.current-false`: **PASS**
- `narrative.location.current-true`: **PASS**
- `narrative.location.region-false`: **PASS**
- `narrative.npc.identity-false`: **PASS**
- `narrative.npc.identity-true`: **PASS**
- `narrative.reward.false-gold`: **PASS**
- `narrative.reward.true-gold`: **PASS**
- `narrative.scene.absent-npc`: **PASS**
- `narrative.scene.party-present`: **PASS**
- `narrative.scene.present-npc`: **PASS**
- `narrative.scene.wrong-home`: **PASS**
- `narrative.secret.revealed`: **PASS**
- `narrative.secret.unrevealed`: **PASS**
- `routing.combat.active-flee`: **PASS**
- `routing.combat.attack.base`: **PASS**
- `routing.combat.attack.case`: **PASS**
- `routing.combat.attack.punctuation`: **PASS**
- `routing.combat.attack.spacing`: **PASS**
- `routing.loot.craft.forge`: **PASS**
- `routing.loot.craft.keyword`: **PASS**
- `routing.loot.shop.buy`: **PASS**
- `routing.loot.shop.sell`: **PASS**
- `routing.loot.treasure.base`: **PASS**
- `routing.loot.treasure.case`: **PASS**
- `routing.loot.treasure.chest`: **PASS**
- `routing.negative.injection`: **PASS**
- `routing.negative.sql`: **PASS**
- `routing.npc.corvo.accepted-set`: **PASS**
- `routing.npc.corvo.base`: **PASS**
- `routing.npc.corvo.case`: **PASS**
- `routing.story.travel.base`: **PASS**
- `routing.story.travel.case`: **PASS**
- `routing.story.travel.punctuation`: **PASS**
- `routing.story.travel.spacing`: **PASS**
- `state.combat.transition-owner`: **PASS**
- `state.event.npc-killed`: **PASS**
- `state.event.route-replay`: **PASS**
- `state.event.unique-claimed`: **PASS**
- `state.lifecycle.accept-death`: **PASS**
- `state.lifecycle.restore-checkpoint`: **PASS**
- `state.lifecycle.unconscious-readable`: **PASS**
- `state.persistence.migration-idempotent`: **PASS**
- `state.persistence.save-load`: **PASS**
- `state.quest.reward-once`: **PASS**
- `state.rule.set-entity`: **PASS**
