"""
Reward calculation module for RL honeypot system.

Computes reward signals based on state transitions to guide
the Q-learning agent toward optimal deception strategies.
"""

from typing import Tuple
from .config import REWARD_CONFIG, STATE_BUCKETS


def calculate_reward(prev_state: Tuple, curr_state: Tuple, protocol: str) -> float:
    """
    Calculate reward for state transition.

    Reward formula:
        r = α·Δduration + β·Δunique - γ₁·detection - γ₂·termination

    Args:
        prev_state: Previous state tuple
        curr_state: Current state tuple
        protocol: "database", "http", or "ssh"

    Returns:
        Reward value (float, can be negative)

    Example:
        >>> prev = (1, 2, 1, 0, 0)
        >>> curr = (1, 3, 2, 0, 1)  # More unique cmds, longer duration, privesc
        >>> calculate_reward(prev, curr, "ssh")
        8.0  # Positive - attacker engaged more
    """
    # Extract state components
    prev_rate, prev_unique, prev_duration, prev_errors, prev_privesc = prev_state
    curr_rate, curr_unique, curr_duration, curr_errors, curr_privesc = curr_state

    # Get reward weights
    alpha = REWARD_CONFIG["alpha"]
    beta = REWARD_CONFIG["beta"]
    gamma1 = REWARD_CONFIG["gamma1"]
    gamma2 = REWARD_CONFIG["gamma2"]

    # Calculate deltas
    delta_duration = curr_duration - prev_duration
    delta_unique = curr_unique - prev_unique

    # Detect honeypot awareness
    detection = 1 if _detect_honeypot_awareness(prev_state, curr_state) else 0

    # Detect early termination
    termination = 1 if _detect_early_termination(prev_state, curr_state) else 0

    # Base reward
    reward = (
        alpha * _duration_bucket_to_seconds(delta_duration)
        + beta * delta_unique
        - gamma1 * detection
        - gamma2 * termination
    )

    # Add protocol-specific bonuses
    bonus = _protocol_specific_bonus(prev_state, curr_state, protocol)
    reward += bonus

    return reward


def _duration_bucket_to_seconds(delta_bucket: int) -> float:
    """
    Convert duration bucket change to approximate seconds.

    Args:
        delta_bucket: Change in duration bucket (-2 to +2)

    Returns:
        Approximate seconds
    """
    # Bucket midpoints: LOW=30s, MED=180s, HIGH=450s
    bucket_midpoints = [30, 180, 450]

    if delta_bucket == 0:
        return 0.0
    elif delta_bucket == 1:
        return 150.0  # ~2.5 minutes
    elif delta_bucket == 2:
        return 420.0  # ~7 minutes
    elif delta_bucket == -1:
        return -150.0
    elif delta_bucket == -2:
        return -420.0
    else:
        return 0.0


def _detect_honeypot_awareness(prev_state: Tuple, curr_state: Tuple) -> bool:
    """
    Detect if attacker suspects honeypot.

    Indicators:
    - Error ratio spike (LOW → HIGH or MED → HIGH)
    - High errors combined with low duration
    - Command rate spike then drop

    Args:
        prev_state: Previous state
        curr_state: Current state

    Returns:
        True if honeypot awareness detected
    """
    prev_rate, prev_unique, prev_duration, prev_errors, prev_privesc = prev_state
    curr_rate, curr_unique, curr_duration, curr_errors, curr_privesc = curr_state

    # Error ratio spike
    if curr_errors == 2 and prev_errors < 2:  # Jumped to HIGH
        return True

    # High errors + short duration
    if curr_errors >= 1 and curr_duration == 0:
        return True

    # Activity spike then drop (testing behavior)
    if prev_rate == 2 and curr_rate == 0:  # HIGH → LOW
        return True

    return False


def _detect_early_termination(prev_state: Tuple, curr_state: Tuple) -> bool:
    """
    Detect premature session end.

    Indicators:
    - Still in LOW duration but no new activity
    - Few unique commands and session appears stalled

    Args:
        prev_state: Previous state
        curr_state: Current state

    Returns:
        True if early termination detected
    """
    prev_rate, prev_unique, prev_duration, prev_errors, prev_privesc = prev_state
    curr_rate, curr_unique, curr_duration, curr_errors, curr_privesc = curr_state

    # Duration still LOW, no new commands
    if curr_duration == 0 and curr_unique <= 2:
        return True

    # Activity dropped to zero
    if prev_rate > 0 and curr_rate == 0 and curr_unique < 3:
        return True

    return False


def _protocol_specific_bonus(
    prev_state: Tuple, curr_state: Tuple, protocol: str
) -> float:
    """
    Add protocol-specific reward bonuses.

    Args:
        prev_state: Previous state
        curr_state: Current state
        protocol: Protocol type

    Returns:
        Bonus reward (float)
    """
    prev_rate, prev_unique, prev_duration, prev_errors, prev_privesc = prev_state
    curr_rate, curr_unique, curr_duration, curr_errors, curr_privesc = curr_state

    bonus = 0.0

    if protocol == "ssh":
        # Privilege escalation attempt bonus
        if curr_privesc and not prev_privesc:
            bonus += REWARD_CONFIG["ssh_privesc_bonus"]

        # Sustained activity bonus
        if curr_rate >= 1 and curr_duration >= 1:
            bonus += REWARD_CONFIG["ssh_file_access_bonus"]

        # High engagement bonus
        if curr_unique >= 2 and curr_duration >= 2:
            bonus += REWARD_CONFIG["ssh_persistence_bonus"]

    elif protocol == "http":
        # Path diversity bonus
        if curr_unique - prev_unique >= 1:
            bonus += REWARD_CONFIG["http_path_diversity_bonus"]

        # Admin access attempt bonus
        if curr_privesc and not prev_privesc:
            bonus += REWARD_CONFIG["http_admin_access_bonus"]

        # Sustained exploration bonus
        if curr_rate >= 1 and curr_unique >= 2:
            bonus += REWARD_CONFIG["http_honeytoken_bonus"]

    elif protocol == "database":
        # Table enumeration bonus
        if curr_unique - prev_unique >= 1:
            bonus += REWARD_CONFIG["db_table_enum_bonus"]

        # Injection attempt bonus
        if curr_privesc and not prev_privesc:
            bonus += REWARD_CONFIG["db_injection_attempt_bonus"]

        # Sustained querying bonus
        if curr_rate >= 1 and curr_unique >= 2 and curr_duration >= 1:
            bonus += REWARD_CONFIG["db_honeytoken_bonus"]

    return bonus


# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    print("Testing reward calculation...\n")

    # Test case 1: Good engagement
    print("Test 1: Attacker exploring more")
    prev = (1, 2, 1, 0, 0)  # MED rate, MED unique, MED duration, LOW errors
    curr = (1, 3, 2, 0, 1)  # HIGH unique, HIGH duration, privesc attempt
    reward = calculate_reward(prev, curr, "ssh")
    print(f"  Previous state: {prev}")
    print(f"  Current state:  {curr}")
    print(f"  Reward: {reward:.2f} (should be positive)\n")

    # Test case 2: Honeypot detection
    print("Test 2: Attacker detected honeypot")
    prev = (1, 2, 1, 0, 0)
    curr = (0, 2, 1, 2, 0)  # LOW rate, HIGH errors (suspicious)
    reward = calculate_reward(prev, curr, "ssh")
    print(f"  Previous state: {prev}")
    print(f"  Current state:  {curr}")
    print(f"  Reward: {reward:.2f} (should be negative)\n")

    # Test case 3: Early termination
    print("Test 3: Attacker disconnected early")
    prev = (1, 1, 0, 0, 0)
    curr = (0, 1, 0, 0, 0)  # No progress, activity stopped
    reward = calculate_reward(prev, curr, "ssh")
    print(f"  Previous state: {prev}")
    print(f"  Current state:  {curr}")
    print(f"  Reward: {reward:.2f} (should be negative)\n")

    # Test case 4: Protocol-specific bonus
    print("Test 4: Database enumeration bonus")
    prev = (1, 1, 1, 0, 0)
    curr = (1, 3, 2, 0, 1)  # More queries, longer session, injection attempt
    reward = calculate_reward(prev, curr, "database")
    print(f"  Previous state: {prev}")
    print(f"  Current state:  {curr}")
    print(f"  Reward: {reward:.2f} (should include DB bonus)\n")
