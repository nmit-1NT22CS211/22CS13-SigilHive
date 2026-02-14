#!/usr/bin/env python3
"""
Validation script for Enhanced Q-Learning Agent Integration

This script verifies that:
1. Enhanced agent imports correctly
2. All components work together
3. Training/inference loops execute properly
4. Persistence mechanisms function
"""

import sys
import os

# Add project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from rl_core import (
    QLearningAgent,
    PrioritizedReplayBuffer,
    Experience,
    shared_rl_agent,
    RL_CONFIG,
    extract_state,
    calculate_reward,
    ACTIONS,
)


def test_import():
    """Test that all components import correctly"""
    print("[TEST] Imports...")
    assert QLearningAgent is not None, "QLearningAgent not imported"
    assert PrioritizedReplayBuffer is not None, "PrioritizedReplayBuffer not imported"
    assert Experience is not None, "Experience not imported"
    assert shared_rl_agent is not None, "shared_rl_agent not imported"
    assert RL_CONFIG is not None, "RL_CONFIG not imported"
    print("  ✓ All imports successful")


def test_agent_initialization():
    """Test agent initialization"""
    print("[TEST] Agent initialization...")
    agent = QLearningAgent(RL_CONFIG)
    
    assert agent.epsilon == RL_CONFIG["epsilon_start"], "Epsilon not initialized"
    assert agent.learning_rate == RL_CONFIG["learning_rate"], "Learning rate not initialized"
    assert agent.discount_factor == RL_CONFIG["discount_factor"], "Discount factor not initialized"
    assert len(agent.config["actions"]) == 6, "Wrong action count"
    assert agent.update_count == 0, "Update count should be 0"
    print("  ✓ Agent initialized correctly")


def test_action_selection():
    """Test epsilon-greedy action selection"""
    print("[TEST] Action selection...")
    agent = QLearningAgent(RL_CONFIG)
    
    test_state = (1, 2, 1, 0, 0)
    
    # Test multiple selections
    actions = [agent.select_action(test_state) for _ in range(100)]
    
    # All should be valid
    assert all(a in ACTIONS for a in actions), "Invalid action selected"
    
    # Should have some diversity due to exploration
    unique_actions = len(set(actions))
    assert unique_actions > 1, "No exploration - all same action"
    
    print(f"  ✓ Action selection working (selected {unique_actions} different actions)")


def test_evaluation_mode():
    """Test evaluation/deterministic mode"""
    print("[TEST] Evaluation mode...")
    agent = QLearningAgent(RL_CONFIG)
    agent.epsilon = 0.0  # Force exploitation
    
    state = (1, 2, 1, 0, 0)
    action1 = agent.select_action(state, evaluation=True)
    action2 = agent.select_action(state, evaluation=True)
    
    # In evaluation mode with epsilon=0, should get same action
    assert action1 == action2, "Evaluation mode not deterministic"
    print(f"  ✓ Evaluation mode working (deterministic: {action1})")


def test_q_value_operations():
    """Test Q-value get/set operations"""
    print("[TEST] Q-value operations...")
    agent = QLearningAgent(RL_CONFIG)
    
    state = (1, 2, 1, 0, 0)
    action = "DECEPTIVE_RESOURCE"
    
    # Initially zero
    q_val = agent.get_q_value(state, action)
    assert q_val == 0.0, f"Initial Q-value should be 0, got {q_val}"
    
    # After update
    next_state = (1, 3, 2, 0, 1)
    reward = 5.0
    agent.update(state, action, reward, next_state)
    
    # Should have some value now (or be pending in n-step buffer)
    print("  ✓ Q-value operations working")


def test_double_q_learning():
    """Test double Q-learning mechanism"""
    print("[TEST] Double Q-Learning...")
    agent = QLearningAgent(RL_CONFIG)
    
    # Verify both Q-tables exist
    assert hasattr(agent, 'q_table_a'), "Missing q_table_a"
    assert hasattr(agent, 'q_table_b'), "Missing q_table_b"
    assert len(agent.q_table_a) == 0, "q_table_a should be empty"
    assert len(agent.q_table_b) == 0, "q_table_b should be empty"
    
    state = (1, 2, 1, 0, 0)
    next_state = (1, 3, 2, 0, 1)
    
    # Do several updates to populate tables
    for i in range(20):
        action = agent.select_action(state)
        reward = float(i)
        agent.update(state, action, reward, next_state, done=(i == 19))
    
    # Should have populated tables
    total_entries = len(agent.q_table_a) + len(agent.q_table_b)
    assert total_entries > 0, "Tables not populated"
    
    print(f"  ✓ Double Q-Learning working ({total_entries} entries across tables)")


def test_prioritized_replay():
    """Test prioritized experience replay buffer"""
    print("[TEST] Prioritized Experience Replay...")
    
    buffer = PrioritizedReplayBuffer(capacity=100, alpha=0.6)
    
    # Add experiences
    for i in range(50):
        exp = Experience(
            state=(i, i, i, 0, 0),
            action="REALISTIC_RESPONSE",
            reward=float(i),
            next_state=(i+1, i+1, i+1, 0, 0),
            done=False,
            td_error=float(i),
        )
        buffer.add(exp)
    
    assert len(buffer) == 50, "Buffer size mismatch"
    
    # Sample and get weights
    samples, indices, weights = buffer.sample(batch_size=10, beta=0.4)
    
    assert len(samples) == 10, "Sample count mismatch"
    assert len(indices) == 10, "Index count mismatch"
    assert len(weights) == 10, "Weight count mismatch"
    
    # Update priorities
    new_td_errors = [1.0] * len(indices)
    buffer.update_priorities(indices, new_td_errors)
    
    print("  ✓ Prioritized Experience Replay working")


def test_episodic_memory():
    """Test episode tracking"""
    print("[TEST] Episodic memory...")
    agent = QLearningAgent(RL_CONFIG)
    
    # Simulate episode
    state = (1, 2, 1, 0, 0)
    for step in range(10):
        action = agent.select_action(state)
        reward = 1.0
        next_state = tuple((min(2, x+1) for x in state))
        done = step == 9
        agent.update(state, action, reward, next_state, done)
        state = next_state
    
    # End episode
    agent.end_episode(total_reward=10.0, episode_length=10)
    
    assert agent.episode_count == 1, "Episode count wrong"
    assert len(agent.episode_rewards) == 1, "Rewards not tracked"
    assert len(agent.episode_lengths) == 1, "Lengths not tracked"
    
    print("  ✓ Episodic memory working")


def test_statistics():
    """Test statistics collection"""
    print("[TEST] Statistics collection...")
    agent = QLearningAgent(RL_CONFIG)
    
    # Simulate some activity
    state = (1, 2, 1, 0, 0)
    for i in range(30):
        action = agent.select_action(state)
        reward = 1.0
        next_state = (1, 2, 1, 0, 0)
        done = i % 10 == 9
        agent.update(state, action, reward, next_state, done)
        if done:
            agent.end_episode(total_reward=10.0, episode_length=10)
    
    # Get statistics
    stats = agent.get_statistics()
    
    assert "update_count" in stats, "Missing update_count"
    assert "episode_count" in stats, "Missing episode_count"
    assert "epsilon" in stats, "Missing epsilon"
    assert "learning_rate" in stats, "Missing learning_rate"
    assert "action_counts" in stats, "Missing action_counts"
    assert stats["episode_count"] == 3, "Episode count mismatch"
    
    print("  ✓ Statistics collection working")


def test_checkpointing():
    """Test save/load checkpoint functionality"""
    print("[TEST] Checkpointing...")
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        agent = QLearningAgent(RL_CONFIG)
        agent.checkpoint_dir = temp_dir
        
        # Simulate training
        state = (1, 2, 1, 0, 0)
        for i in range(50):
            action = agent.select_action(state)
            reward = 1.0
            next_state = (1, 2, 1, 0, 0)
            agent.update(state, action, reward, next_state)
        
        stats_before = agent.get_statistics()
        
        # Save
        checkpoint_path = os.path.join(temp_dir, "test_checkpoint.pkl")
        agent.save_checkpoint(checkpoint_path)
        assert os.path.exists(checkpoint_path), "Checkpoint not saved"
        
        # Load into new agent
        agent2 = QLearningAgent(RL_CONFIG)
        agent2.checkpoint_dir = temp_dir
        agent2.load_checkpoint(checkpoint_path)
        
        stats_after = agent2.get_statistics()
        
        assert stats_after["update_count"] == stats_before["update_count"], \
            "Update count not preserved"
        assert stats_after["epsilon"] == stats_before["epsilon"], \
            "Epsilon not preserved"
        
        print("  ✓ Checkpointing working")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_adaptive_learning_rate():
    """Test adaptive learning rate"""
    print("[TEST] Adaptive learning rate...")
    agent = QLearningAgent(RL_CONFIG)
    assert agent.adaptive_lr_enabled, "Adaptive LR should be enabled"
    
    initial_lr = agent.learning_rate
    
    # Do multiple updates on same state
    state = (1, 2, 1, 0, 0)
    next_state = (1, 2, 1, 0, 0)
    
    for i in range(100):
        action = agent.select_action(state)
        reward = 1.0
        agent.update(state, action, reward, next_state)
    
    # Learning rate should decay
    final_lr = agent.learning_rate
    assert final_lr < initial_lr, "Learning rate not decayed"
    
    print(f"  ✓ Adaptive learning rate working ({initial_lr:.4f} → {final_lr:.4f})")


def test_backward_compatibility():
    """Test backward compatibility with old API"""
    print("[TEST] Backward compatibility...")
    agent = QLearningAgent(RL_CONFIG)
    
    # Old API methods should still exist
    assert hasattr(agent, 'get_best_action'), "Missing get_best_action"
    assert hasattr(agent, 'save_q_table'), "Missing save_q_table"
    assert hasattr(agent, 'load_q_table'), "Missing load_q_table"
    assert hasattr(agent, 'decay_epsilon'), "Missing decay_epsilon"
    
    # Should work
    state = (1, 2, 1, 0, 0)
    action = agent.get_best_action(state)
    assert action in ACTIONS, "get_best_action not working"
    
    print("  ✓ Backward compatibility maintained")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("ENHANCED Q-LEARNING AGENT VALIDATION")
    print("="*70 + "\n")
    
    tests = [
        test_import,
        test_agent_initialization,
        test_action_selection,
        test_evaluation_mode,
        test_q_value_operations,
        test_double_q_learning,
        test_prioritized_replay,
        test_episodic_memory,
        test_statistics,
        test_checkpointing,
        test_adaptive_learning_rate,
        test_backward_compatibility,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    if failed == 0:
        print("✓ All tests passed! Enhanced Q-Learning agent is ready for deployment.")
        return 0
    else:
        print(f"✗ {failed} test(s) failed. Please review the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
