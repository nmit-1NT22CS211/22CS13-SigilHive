# LangGraph Architecture in SigilHive
## Comprehensive Guide to Adversarial Training Workflow

---

## Table of Contents
1. [What is LangGraph?](#what-is-langgraph)
2. [Why LangGraph for SigilHive?](#why-langgraph-for-sigilhive)
3. [Core Architecture](#core-architecture)
4. [Workflow Phases](#workflow-phases)
5. [State Management](#state-management)
6. [Node Functions](#node-functions)
7. [Data Flow](#data-flow)
8. [Execution Modes](#execution-modes)
9. [Integration with Components](#integration-with-components)
10. [Benefits & Advantages](#benefits--advantages)

---

## What is LangGraph?

**LangGraph** is a framework for building stateful, multi-step workflows with AI agents. It's built on top of LangChain and provides:

- **Graph-based execution model**: Defines steps as nodes and transitions as edges
- **State management**: Maintains a shared state dictionary throughout execution
- **Conditional routing**: Routes execution based on conditions
- **Error handling**: Supports error recovery and fallback paths
- **Type safety**: Uses TypedDict for type-safe state management

### Key Concepts:

| Concept | Purpose |
|---------|---------|
| **StateGraph** | Defines the structure of the workflow |
| **Nodes** | Individual functions that process state and return modified state |
| **Edges** | Connections between nodes (sequential or conditional) |
| **Entry Point** | Starting node of execution |
| **Conditional Edges** | Route execution based on state conditions |
| **Compiled Graph** | Executable workflow that can be invoked |

---

## Why LangGraph for SigilHive?

### Problem We're Solving

The SigilHive adversarial training system needs to orchestrate **multiple complex, interdependent components**:

1. **Gemini AI Agent** - Plans attacks using natural language reasoning
2. **Q-Learning Agent** - Selects strategies based on reinforcement learning
3. **Honeypot Services** - Responds to attacks with realistic behavior
4. **Training Loop** - Updates models based on attack results
5. **Evaluation System** - Measures attack success and learning progress

Without a coordinating framework, these components would require:
- ❌ Tight coupling and complex state passing
- ❌ Manual error handling and recovery
- ❌ Unclear execution flow and dependencies
- ❌ Difficult debugging and monitoring
- ❌ Limited ability to switch execution strategies

### LangGraph Advantages for SigilHive

✅ **Explicit Workflow Definition** - Clear phase-by-phase execution  
✅ **Centralized State Management** - All components share a single state dict  
✅ **Modular Architecture** - Each phase is an independent, testable node  
✅ **Flexible Execution** - Easy to add/remove phases or change order  
✅ **Built-in Looping** - Implements episode/step loops automatically  
✅ **Production Ready** - Designed for complex AI systems at scale  

---

## Core Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                   LangGraphTrainingSystem                      │
│  (Main orchestrator for adversarial training)                  │
└────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────┐         ┌────▼────┐         ┌───▼────┐
   │Adversarial│        │Training │        │  RL    │
   │  Agent   │        │Integration│       │ Agent  │
   │(Gemini)  │        │(Q-Learning)│      │(Double │
   │          │        │            │      │  Q)    │
   └──────────┘        └────────────┘      └────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
  ┌─────▼──────┐    ┌──────▼────┐     ┌───────▼──┐
  │   HTTP     │    │    SSH    │     │ Database │
  │  Honeypot  │    │  Honeypot │     │ Honeypot │
  └────────────┘    └───────────┘     └──────────┘
```

### LangGraph Nodes (Workflow Phases)

The workflow consists of **7 sequential nodes**:

1. **OBSERVE** - Capture honeypot environment state
2. **PLAN** - RL agent selects attack strategy
3. **EXECUTE** - Gemini agent executes the attack
4. **EVALUATE** - Calculate reward and learning signal
5. **LEARN** - Update Q-Learning model
6. **EVOLVE** - Decide on honeypot structure changes (currently disabled)
7. **COMPLETE** - Finalize step and check continuation conditions

---

## Workflow Phases

### Phase 1: OBSERVE 📊
**Function**: `observe_environment()`

```
Purpose: Gather current honeypot state
├── Retrieve last 10 attack results from adversarial agent
├── Extract state features:
│   ├── Suspicion level (0.0 - 1.0)
│   ├── Number of active sessions
│   ├── Commands executed per session
│   ├── Data fields exfiltrated
│   ├── Tables/databases probed
│   ├── Honeypot tokens triggered
│   └── Evolution count
├── Create EnvironmentSnapshot
└── Store in state["environment"]
```

**Key Data Structures**:
- `HoneypotState` - Feature vector for RL (11 dimensions)
- `EnvironmentSnapshot` - Current honeypot metrics

**Output**: Updated state with `environment` field

---

### Phase 2: PLAN 🧠
**Function**: `plan_strategy()`

```
Purpose: RL agent decides attack strategy
├── Convert honeypot state to discrete format
├── Query Q-Learning agent:
│   ├── Check Q-table for state-action values
│   ├── Apply ε-greedy exploration (~10% random)
│   └── Select best action or random action
├── Determine attack parameters:
│   ├── Selected protocol (SSH/HTTP/Database)
│   ├── Attack intensity (1-3 scale)
│   └── Reasoning string
└── Store StrategyDecision in state["strategy_decision"]
```

**Q-Learning Details**:
- State space: ~5^11 discretized states (exponential but manageable)
- Action space: Multiple strategies (depends on configuration)
- Exploration rate (ε): Decays over time
- Model: Double Q-Learning (prevents overestimation)

**Output**: StrategyDecision with protocol, intensity, q_value

---

### Phase 3: EXECUTE 🎯
**Function**: `execute_attack()`

```
Purpose: Execute the planned attack
├── Invoke AdversarialAgent (Gemini-powered):
│   ├── Generate reasoning about attack approach
│   ├── Plan exploitation phases:
│   │   ├── RECONNAISSANCE
│   │   ├── EXPLOITATION
│   │   ├── PERSISTENCE
│   │   ├── EXFILTRATION
│   │   └── CLEANUP
│   └── Execute real attacks against honeypots
├── Gather results:
│   ├── Attack success/failure
│   ├── Data exfiltrated
│   ├── Honeypot responses
│   ├── Suspicion level changes
│   └── Commands executed
└── Store AttackExecution in state["attack_execution"]
```

**Real Attack Implementations**:
- **SSH**: Paramiko-based credential attacks, command injection
- **HTTP**: Request exploitation, path traversal, SQLi simulation
- **Database**: Direct connection attacks, table/data extraction

**Output**: AttackExecution with results and metrics

---

### Phase 4: EVALUATE 📈
**Function**: `evaluate_results()`

```
Purpose: Score attack and calculate learning signal
├── Extract old state (before attack)
├── Observe new state (after attack)
├── Calculate multi-factor reward:
│   ├── Data exfiltration success
│   ├── Suspicion level reduction
│   ├── Attack efficiency
│   ├── Duration efficiency
│   └── Protocol diversity bonus
├── Compute Temporal Difference (TD) error:
│   ├── TD_error = r + γ*Q(s',a') - Q(s,a)
│   ├── Measures learning discrepancy
│   └── Used for prioritized replay
└── Store LearningUpdate in state["learning_update"]
```

**Reward Calculation**:
```python
reward = (
    data_exfiltration_factor * 0.4 +      # 40% weight
    suspicion_delta_factor * -0.3 +        # -30% (avoid detection)
    attack_efficiency_factor * 0.2 +       # 20% weight
    protocol_diversity_factor * 0.1        # 10% bonus
)
```

**Output**: LearningUpdate with reward, td_error, q_table stats

---

### Phase 5: LEARN 🎓
**Function**: `update_learning()`

```
Purpose: Update Q-Learning agent with experience
├── Skip if in EVALUATION mode
├── Create experience tuple:
│   ├── state (old state vector)
│   ├── action (selected strategy)
│   ├── reward (calculated in EVALUATE)
│   ├── next_state (new state vector)
│   └── done (episode terminal flag)
├── Update Q-Learning agent:
│   ├── Prioritized Replay Buffer stores experience
│   ├── N-step returns (n=3) for credit assignment
│   ├── Double Q-learning updates both Q-tables
│   ├── Epsilon decay (exploration → exploitation)
│   └── Adaptive learning rate based on state complexity
└── Update replay buffer statistics
```

**Q-Learning Update Rule**:
```
Q(s,a) ← Q(s,a) + α * [r + γ * max_a' Q(s',a') - Q(s,a)]
```

Where:
- α = learning rate (adaptive)
- γ = 0.99 discount factor
- r = reward signal

**Features**:
- ✅ Prioritized Experience Replay (recent, high-error experiences first)
- ✅ N-Step Returns (n=3 for temporal credit assignment)
- ✅ Double Q-Learning (separate Q1 and Q2 tables)
- ✅ Adaptive Learning Rate (scales with state dimensions)

**Output**: Updated Q-tables, incremented training step counter

---

### Phase 6: EVOLVE 🔄
**Function**: `make_evolution_decision()`

```
Purpose: Decide honeypot defensive evolution
├── Check evolution triggers:
│   ├── Learning reward > 0.3 (good progress)
│   ├── Q-table size > 50 (learned enough states)
│   └── Every N steps (periodic evolution)
├── If should_evolve:
│   └── (Currently disabled - FileStructureEvolver removed)
└── Store EvolutionDecision in state["evolution_decision"]
```

**Note**: File structure evolution was removed as it wasn't improving performance. The system can be extended with other defensive mechanisms.

**Output**: EvolutionDecision with trigger flags

---

### Phase 7: COMPLETE ✅
**Function**: `complete_step()`

```
Purpose: Finalize step and determine continuation
├── Increment step counter
├── Check episode terminal conditions:
│   ├── Max steps per episode reached?
│   ├── Mission success (all data exfiltrated)?
│   ├── Mission failure (suspended by honeypot)?
│   └── Timeout exceeded?
├── Log summary metrics
├── Determine should_continue:
│   ├── true: Loop back to OBSERVE
│   └── false: End episode
└── Update state["should_continue"]
```

**Output**: Updated step counter, should_continue flag

---

## State Management

### TrainingSystemState (TypedDict)

```python
class TrainingSystemState(TypedDict):
    # Tracking
    current_phase: str                      # e.g., "observe", "plan", "execute"
    execution_mode: str                     # "training", "evaluation", "testing"
    episode_number: int                     # Current episode (1-max_episodes)
    step_number: int                        # Current step within episode
    
    # Phase results
    environment: EnvironmentSnapshot        # Current honeypot state
    strategy_decision: StrategyDecision      # RL agent's decision
    attack_execution: AttackExecution       # Attack results
    learning_update: LearningUpdate         # Learning signals
    evolution_decision: EvolutionDecision   # Evolution flags
    
    # Control flow
    should_continue: bool                   # Loop control
    error_message: str                      # Error details if any
    
    # Metrics
    step_rewards: list[float]               # Rewards per step
    episode_summary: dict                   # Episode statistics
```

### State Flow Through Phases

```
Initial State (empty)
    ↓
    │ [OBSERVE]
    ├→ populate: environment
    │
    ├→ [PLAN]
    │  ├→ populate: strategy_decision
    │  │
    │  ├→ [EXECUTE]
    │  │  ├→ populate: attack_execution
    │  │  │
    │  │  ├→ [EVALUATE]
    │  │  │  ├→ populate: learning_update
    │  │  │  │
    │  │  │  ├→ [LEARN]
    │  │  │  │  ├→ update: Q-tables
    │  │  │  │  │
    │  │  │  │  ├→ [EVOLVE]
    │  │  │  │  │  ├→ populate: evolution_decision
    │  │  │  │  │  │
    │  │  │  │  │  ├→ [COMPLETE]
    │  │  │  │  │  │  ├→ update: step statistics
    │  │  │  │  │  │  ├→ set: should_continue
    │  │  │  │  │  │  │
    │  │  │  │  │  │  └→ Conditional Route
    │  │  │  │  │  │     ├─ if should_continue → OBSERVE
    │  │  │  │  │  │     └─ else → END
```

---

## Node Functions

### Detailed Node Implementations

#### 1. `observe_environment(state) → state`

```python
def observe_environment(self, state: TrainingSystemState) -> TrainingSystemState:
    """
    Capture the current honeypot environment.
    
    Responsibilities:
    1. Extract last 10 attacks from agent history
    2. Convert to HoneypotState feature vector
    3. Create EnvironmentSnapshot with metrics
    4. Handle errors gracefully
    """
    # Get recent attacks
    recent_attacks = self.adversarial_agent.attack_history[-10:]
    
    # Extract RL state features
    honeypot_state = self.training_integration.extract_state(recent_attacks)
    
    # Package as snapshot
    snapshot = EnvironmentSnapshot(
        suspicion_level=honeypot_state.suspicion_level,
        active_sessions=honeypot_state.commands_per_session,
        recent_attacks=recent_attacks,
        metrics={...}
    )
    
    state["environment"] = snapshot
    return state
```

#### 2. `plan_strategy(state) → state`

```python
def plan_strategy(self, state: TrainingSystemState) -> TrainingSystemState:
    """
    RL agent selects attack strategy.
    
    Responsibilities:
    1. Discretize honeypot state
    2. Query Q-Learning agent
    3. Select protocol and intensity
    4. Record decision metadata
    """
    honeypot_state = state["environment"].honeypot_state
    state_key = honeypot_state.to_key()
    
    # ε-greedy action selection
    action = shared_rl_agent.select_action(
        state=state_key,
        evaluation=(state["execution_mode"] == "evaluation")
    )
    
    # Select protocol intelligently
    protocol = self._select_protocol(honeypot_state)
    intensity = self._calculate_intensity(honeypot_state.suspicion_level)
    
    state["strategy_decision"] = StrategyDecision(
        action=action,
        q_value=shared_rl_agent.get_q_value(state_key, action),
        epsilon=shared_rl_agent.epsilon,
        selected_protocol=protocol,
        intensity_level=intensity
    )
    
    return state
```

#### 3. `execute_attack(state) → state`

```python
def execute_attack(self, state: TrainingSystemState) -> TrainingSystemState:
    """
    Gemini-powered attack execution.
    
    Responsibilities:
    1. Prepare attack parameters
    2. Invoke AdversarialAgent
    3. Execute multi-phase attacks
    4. Collect results and metrics
    """
    decision = state["strategy_decision"]
    
    # Execute attack
    results = self.adversarial_agent.execute(
        protocol=decision.selected_protocol,
        intensity=decision.intensity_level
    )
    
    # Package results
    execution = AttackExecution(
        attack_results=results,
        total_suspicion_delta=sum(r.suspicion_delta for r in results),
        success=all(r.success for r in results)
    )
    
    state["attack_execution"] = execution
    return state
```

#### 4. `evaluate_results(state) → state`

```python
def evaluate_results(self, state: TrainingSystemState) -> TrainingSystemState:
    """
    Calculate reward and TD error.
    
    Responsibilities:
    1. Compare old vs new environment state
    2. Calculate multi-factor reward
    3. Compute TD error for prioritized replay
    4. Update learning metadata
    """
    old_state = state["environment"].honeypot_state
    
    # Observe new state
    self.observe_environment(state)
    new_state = state["environment"].honeypot_state
    
    # Reward calculation
    reward = calculate_reward(
        old_state_tuple,
        new_state_tuple,
        protocol=state["strategy_decision"].selected_protocol
    )
    
    # TD error
    td_error = reward + γ * max_a Q(new_state, a) - Q(old_state, action)
    
    state["learning_update"] = LearningUpdate(
        reward=reward,
        td_error=td_error,
        q_table_size=len(shared_rl_agent.q_table_a)
    )
    
    return state
```

#### 5. `update_learning(state) → state`

```python
def update_learning(self, state: TrainingSystemState) -> TrainingSystemState:
    """
    Update Q-Learning agent.
    
    Responsibilities:
    1. Skip if evaluation mode
    2. Create experience tuple
    3. Store in prioritized replay buffer
    4. Update Q-tables
    5. Decay exploration rate
    """
    if state["execution_mode"] == "evaluation":
        return state
    
    # Create transition
    old_state = self._state_tuple_from_honeypot(
        state["environment"].honeypot_state
    )
    new_state = self._state_tuple_from_honeypot(
        state["environment"].honeypot_state  # Updated in evaluate
    )
    
    # Update agent
    shared_rl_agent.update(
        state=old_state,
        action=state["strategy_decision"].action,
        reward=state["learning_update"].reward,
        next_state=new_state,
        done=False
    )
    
    return state
```

---

## Data Flow

### Complete Flow Example

```
EPISODE START
    │
    └→ Episode 1, Step 1
        │
        ├─[OBSERVE]─────────────────────┐
        │  Suspicion: 0.3                │
        │  Sessions: 2                   │
        │  Data Exposed: 5 fields        │
        │                                │
        ├─[PLAN]─────────────────────────┤
        │  Action: DATABASE_EXFILTRATION │
        │  Protocol: HTTP                │
        │  Intensity: 2/3                │
        │                                │
        ├─[EXECUTE]─────────────────────┤
        │  Attack phases completed: 4/5 │
        │  Data extracted: 8 records    │
        │  Suspicion delta: +0.15       │
        │                                │
        ├─[EVALUATE]────────────────────┤
        │  Reward: +0.45 (high success)  │
        │  TD Error: 0.032 (low error)   │
        │                                │
        ├─[LEARN]───────────────────────┤
        │  Q-table updated               │
        │  Epsilon: 0.089 (decayed)      │
        │  Buffer size: 234              │
        │                                │
        ├─[EVOLVE]──────────────────────┤
        │  Should evolve: NO (disabled)  │
        │                                │
        ├─[COMPLETE]────────────────────┤
        │  Step 1 complete               │
        │  Should continue: YES          │
        │                                │
        └─ Loop back to OBSERVE
         
         ... (repeat steps) ...
        
        └→ Episode 1, Step 50 (max reached)
           Should continue: NO → Episode ends
```

---

## Execution Modes

### 1. TRAINING Mode
```python
ExecutionMode.TRAINING
├── Updates Q-tables: YES
├── Exploration (ε-greedy): YES
├── Experience replay: YES
├── Learning rate: Adaptive
└── Use case: Initial learning phase
```

### 2. EVALUATION Mode
```python
ExecutionMode.EVALUATION
├── Updates Q-tables: NO
├── Exploration (ε-greedy): NO
├── Experience replay: NO
├── Learning rate: N/A (frozen)
└── Use case: Testing learned policy
```

### 3. TESTING Mode
```python
ExecutionMode.TESTING
├── Updates Q-tables: NO
├── Single attack: YES
├── Experience replay: NO
├── Learning rate: N/A
└── Use case: Debug individual attacks
```

---

## Integration with Components

### 1. AdversarialAgent (Lemini-powered)

```
LangGraph State ──────────────────→ AdversarialAgent
                    execute_attack()
                    ├─ strategy: Protocol (SSH/HTTP/Database)
                    ├─ intensity: 1-3
                    └─ reasoning: from RL decision

AdversarialAgent ───────────────→ LangGraph State
    returns:
    ├─ AttackResult[] with phases and metrics
    ├─ Suspicion delta
    ├─ Data extracted
    ├─ Commands executed
    └─ Honeypot responses
```

### 2. TrainingIntegration (RL Engine)

```
LangGraph State ───────────────→ TrainingIntegration
                extract_state()
                ├─ input: recent_attacks
                └─ processes through state extractor

TrainingIntegration ───────────→ LangGraph State
    returns:
    ├─ HoneypotState (11-dim feature vector)
    ├─ Reward signals
    ├─ TD errors
    └─ Learning metrics
```

### 3. Honeypot Services (HTTP/SSH/Database)

```
LangGraph State ───────────────────→ AdversarialAgent
                                      │
                                      ├─ SSH Attacker
                                      ├─ HTTP Attacker
                                      └─ Database Attacker
                                          │
                                          ├→ SSH Honeypot (port 5555)
                                          ├→ HTTP Honeypot (port 8080)
                                          └→ Database Honeypot (port 2225)

Honeypots ──────────────────────────→ LangGraph State
    returns:
    ├─ Connection success/failure
    ├─ Authentication challenges
    ├─ Available data/tables
    ├─ Honeypot responses
    └─ Suspicion indicators
```

### 4. Shared RL Agent (Q-Learning)

```
LangGraph State ───────────────→ shared_rl_agent
            plan_strategy()
            ├─ state: state_key
            ├─ evaluation: bool
            └─ select_action()

shared_rl_agent ───────────────→ LangGraph State
        returns:
        ├─ action (strategy)
        ├─ q_value (confidence)
        ├─ epsilon (exploration rate)
        └─ reasoning

LangGraph State ───────────────→ shared_rl_agent
            update_learning()
            ├─ state / action / reward / next_state
            └─ update()

shared_rl_agent ───────────────→ LangGraph State
        updated:
        ├─ Q-table_a (primary)
        ├─ Q-table_b (secondary)
        ├─ replay_buffer
        └─ epsilon
```

---

## Benefits & Advantages

### 1. **Modularity**
```
✅ Each phase is independent
✅ Easy to add/remove/modify phases
✅ Test individual nodes in isolation
✅ Reuse nodes in different workflows
```

### 2. **Clarity**
```
✅ Explicit execution sequence
✅ Clear data dependencies
✅ Easy to understand workflow
✅ Better documentation and maintenance
```

### 3. **Robustness**
```
✅ Centralized error handling
✅ Graceful degradation
✅ State recovery
✅ Detailed logging at each phase
```

### 4. **Flexibility**
```
✅ Conditional routing based on state
✅ Multiple execution modes (training/evaluation/testing)
✅ Easy to add parallel paths
✅ Support for branching decisions
```

### 5. **Scalability**
```
✅ Handle complex, multi-component systems
✅ Clear separation of concerns
✅ Independent scaling of components
✅ Production-ready framework
```

### 6. **Debuggability**
```
✅ Inspect state at each phase
✅ Understand decision flow
✅ Trace errors to specific nodes
✅ Replay execution history
```

---

## Workflow Summary

```
┌─────────────────────────────────────────────────────┐
│     LANGGRAPH ADVERSARIAL TRAINING WORKFLOW         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1️⃣  OBSERVE ──→ Extract honeypot state           │
│  2️⃣  PLAN ─────→ RL selects strategy              │
│  3️⃣  EXECUTE ──→ Gemini executes attack           │
│  4️⃣  EVALUATE ─→ Calculate reward signal          │
│  5️⃣  LEARN ────→ Update Q-tables                  │
│  6️⃣  EVOLVE ───→ Adapt honeypot defenses          │
│  7️⃣  COMPLETE ─→ Check continuation               │
│                  └─→ Loop or End                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

| Decision | Reasoning |
|----------|-----------|
| **LangGraph over Manual Loop** | Framework handles complexity, enables monitoring/debugging |
| **Phase-based Architecture** | Clear separation of concerns, easier to extend |
| **Shared State Dictionary** | All components access same data, no coupling |
| **Conditional Routing** | Dynamic loop control based on learned progress |
| **TypedDict for State** | Type safety, IDE support, documentation |
| **Separate Nodes** | Testability, reusability, modularity |
| **Centralized Logging** | Track execution flow, diagnose issues |

---

## Future Enhancements

```
Possible Extensions:
├─ Parallel execution of independent phases
├─ Caching layer for frequent state checks
├─ State persistence/checkpointing
├─ Interactive debugging UI
├─ Visualization of decision tree
├─ Multi-agent coordination
├─ Hierarchical workflow nesting
└─ Performance profiling per phase
```

---

## Conclusion

LangGraph provides SigilHive with a **production-grade workflow orchestration** framework that elegantly solves the complexity of coordinating:

- **AI Agents** (Gemini for planning, Q-Learning for strategy)
- **Real Services** (SSH, HTTP, Database honeypots)
- **Training Loops** (RL feedback)
- **State Management** (centralized, type-safe)
- **Error Handling** (graceful, recoverable)

This architecture enables SigilHive to scale from research prototype to production honeypot training system while maintaining code clarity, maintainability, and debuggability.
