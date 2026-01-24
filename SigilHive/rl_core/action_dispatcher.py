"""
Action space definitions for the RL honeypot system.

Defines the 6 discrete actions the agent can take and provides
descriptions for each action across different protocols.
"""

from typing import Optional

# ==============================================================================
# ACTION SPACE DEFINITION
# ==============================================================================

ACTIONS = [
    "REALISTIC_RESPONSE",  # Use existing honeypot logic (LLM, simulations)
    "DECEPTIVE_RESOURCE",  # Return fake sensitive data with honeytokens
    "RESPONSE_DELAY",  # Add artificial delay (0.5-2 seconds)
    "MISLEADING_SUCCESS",  # Fake success for operations that should fail
    "FAKE_VULNERABILITY",  # Expose fake system weaknesses
    "TERMINATE_SESSION",  # Force disconnect the session
]


# ==============================================================================
# ACTION DESCRIPTIONS
# ==============================================================================

ACTION_DESCRIPTIONS = {
    "REALISTIC_RESPONSE": {
        "general": "Use existing honeypot logic - simulations, LLM generation, or real responses",
        "ssh": "Execute command simulations or use LLM for complex commands",
        "http": "Generate realistic HTML/JSON responses using LLM",
        "database": "Return actual table data or use LLM for query responses",
    },
    "DECEPTIVE_RESOURCE": {
        "general": "Return fake sensitive data containing honeytokens for tracking",
        "ssh": "Return fake /etc/passwd, /etc/shadow, SSH keys, .env files with honeytokens",
        "http": "Return fake admin panels, .env files, .git configs, API keys",
        "database": "Return fake admin_users tables, credit cards, API keys with honeytokens",
    },
    "RESPONSE_DELAY": {
        "general": "Add 0.5-2 second delay before responding (simulates busy server)",
        "ssh": "Delay command output as if system is under load",
        "http": "Delay HTTP response as if processing request",
        "database": "Delay query results as if database is busy",
    },
    "MISLEADING_SUCCESS": {
        "general": "Return success messages for operations that should fail",
        "ssh": "Fake successful sudo/su access, pretend files exist",
        "http": "Return 200 OK for unauthorized admin access",
        "database": "Return 'Query OK' for operations that should fail",
    },
    "FAKE_VULNERABILITY": {
        "general": "Expose fake system weaknesses to keep attacker engaged",
        "ssh": "Show world-writable files, excessive sudo permissions, exposed keys",
        "http": "Expose .git directory, directory listings, SQL injection 'success'",
        "database": "Expose mysql.user table, information_schema with sensitive tables",
    },
    "TERMINATE_SESSION": {
        "general": "Immediately disconnect the session (last resort)",
        "ssh": "Close SSH connection with 'Connection closed by remote host'",
        "http": "Return 403 Forbidden and close connection",
        "database": "Return MySQL error 2013 (Lost connection) and disconnect",
    },
}


# ==============================================================================
# ACTION EXAMPLES
# ==============================================================================

ACTION_EXAMPLES = {
    "REALISTIC_RESPONSE": {
        "ssh": "$ ls -la\ndrwxr-xr-x 5 shophub shophub 4096 Jan 15 10:30 .",
        "http": "<!DOCTYPE html><html>... (full homepage) ...</html>",
        "database": '{"columns": ["id", "name"], "rows": [[1, "Product A"]]}',
    },
    "DECEPTIVE_RESOURCE": {
        "ssh": "root:x:0:0:root:/root:/bin/bash\nadmin:$6$HONEYTOKEN_001:...",
        "http": "<h1>Admin Panel</h1><p>DB Password: HONEYTOKEN_PASS_001</p>",
        "database": "admin | $2b$10$HONEYTOKEN_HASH_001 | superuser",
    },
    "RESPONSE_DELAY": {
        "ssh": "[... 1.5 second delay ...]\n$ ls -la\ndrwxr-xr-x ...",
        "http": "[... 1.2 second delay ...]\nHTTP/1.1 200 OK",
        "database": "[... 0.8 second delay ...]\nQuery OK, 1 row affected",
    },
    "MISLEADING_SUCCESS": {
        "ssh": "# [sudo succeeded, now root shell]",
        "http": "HTTP/1.1 200 OK\n<h1>Admin Dashboard Loaded</h1>",
        "database": "Query OK, 1 row affected",
    },
    "FAKE_VULNERABILITY": {
        "ssh": "-rw-rw-rw- 1 root root 1234 /etc/backup_credentials.txt",
        "http": "Index of /backup/\n  database_dump.sql\n  credentials.txt",
        "database": "Table: admin_credentials | api_keys | session_tokens",
    },
    "TERMINATE_SESSION": {
        "ssh": "Connection to shophub-prod-01 closed by remote host.",
        "http": "HTTP/1.1 403 Forbidden\nConnection: close",
        "database": "ERROR 2013 (HY000): Lost connection to MySQL server",
    },
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def get_action_description(action: str, protocol: Optional[str] = None) -> str:
    """
    Get human-readable description of an action.

    Args:
        action: One of the ACTIONS
        protocol: "ssh", "http", "database", or None for general

    Returns:
        Description string

    Example:
        >>> get_action_description("DECEPTIVE_RESOURCE", "ssh")
        'Return fake /etc/passwd, /etc/shadow, SSH keys, .env files with honeytokens'
    """
    if action not in ACTION_DESCRIPTIONS:
        return f"Unknown action: {action}"

    descriptions = ACTION_DESCRIPTIONS[action]

    if protocol and protocol in descriptions:
        return descriptions[protocol]

    return descriptions.get("general", "No description available")


def get_action_example(action: str, protocol: str) -> Optional[str]:
    """
    Get example output for an action.

    Args:
        action: One of the ACTIONS
        protocol: "ssh", "http", or "database"

    Returns:
        Example string or None
    """
    if action not in ACTION_EXAMPLES:
        return None

    examples = ACTION_EXAMPLES[action]
    return examples.get(protocol)


def validate_action(action: str) -> bool:
    """
    Check if action is valid.

    Args:
        action: Action string to validate

    Returns:
        True if valid, False otherwise
    """
    return action in ACTIONS


def get_action_index(action: str) -> int:
    """
    Get numeric index of action (useful for some ML frameworks).

    Args:
        action: Action string

    Returns:
        Index (0-5) or -1 if invalid
    """
    try:
        return ACTIONS.index(action)
    except ValueError:
        return -1


def get_action_by_index(index: int) -> Optional[str]:
    """
    Get action string by numeric index.

    Args:
        index: Action index (0-5)

    Returns:
        Action string or None if invalid
    """
    if 0 <= index < len(ACTIONS):
        return ACTIONS[index]
    return None


# ==============================================================================
# PRINTING UTILITIES
# ==============================================================================


def print_action_space():
    """Print all actions with descriptions"""
    print("\n" + "=" * 70)
    print("RL HONEYPOT ACTION SPACE")
    print("=" * 70)

    for i, action in enumerate(ACTIONS):
        print(f"\n[{i}] {action}")
        print(f"    General: {get_action_description(action)}")
        print(f"    SSH:     {get_action_description(action, 'ssh')}")
        print(f"    HTTP:    {get_action_description(action, 'http')}")
        print(f"    DB:      {get_action_description(action, 'database')}")

    print("\n" + "=" * 70 + "\n")


# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    # Test action space
    print(f"Total actions: {len(ACTIONS)}")
    print(f"Actions: {ACTIONS}\n")

    # Test validation
    print(
        f"validate_action('REALISTIC_RESPONSE'): {validate_action('REALISTIC_RESPONSE')}"
    )
    print(f"validate_action('INVALID_ACTION'): {validate_action('INVALID_ACTION')}\n")

    # Test descriptions
    print("SSH Deceptive Resource:")
    print(get_action_description("DECEPTIVE_RESOURCE", "ssh"))
    print("\nExample:")
    print(get_action_example("DECEPTIVE_RESOURCE", "ssh"))

    # Print full action space
    print_action_space()
