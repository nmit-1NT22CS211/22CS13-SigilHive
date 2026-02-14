"""
Adaptive File Structure Evolver for SigilHive
Allows RL agents to dynamically modify file_structure.py based on attacker behavior.

Evolution strategies:
  - DEEPEN:       Add nested tables/columns to increase attacker exploration time
  - HONEYTOKENS:  Insert fake high-value credentials/keys to trigger exfil alerts
  - CAMOUFLAGE:   Rename/reorganize structures to confuse attackers who cached schema
  - DECOY_TABLES: Add enticing but tracked decoy tables
  - SANITIZE:     Remove structures an attacker has already enumerated
  - REINFORCE:    Add more realistic data to tables the attacker skipped

Each evolution action is scored by the RL reward signal and logged for analysis.
"""

import ast
import copy
import hashlib
import json
import logging
import os
import random
import re
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EvolutionStrategy(str, Enum):
    DEEPEN = "deepen"              # Add nested complexity
    HONEYTOKENS = "honeytokens"    # Plant fake credentials
    CAMOUFLAGE = "camouflage"      # Rename/shuffle known structures
    DECOY_TABLES = "decoy_tables"  # Add tracked lure tables
    SANITIZE = "sanitize"          # Remove enumerated structures
    REINFORCE = "reinforce"        # Add realism to untouched areas
    EXPAND_SCHEMA = "expand_schema"  # Add entirely new realistic schemas


@dataclass
class EvolutionRecord:
    """Tracks a single evolution event."""
    strategy: EvolutionStrategy
    timestamp: float
    reward_before: float
    reward_after: float
    changes_made: list[str]
    attacker_patterns: dict[str, Any]
    checksum_before: str
    checksum_after: str

    @property
    def reward_delta(self) -> float:
        return self.reward_after - self.reward_before

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "timestamp": self.timestamp,
            "reward_delta": round(self.reward_delta, 3),
            "changes": self.changes_made,
            "checksum_before": self.checksum_before[:8],
            "checksum_after": self.checksum_after[:8],
        }


class FileStructureEvolver:
    """
    Adaptive system enabling RL agents to evolve the honeypot's file_structure.py.

    The evolver:
    1. Monitors attacker behavior (which tables/paths they probe)
    2. Selects the best evolution strategy via RL Q-values
    3. Modifies file_structure.py in-place (with backup)
    4. Reports reward delta back to RL agents
    5. Syncs changes across Docker containers via shared volume

    Integration with Docker:
    - file_structure.py is mounted as a shared volume into all honeypot containers
    - Changes take effect on the next honeypot request (no restart needed)
    """

    # Evolution reward weights
    STRATEGY_BASE_REWARDS = {
        EvolutionStrategy.DEEPEN: 5.0,
        EvolutionStrategy.HONEYTOKENS: 12.0,    # High value: triggers alerts
        EvolutionStrategy.CAMOUFLAGE: 7.0,
        EvolutionStrategy.DECOY_TABLES: 10.0,
        EvolutionStrategy.SANITIZE: 6.0,
        EvolutionStrategy.REINFORCE: 4.0,
        EvolutionStrategy.EXPAND_SCHEMA: 8.0,
    }

    # Max evolutions per session to prevent runaway mutation
    MAX_EVOLUTIONS_PER_SESSION = 50

    def __init__(
        self,
        file_structure_path: str = "file_structure.py",
        backup_dir: str = ".fs_backups",
        evolution_log_path: str = "evolution_log.json",
        auto_backup: bool = True,
    ):
        self.file_path = Path(file_structure_path)
        self.backup_dir = Path(backup_dir)
        self.evolution_log_path = Path(evolution_log_path)
        self.auto_backup = auto_backup

        self.evolution_history: list[EvolutionRecord] = []
        self.evolution_count = 0
        self._structure_cache: Optional[dict] = None

        # Strategy Q-values (updated by RL feedback)
        self.strategy_q_values: dict[str, float] = {
            s.value: self.STRATEGY_BASE_REWARDS[s]
            for s in EvolutionStrategy
        }

        # Attacker intelligence: what has been probed
        self.probed_tables: set[str] = set()
        self.probed_columns: dict[str, set[str]] = {}
        self.exfil_targets: set[str] = set()

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"FileStructureEvolver initialized | target={self.file_path} | "
            f"auto_backup={auto_backup}"
        )

    # ------------------------------------------------------------------ #
    #  Structure I/O                                                       #
    # ------------------------------------------------------------------ #

    def _load_structure(self) -> dict:
        """Load and execute file_structure.py to get the data structures."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"file_structure.py not found at {self.file_path}")

        namespace: dict = {}
        with open(self.file_path, "r") as f:
            source = f.read()
        exec(compile(source, str(self.file_path), "exec"), namespace)

        return {
            "DATABASES": namespace.get("DATABASES", {}),
            "SSH_FILESYSTEM": namespace.get("SSH_FILESYSTEM", {}),
            "HTTP_ROUTES": namespace.get("HTTP_ROUTES", {}),
            "PRODUCTS": namespace.get("PRODUCTS", {}),
        }

    def _save_structure(self, structure: dict) -> str:
        """Write modified structure back to file_structure.py. Returns new checksum."""
        content_parts = []

        if "DATABASES" in structure and structure["DATABASES"]:
            content_parts.append(f"DATABASES = {repr(structure['DATABASES'])}\n")

        if "SSH_FILESYSTEM" in structure and structure["SSH_FILESYSTEM"]:
            content_parts.append(f"\nSSH_FILESYSTEM = {repr(structure['SSH_FILESYSTEM'])}\n")

        if "HTTP_ROUTES" in structure and structure["HTTP_ROUTES"]:
            content_parts.append(f"\nHTTP_ROUTES = {repr(structure['HTTP_ROUTES'])}\n")

        if "PRODUCTS" in structure and structure["PRODUCTS"]:
            content_parts.append(f"\nPRODUCTS = {repr(structure['PRODUCTS'])}\n")

        new_content = "".join(content_parts)

        with open(self.file_path, "w") as f:
            f.write(new_content)

        self._structure_cache = None  # Invalidate cache
        checksum = hashlib.sha256(new_content.encode()).hexdigest()
        logger.info(f"Structure saved | checksum={checksum[:8]}")
        return checksum

    def _checksum(self) -> str:
        if not self.file_path.exists():
            return "00000000"
        content = self.file_path.read_text()
        return hashlib.sha256(content.encode()).hexdigest()

    def _backup(self) -> Path:
        """Create a timestamped backup of the current file_structure.py."""
        ts = int(time.time())
        backup_path = self.backup_dir / f"file_structure_{ts}.py.bak"
        shutil.copy2(self.file_path, backup_path)
        logger.debug(f"Backup created: {backup_path}")
        return backup_path

    def restore_backup(self, backup_path: Optional[str] = None) -> None:
        """Restore from the latest (or specified) backup."""
        if backup_path:
            target = Path(backup_path)
        else:
            backups = sorted(self.backup_dir.glob("file_structure_*.py.bak"))
            if not backups:
                raise FileNotFoundError("No backups available")
            target = backups[-1]

        shutil.copy2(target, self.file_path)
        self._structure_cache = None
        logger.info(f"Restored from backup: {target}")

    # ------------------------------------------------------------------ #
    #  RL Integration                                                      #
    # ------------------------------------------------------------------ #

    def update_attacker_intelligence(
        self,
        attack_results: list,
        probed_tables: Optional[list[str]] = None,
        exfil_targets: Optional[list[str]] = None,
    ) -> None:
        """
        Feed attacker behavior data to the evolver.
        Called by TrainingIntegration after each attack batch.
        """
        if probed_tables:
            self.probed_tables.update(probed_tables)
        if exfil_targets:
            self.exfil_targets.update(exfil_targets)

        # Extract tables from attack commands
        for result in attack_results:
            for cmd in getattr(result, "commands_executed", []):
                # Parse SQL table references
                tables = re.findall(r"FROM\s+(\w+\.?\w+)", cmd, re.IGNORECASE)
                self.probed_tables.update(tables)
                tables2 = re.findall(r"INTO\s+(\w+\.?\w+)", cmd, re.IGNORECASE)
                self.probed_tables.update(tables2)

        logger.debug(f"Attacker intelligence updated | probed_tables={len(self.probed_tables)}")

    def update_q_value(self, strategy: EvolutionStrategy, reward_delta: float) -> None:
        """
        Update the Q-value for a strategy based on RL feedback.
        Uses a simple learning rate update: Q(s) = Q(s) + α * (r - Q(s))
        """
        alpha = 0.1  # Learning rate
        key = strategy.value
        old_q = self.strategy_q_values[key]
        self.strategy_q_values[key] = old_q + alpha * (reward_delta - old_q)
        logger.debug(f"Q-value updated | strategy={key} | {old_q:.2f} → {self.strategy_q_values[key]:.2f}")

    def select_strategy(self, epsilon: float = 0.15) -> EvolutionStrategy:
        """
        ε-greedy strategy selection.
        With probability ε, explore randomly; otherwise exploit best Q-value.
        """
        if random.random() < epsilon:
            return random.choice(list(EvolutionStrategy))

        best = max(self.strategy_q_values, key=self.strategy_q_values.get)
        return EvolutionStrategy(best)

    # ------------------------------------------------------------------ #
    #  Evolution strategies                                                #
    # ------------------------------------------------------------------ #

    def _evolve_deepen(self, structure: dict) -> tuple[dict, list[str]]:
        """Add nested complexity: new columns, foreign key hints, indexes."""
        changes = []
        db = structure.get("DATABASES", {})

        for db_name, db_data in db.items():
            if db_name == "information_schema":
                continue
            for tbl_name, tbl in db_data.get("tables", {}).items():
                if "columns" in tbl and len(tbl["columns"]) < 12:
                    new_cols = random.sample([
                        "metadata_json", "external_ref_id", "audit_hash",
                        "created_by_ip", "last_modified_by", "version_tag",
                        "soft_delete_at", "tenant_id", "encryption_key_id",
                    ], k=random.randint(1, 2))
                    for col in new_cols:
                        if col not in tbl["columns"]:
                            tbl["columns"].append(col)
                            changes.append(f"Added column '{col}' to {db_name}.{tbl_name}")

        return structure, changes

    def _evolve_honeytokens(self, structure: dict) -> tuple[dict, list[str]]:
        """Plant fake high-value credentials and API keys as honeytokens."""
        changes = []
        db = structure.get("DATABASES", {})

        # Add a fake secrets table
        if "shophub" in db:
            fake_secrets_table = {
                "columns": ["id", "key_name", "key_value", "environment", "rotated_at"],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["key_name", "varchar(100)", "NO", "UNI", None, ""],
                    ["key_value", "text", "NO", "", None, ""],
                    ["environment", "varchar(20)", "NO", "", "production", ""],
                    ["rotated_at", "timestamp", "YES", "", None, ""],
                ],
                "rows": [
                    [1, "stripe_secret_key", "sk_live_HONEYTOKEN_DO_NOT_USE_xK92m", "production", "2024-11-01"],
                    [2, "aws_access_key", "AKIAHONEYTOKEN123FAKE", "production", "2024-10-15"],
                    [3, "jwt_signing_secret", "hs256_honeytoken_7f4e2a9c1b8d3f6e", "production", "2024-12-01"],
                    [4, "sendgrid_api_key", "SG.HONEYTOKEN.FAKE.KEY.12345", "production", "2024-09-20"],
                ],
                "_honeytoken": True,  # Internal flag for alerting
            }
            db["shophub"]["tables"]["app_secrets"] = fake_secrets_table
            changes.append("Planted honeytoken table: shophub.app_secrets")

        # Add a fake admin account
        if "mysql" in db and "user" in db["mysql"].get("tables", {}):
            db["mysql"]["tables"]["user"]["rows"].append(
                ["%", "deploy_admin", "*HONEYTOKEN_HASH_7f4e2a9c"]
            )
            changes.append("Planted honeytoken MySQL user: deploy_admin@%")

        return structure, changes

    def _evolve_camouflage(self, structure: dict) -> tuple[dict, list[str]]:
        """Rename or shuffle structures that the attacker has already probed."""
        changes = []
        db = structure.get("DATABASES", {})

        if "shophub" not in db:
            return structure, changes

        tables = db["shophub"].get("tables", {})
        probed = [t for t in self.probed_tables if t.split(".")[-1] in tables]

        if not probed:
            # Nothing probed yet; shuffle column order as a pre-emptive move
            for tbl_name, tbl in tables.items():
                if "columns" in tbl and len(tbl["columns"]) > 3:
                    random.shuffle(tbl["columns"])
                    changes.append(f"Shuffled column order in shophub.{tbl_name}")
            return structure, changes

        # Rename a probed table to a new name with suffix
        target = random.choice(probed).split(".")[-1]
        suffixes = ["_v2", "_archive", "_legacy", "_bak", "_2024"]
        new_name = target + random.choice(suffixes)
        tables[new_name] = tables.pop(target)
        changes.append(f"Renamed probed table '{target}' → '{new_name}'")

        # Update information_schema.tables to reflect rename
        info_tables = (
            db.get("information_schema", {})
            .get("tables", {})
            .get("tables", {})
        )
        if info_tables and "rows" in info_tables:
            for row in info_tables["rows"]:
                if row[1] == target:
                    row[1] = new_name
                    break

        return structure, changes

    def _evolve_decoy_tables(self, structure: dict) -> tuple[dict, list[str]]:
        """Add enticing but instrumented decoy tables."""
        changes = []
        db = structure.get("DATABASES", {})

        if "shophub" not in db:
            return structure, changes

        decoy_tables = {
            "internal_audit_log": {
                "columns": ["id", "admin_id", "action", "target_table", "old_value", "new_value", "timestamp"],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["admin_id", "int", "NO", "MUL", None, ""],
                    ["action", "varchar(50)", "NO", "", None, ""],
                    ["target_table", "varchar(100)", "NO", "", None, ""],
                    ["old_value", "json", "YES", "", None, ""],
                    ["new_value", "json", "YES", "", None, ""],
                    ["timestamp", "timestamp", "NO", "", "CURRENT_TIMESTAMP", "DEFAULT_GENERATED"],
                ],
                "rows": [],
                "_decoy": True,
            },
            "payment_processor_keys": {
                "columns": ["id", "processor", "api_key_enc", "webhook_secret", "active"],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["processor", "varchar(50)", "NO", "", None, ""],
                    ["api_key_enc", "text", "NO", "", None, ""],
                    ["webhook_secret", "varchar(255)", "NO", "", None, ""],
                    ["active", "tinyint(1)", "NO", "", "1", ""],
                ],
                "rows": [],
                "_decoy": True,
            },
        }

        for tbl_name, tbl_def in decoy_tables.items():
            if tbl_name not in db["shophub"]["tables"]:
                db["shophub"]["tables"][tbl_name] = tbl_def
                changes.append(f"Added decoy table: shophub.{tbl_name}")

                # Register in information_schema
                info_tables = (
                    db.get("information_schema", {})
                    .get("tables", {})
                    .get("tables", {})
                )
                if info_tables and "rows" in info_tables:
                    info_tables["rows"].append(["shophub", tbl_name, "BASE TABLE"])

        return structure, changes

    def _evolve_sanitize(self, structure: dict) -> tuple[dict, list[str]]:
        """Remove tables/data that the attacker has successfully enumerated."""
        changes = []
        db = structure.get("DATABASES", {})

        if "shophub" not in db:
            return structure, changes

        tables = db["shophub"].get("tables", {})
        # Remove rows from heavily probed tables (keep schema, empty data)
        for probed in self.probed_tables:
            tbl_short = probed.split(".")[-1]
            if tbl_short in tables and "rows" in tables[tbl_short]:
                old_row_count = len(tables[tbl_short]["rows"])
                tables[tbl_short]["rows"] = []
                if old_row_count:
                    changes.append(
                        f"Sanitized {old_row_count} rows from shophub.{tbl_short}"
                    )

        return structure, changes

    def _evolve_reinforce(self, structure: dict) -> tuple[dict, list[str]]:
        """Add realistic decoy data to tables the attacker hasn't touched yet."""
        changes = []
        db = structure.get("DATABASES", {})

        if "shophub" not in db:
            return structure, changes

        tables = db["shophub"].get("tables", {})
        unprobed = [
            t for t in tables
            if t not in {p.split(".")[-1] for p in self.probed_tables}
            and t not in {"app_secrets", "payment_processor_keys", "internal_audit_log"}
        ]

        for tbl_name in random.sample(unprobed, min(2, len(unprobed))):
            tbl = tables[tbl_name]
            # Add dummy rows to make table look active
            if "columns" in tbl:
                dummy_rows = self._generate_dummy_rows(tbl["columns"], count=5)
                existing = tbl.get("rows", [])
                tbl["rows"] = existing + dummy_rows
                changes.append(
                    f"Reinforced shophub.{tbl_name} with {len(dummy_rows)} synthetic rows"
                )

        return structure, changes

    def _evolve_expand_schema(self, structure: dict) -> tuple[dict, list[str]]:
        """Add an entirely new realistic database schema to expand the attack surface."""
        changes = []
        db = structure.get("DATABASES", {})

        new_schemas = {
            "shophub_analytics": {
                "tables": {
                    "page_views": {
                        "columns": ["id", "session_id", "user_id", "page_path", "referrer",
                                    "user_agent", "duration_ms", "timestamp"],
                        "rows": [],
                    },
                    "conversion_funnel": {
                        "columns": ["id", "session_id", "step", "product_id", "value", "timestamp"],
                        "rows": [],
                    },
                }
            },
            "shophub_internal": {
                "tables": {
                    "staff_users": {
                        "columns": ["id", "username", "role", "last_login", "mfa_enabled"],
                        "rows": [
                            [1, "ops_manager", "superadmin", "2025-01-10 09:00:00", 0],
                            [2, "dev_lead", "developer", "2025-01-12 14:30:00", 1],
                        ],
                    },
                    "deployment_tokens": {
                        "columns": ["id", "token_hash", "service", "expires_at", "created_by"],
                        "rows": [],
                    },
                }
            },
        }

        for schema_name, schema_data in new_schemas.items():
            if schema_name not in db:
                db[schema_name] = schema_data
                changes.append(f"Added new database schema: {schema_name}")

                # Register in information_schema
                schemata = (
                    db.get("information_schema", {})
                    .get("tables", {})
                    .get("schemata", {})
                )
                if schemata and "rows" in schemata:
                    schemata["rows"].append([schema_name, "utf8mb4"])

        return structure, changes

    # ------------------------------------------------------------------ #
    #  Synthetic data generation                                           #
    # ------------------------------------------------------------------ #

    def _generate_dummy_rows(self, columns: list[str], count: int = 5) -> list[list]:
        """Generate plausible fake rows for a given column schema."""
        rows = []
        for i in range(count):
            row = []
            for col in columns:
                col_lower = col.lower()
                if col_lower == "id":
                    row.append(random.randint(1000, 9999))
                elif "email" in col_lower:
                    row.append(f"user{random.randint(100,999)}@shophub.example")
                elif "password" in col_lower or "hash" in col_lower:
                    row.append(f"$2b$12${''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=22))}")
                elif "name" in col_lower:
                    names = ["Alice", "Bob", "Charlie", "Diana", "Evan", "Fiona"]
                    row.append(random.choice(names))
                elif "amount" in col_lower or "price" in col_lower or "total" in col_lower:
                    row.append(round(random.uniform(10.0, 500.0), 2))
                elif "status" in col_lower:
                    row.append(random.choice(["active", "pending", "completed", "cancelled"]))
                elif "timestamp" in col_lower or "_at" in col_lower:
                    row.append(f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d} "
                               f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:00")
                elif "id" in col_lower:
                    row.append(random.randint(1, 100))
                else:
                    row.append(f"value_{random.randint(1000, 9999)}")
            rows.append(row)
        return rows

    # ------------------------------------------------------------------ #
    #  Main evolution entry point                                          #
    # ------------------------------------------------------------------ #

    def evolve(
        self,
        strategy: Optional[EvolutionStrategy] = None,
        reward_before: float = 0.0,
        epsilon: float = 0.15,
    ) -> Optional[EvolutionRecord]:
        """
        Execute one evolution step on file_structure.py.

        Args:
            strategy:      Force a specific strategy (None = ε-greedy selection)
            reward_before: Current RL reward before evolution
            epsilon:       Exploration rate for strategy selection

        Returns:
            EvolutionRecord with details of changes made
        """
        if self.evolution_count >= self.MAX_EVOLUTIONS_PER_SESSION:
            logger.warning("Max evolutions per session reached; skipping")
            return None

        if not self.file_path.exists():
            logger.error(f"file_structure.py not found at {self.file_path}")
            return None

        checksum_before = self._checksum()

        if self.auto_backup:
            self._backup()

        # Select strategy
        chosen_strategy = strategy or self.select_strategy(epsilon=epsilon)
        logger.info(f"Evolving structure | strategy={chosen_strategy.value}")

        # Load current structure
        try:
            structure = self._load_structure()
        except Exception as exc:
            logger.error(f"Failed to load structure: {exc}")
            return None

        # Apply strategy
        strategy_map = {
            EvolutionStrategy.DEEPEN: self._evolve_deepen,
            EvolutionStrategy.HONEYTOKENS: self._evolve_honeytokens,
            EvolutionStrategy.CAMOUFLAGE: self._evolve_camouflage,
            EvolutionStrategy.DECOY_TABLES: self._evolve_decoy_tables,
            EvolutionStrategy.SANITIZE: self._evolve_sanitize,
            EvolutionStrategy.REINFORCE: self._evolve_reinforce,
            EvolutionStrategy.EXPAND_SCHEMA: self._evolve_expand_schema,
        }

        evolve_fn = strategy_map[chosen_strategy]
        try:
            new_structure, changes = evolve_fn(structure)
        except Exception as exc:
            logger.error(f"Evolution strategy failed: {exc}", exc_info=True)
            return None

        if not changes:
            logger.info("No changes made by evolution strategy")
            return None

        # Save modified structure
        try:
            checksum_after = self._save_structure(new_structure)
        except Exception as exc:
            logger.error(f"Failed to save evolved structure: {exc}")
            self.restore_backup()
            return None

        self.evolution_count += 1

        # Estimate reward_after (heuristic: more changes = higher reward)
        reward_after = reward_before + self.STRATEGY_BASE_REWARDS[chosen_strategy] * len(changes)

        record = EvolutionRecord(
            strategy=chosen_strategy,
            timestamp=time.time(),
            reward_before=reward_before,
            reward_after=reward_after,
            changes_made=changes,
            attacker_patterns={
                "probed_tables": list(self.probed_tables),
                "exfil_targets": list(self.exfil_targets),
            },
            checksum_before=checksum_before,
            checksum_after=checksum_after,
        )

        self.evolution_history.append(record)
        self._append_to_log(record)

        # Update Q-value for chosen strategy
        self.update_q_value(chosen_strategy, record.reward_delta)

        logger.info(
            f"Evolution complete | strategy={chosen_strategy.value} | "
            f"changes={len(changes)} | reward_delta={record.reward_delta:+.2f}"
        )
        for change in changes:
            logger.debug(f"  ↳ {change}")

        return record

    def evolve_from_rl_signal(
        self,
        q_values: dict[str, float],
        attack_results: list,
        current_reward: float,
    ) -> Optional[EvolutionRecord]:
        """
        Trigger evolution directly from RL agent Q-values.

        Called by TrainingIntegration when the RL agent decides an evolution
        is beneficial based on recent attack patterns.

        Args:
            q_values:       Q-values from the RL agent (strategy → value)
            attack_results: Recent attack results from adversarial agent
            current_reward: Current cumulative RL reward
        """
        # Merge RL Q-values into our strategy Q-values
        for strategy_name, q_val in q_values.items():
            if strategy_name in self.strategy_q_values:
                # Blend: 60% RL signal, 40% internal estimate
                self.strategy_q_values[strategy_name] = (
                    0.6 * q_val + 0.4 * self.strategy_q_values[strategy_name]
                )

        # Update attacker intelligence from recent results
        self.update_attacker_intelligence(attack_results)

        # Select and execute best strategy (greedy, no exploration)
        return self.evolve(strategy=None, reward_before=current_reward, epsilon=0.05)

    # ------------------------------------------------------------------ #
    #  Logging and reporting                                               #
    # ------------------------------------------------------------------ #

    def _append_to_log(self, record: EvolutionRecord) -> None:
        log_entries = []
        if self.evolution_log_path.exists():
            try:
                with open(self.evolution_log_path) as f:
                    log_entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        log_entries.append(record.to_dict())

        with open(self.evolution_log_path, "w") as f:
            json.dump(log_entries, f, indent=2)

    def get_evolution_summary(self) -> dict:
        if not self.evolution_history:
            return {"total_evolutions": 0}

        strategy_counts: dict[str, int] = {}
        total_reward_delta = 0.0
        for rec in self.evolution_history:
            key = rec.strategy.value
            strategy_counts[key] = strategy_counts.get(key, 0) + 1
            total_reward_delta += rec.reward_delta

        return {
            "total_evolutions": self.evolution_count,
            "strategy_breakdown": strategy_counts,
            "total_reward_delta": round(total_reward_delta, 2),
            "probed_tables_count": len(self.probed_tables),
            "exfil_targets_count": len(self.exfil_targets),
            "current_q_values": {
                k: round(v, 2) for k, v in self.strategy_q_values.items()
            },
            "backups_available": len(list(self.backup_dir.glob("*.py.bak"))),
        }

    def print_summary(self) -> None:
        summary = self.get_evolution_summary()
        print("\n" + "=" * 55)
        print("  FILE STRUCTURE EVOLVER SUMMARY")
        print("=" * 55)
        for k, v in summary.items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for sk, sv in v.items():
                    print(f"    {sk:<30} {sv}")
            else:
                print(f"  {k:<35} {v}")
        print("=" * 55 + "\n")