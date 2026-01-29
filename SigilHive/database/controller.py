import os
import re
import json
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from llm_gen import generate_db_response_async
from kafka_manager import HoneypotKafkaManager
from file_structure import DATABASES
from rl_core.q_learning_agent import shared_rl_agent
from rl_core.state_extractor import extract_state
from rl_core.reward_calculator import calculate_reward
from rl_core.logging.structured_logger import log_interaction


class ShopHubDatabase:
    """Maintains ShopHub e-commerce database state"""

    def __init__(self):
        self.databases = DATABASES
        # IMPORTANT: no default DB selected on startup (matches MySQL semantics)
        self.current_db: Optional[str] = None

    def create_database(self, db_name: str) -> bool:
        if db_name.lower() not in self.databases:
            self.databases[db_name.lower()] = {"tables": {}}
            return True
        return False

    def drop_database(self, db_name: str) -> bool:
        if db_name.lower() in self.databases and db_name.lower() not in [
            "information_schema",
            "mysql",
            "shophub",
            "shophub_logs",
        ]:
            del self.databases[db_name.lower()]
            return True
        return False

    def use_database(self, db_name: str) -> bool:
        if db_name.lower() in self.databases:
            self.current_db = db_name.lower()
            return True
        return False

    def create_table(self, table_name: str, columns: List[str]) -> bool:
        if (
            self.current_db
            and table_name.lower() not in self.databases[self.current_db]["tables"]
        ):
            self.databases[self.current_db]["tables"][table_name.lower()] = {
                "columns": columns,
                "rows": [],
            }
            return True
        return False

    def drop_table(self, table_name: str) -> bool:
        if (
            self.current_db
            and table_name.lower() in self.databases[self.current_db]["tables"]
        ):
            del self.databases[self.current_db]["tables"][table_name.lower()]
            return True
        return False

    def insert_into_table(self, table_name: str, values: List[Any]) -> bool:
        if (
            self.current_db
            and table_name.lower() in self.databases[self.current_db]["tables"]
        ):
            self.databases[self.current_db]["tables"][table_name.lower()][
                "rows"
            ].append(values)
            return True
        return False

    def get_table_data(self, table_name: str, db_name: str = None) -> Optional[Dict]:
        db = db_name.lower() if db_name else self.current_db
        if (
            db
            and db in self.databases
            and table_name.lower() in self.databases[db]["tables"]
        ):
            return self.databases[db]["tables"][table_name.lower()]
        return None

    def list_databases(self) -> List[str]:
        return sorted(self.databases.keys())

    def list_tables(self, db_name: str = None) -> List[str]:
        db = db_name.lower() if db_name else self.current_db
        if db and db in self.databases:
            return list(self.databases[db]["tables"].keys())
        return []

    def get_state_summary(self) -> str:
        summary = "ShopHub E-commerce Database System\n"
        summary += f"Current Database: {self.current_db}\n"
        summary += f"Available Databases: {', '.join(self.list_databases())}\n\n"

        if self.current_db:
            tables = self.list_tables()
            summary += f"Tables in '{self.current_db}': {len(tables)} tables\n"
            for table in tables[:10]:
                table_info = self.get_table_data(table)
                if table_info:
                    row_count = len(table_info.get("rows", []))
                    col_count = len(table_info.get("columns", []))
                    summary += f"  - {table}: {row_count} rows, {col_count} columns\n"
                    cols = table_info.get("columns", [])
                    summary += f"    Columns: {', '.join(cols)}\n"

        return summary


def extract_json_from_text(text: str) -> Optional[Dict]:
    """
    Aggressively extract JSON from LLM response text.
    Tries multiple strategies to find valid JSON.
    """
    if not isinstance(text, str):
        return None

    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strategy 2: Remove markdown code blocks
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Strategy 3: Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass

    # Strategy 4: Balanced brace extraction
    if "{" in text:
        start = text.find("{")
        counter = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                counter += 1
            elif text[i] == "}":
                counter -= 1
                if counter == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except Exception:
                        break

    return None


class ShopHubDBController:
    """Intelligent controller for ShopHub MySQL honeypot"""

    NO_DB_ERROR = "ERROR 1046 (3D000): No database selected"

    def __init__(self):
        self.db_state = ShopHubDatabase()
        self.sessions = {}
        self.kafka_manager = HoneypotKafkaManager()

        self.rl_agent = shared_rl_agent
        self.rl_enabled = os.getenv("RL_ENABLED", "true").lower() == "true"
        print(f"[DBController] RL enabled: {self.rl_enabled}")

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "query_history": [],
                "suspicious_count": 0,
                "failed_auth_attempts": 0,
                "username": None,
            }
        return self.sessions[session_id]

    def _classify_query(self, query: str) -> str:
        q_upper = query.upper().strip()

        if re.match(r"^\s*(DESCRIBE|DESC)\b", q_upper):
            return "describe"
        elif re.match(r"^\s*(SELECT|SHOW|EXPLAIN)\b", q_upper):
            return "read"
        elif re.match(r"^\s*(INSERT|UPDATE|DELETE)\b", q_upper):
            return "write"
        elif "CREATE DATABASE" in q_upper or "CREATE SCHEMA" in q_upper:
            return "create_db"
        elif "DROP DATABASE" in q_upper or "DROP SCHEMA" in q_upper:
            return "drop_db"
        elif "CREATE TABLE" in q_upper:
            return "create_table"
        elif "DROP TABLE" in q_upper:
            return "drop_table"
        elif "ALTER" in q_upper:
            return "alter"
        elif re.match(r"^\s*(GRANT|REVOKE)\b", q_upper):
            return "admin"
        elif "USE" in q_upper:
            return "use_db"
        else:
            return "other"

    def _is_suspicious(self, query: str) -> bool:
        q_upper = query.upper()
        suspicious_patterns = [
            "UNION SELECT",
            "OR 1=1",
            "AND 1=1",
            "' OR '",
            "'; DROP",
            "--",
            "LOAD_FILE",
            "INTO OUTFILE",
            "INTO DUMPFILE",
            "BENCHMARK(",
            "SLEEP(",
            "WAITFOR DELAY",
            "../",
            "password_hash",
            "authentication_string",
            "admin_users",
        ]
        return any(pattern in q_upper for pattern in suspicious_patterns)

    def _parse_create_database(self, query: str) -> Optional[str]:
        match = re.search(
            r'CREATE\s+(?:DATABASE|SCHEMA)\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?',
            query,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _parse_drop_database(self, query: str) -> Optional[str]:
        match = re.search(
            r'DROP\s+(?:DATABASE|SCHEMA)\s+(?:IF\s+EXISTS\s+)?[`"]?(\w+)[`"]?',
            query,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _parse_use_database(self, query: str) -> Optional[str]:
        match = re.search(r'USE\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        return match.group(1) if match else None

    def _parse_create_table(self, query: str) -> Optional[Tuple]:
        match = re.search(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?\s*\((.*?)\)',
            query,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table_name = match.group(1)
            columns_str = match.group(2)
            columns = []
            for col_def in columns_str.split(","):
                col_name = col_def.strip().split()[0].strip('`"')
                if col_name.upper() not in [
                    "PRIMARY",
                    "KEY",
                    "FOREIGN",
                    "CONSTRAINT",
                    "INDEX",
                ]:
                    columns.append(col_name)
            return (table_name, columns)
        return None

    def _parse_drop_table(self, query: str) -> Optional[str]:
        match = re.search(
            r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?[`"]?(\w+)[`"]?', query, re.IGNORECASE
        )
        return match.group(1) if match else None

    def _parse_insert(self, query: str) -> Optional[Tuple]:
        match = re.search(
            r'INSERT\s+INTO\s+[`"]?(\w+)[`"]?.*?VALUES\s*\((.*?)\)',
            query,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table_name = match.group(1)
            values_str = match.group(2)
            values = [v.strip().strip("'\"") for v in values_str.split(",")]
            return (table_name, values)
        return None

    def _parse_select(self, query: str) -> Optional[str]:
        match = re.search(r'FROM\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        return match.group(1) if match else None

    def _parse_describe(self, query: str) -> Optional[str]:
        match = re.search(r'(?:DESCRIBE|DESC)\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        return match.group(1) if match else None

    def _execute_state_change(self, query: str, intent: str) -> Tuple[bool, str]:
        if intent == "create_db":
            db_name = self._parse_create_database(query)
            if db_name:
                success = self.db_state.create_database(db_name)
                return (
                    (True, "Query OK, 1 row affected")
                    if success
                    else (
                        False,
                        f"ERROR 1007 (HY000): Can't create database '{db_name}'; database exists",
                    )
                )

        elif intent == "drop_db":
            db_name = self._parse_drop_database(query)
            if db_name:
                success = self.db_state.drop_database(db_name)
                return (
                    (True, "Query OK, 0 rows affected")
                    if success
                    else (
                        False,
                        f"ERROR 1008 (HY000): Can't drop database '{db_name}'; database doesn't exist",
                    )
                )

        elif intent == "use_db":
            db_name = self._parse_use_database(query)
            if db_name:
                success = self.db_state.use_database(db_name)
                return (
                    (True, "Database changed")
                    if success
                    else (False, f"ERROR 1049 (42000): Unknown database '{db_name}'")
                )

        elif intent == "create_table":
            table_info = self._parse_create_table(query)
            if table_info:
                table_name, columns = table_info
                success = self.db_state.create_table(table_name, columns)
                return (
                    (True, "Query OK, 0 rows affected")
                    if success
                    else (
                        False,
                        f"ERROR 1050 (42S01): Table '{table_name}' already exists",
                    )
                )

        elif intent == "drop_table":
            table_name = self._parse_drop_table(query)
            if table_name:
                success = self.db_state.drop_table(table_name)
                return (
                    (True, "Query OK, 0 rows affected")
                    if success
                    else (False, f"ERROR 1051 (42S02): Unknown table '{table_name}'")
                )

        elif intent == "write":
            insert_info = self._parse_insert(query)
            if insert_info:
                table_name, values = insert_info
                success = self.db_state.insert_into_table(table_name, values)
                return (
                    (True, "Query OK, 1 row affected")
                    if success
                    else (
                        False,
                        f"ERROR 1146 (42S02): Table '{table_name}' doesn't exist",
                    )
                )

        return False, "Query OK"

    async def _finalize_query(
        self,
        session_id: str,
        query: str,
        intent: str,
        response: Any,
        delay: float,
    ):
        """Finalization wrapper: send Kafka events and return DB response."""
        try:
            payload = {
                "session_id": session_id,
                "query": query,
                "intent": intent,
                "response": response,
                "delay": delay,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.kafka_manager.send(topic="DBtoHTTP", value=payload)
            self.kafka_manager.send(topic="DBtoSSH", value=payload)
            self.kafka_manager.send_dashboard(
                topic="honeypot-logs",
                value=payload,
                service="database",
                event_type=intent,
            )

        except Exception as e:
            print(f"[DBController] Kafka send error: {e}")

        return {"response": response, "delay": delay}

    async def _original_query_handler(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        query = event.get("query", "")
        intent = self._classify_query(query)

        # ------------------------
        # STATE-CHANGING QUERIES
        # ------------------------
        if intent in [
            "create_db",
            "drop_db",
            "use_db",
            "create_table",
            "drop_table",
            "write",
        ]:
            success, message = self._execute_state_change(query, intent)
            return await self._finalize_query(
                session_id,
                query,
                intent,
                message,
                0.05,
            )

        # ------------------------
        # DESCRIBE TABLE
        # ------------------------
        if intent == "describe":
            table_name = self._parse_describe(query)
            if table_name:
                if not self.db_state.current_db:
                    return await self._finalize_query(
                        session_id, query, intent, self.NO_DB_ERROR, 0.0
                    )

                table_info = self.db_state.get_table_data(table_name)

                if table_info and "column_defs" in table_info:
                    response = {
                        "columns": ["Field", "Type", "Null", "Key", "Default", "Extra"],
                        "rows": table_info["column_defs"],
                    }
                    return await self._finalize_query(
                        session_id, query, intent, response, 0.0
                    )

                # Unknown table
                db = self.db_state.current_db or "shophub"
                err = f"ERROR 1146 (42S02): Table '{db}.{table_name}' doesn't exist"
                return await self._finalize_query(session_id, query, intent, err, 0.0)

        # ------------------------
        # READ QUERIES
        # ------------------------
        if intent == "read":
            q_upper = query.upper()

            # SHOW DATABASES
            if "SHOW DATABASES" in q_upper or "SHOW SCHEMAS" in q_upper:
                response = {
                    "columns": ["Database"],
                    "rows": [[db] for db in self.db_state.list_databases()],
                }
                return await self._finalize_query(
                    session_id, query, intent, response, 0.0
                )

            # SELECT DATABASE()
            if "DATABASE()" in q_upper or "SCHEMA()" in q_upper:
                current = self.db_state.current_db
                response = {
                    "columns": ["DATABASE()"],
                    "rows": [[current]],
                }
                return await self._finalize_query(
                    session_id, query, intent, response, 0.0
                )

            # SHOW TABLES
            if "SHOW TABLES" in q_upper:
                if not self.db_state.current_db:
                    return await self._finalize_query(
                        session_id, query, intent, self.NO_DB_ERROR, 0.0
                    )
                tables = self.db_state.list_tables()
                colname = f"Tables_in_{self.db_state.current_db}"
                response = {
                    "columns": [colname],
                    "rows": [[t] for t in tables],
                }
                return await self._finalize_query(
                    session_id, query, intent, response, 0.0
                )

            # SELECT ... FROM table
            table_name = self._parse_select(query)
            if table_name:
                if not self.db_state.current_db:
                    return await self._finalize_query(
                        session_id, query, intent, self.NO_DB_ERROR, 0.0
                    )

                table_info = self.db_state.get_table_data(table_name)
                if table_info:
                    columns = table_info.get("columns", [])
                    rows = table_info.get("rows", [])

                    # If table has fewer than 5 rows → use LLM to generate synthetic data
                    if len(rows) < 5:
                        try:
                            print(f"[DBController] Calling LLM for table: {table_name}")
                            db_context = self.db_state.get_state_summary()
                            llm_raw = await generate_db_response_async(
                                query=query,
                                intent=intent,
                                db_context=db_context,
                            )

                            print(
                                f"[DBController] LLM raw response type: {type(llm_raw)}"
                            )
                            print(
                                f"[DBController] LLM raw response: {llm_raw[:500] if isinstance(llm_raw, str) else llm_raw}"
                            )

                            # Try to extract JSON from the response
                            if isinstance(llm_raw, str):
                                json_data = extract_json_from_text(llm_raw)
                                if json_data:
                                    print("[DBController] Extracted JSON successfully")
                                    response = json_data
                                else:
                                    print(
                                        "[DBController] Failed to extract JSON, wrapping as text"
                                    )
                                    response = {
                                        "columns": ["result"],
                                        "rows": [[llm_raw]],
                                    }
                            elif isinstance(llm_raw, dict):
                                response = llm_raw
                            else:
                                response = {
                                    "columns": ["result"],
                                    "rows": [[str(llm_raw)]],
                                }

                            # Validate the response has proper structure
                            if (
                                not isinstance(response, dict)
                                or "columns" not in response
                                or "rows" not in response
                            ):
                                print(
                                    "[DBController] Invalid response structure, using fallback"
                                )
                                response = {"columns": columns, "rows": []}

                        except Exception as e:
                            print(f"[DBController] LLM error: {e}")
                            import traceback

                            traceback.print_exc()
                            response = {"columns": columns, "rows": []}

                        return await self._finalize_query(
                            session_id, query, intent, response, 0.1
                        )

                    # LIMIT support
                    limit_match = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
                    if limit_match:
                        limit = int(limit_match.group(1))
                        rows = rows[:limit]

                    response = {"columns": columns, "rows": rows}

                    return await self._finalize_query(
                        session_id, query, intent, response, 0.0
                    )

                # Unknown table
                db = self.db_state.current_db or "shophub"
                err = f"ERROR 1146 (42S02): Table '{db}.{table_name}' doesn't exist"
                return await self._finalize_query(session_id, query, intent, err, 0.0)

        # ------------------------
        # LLM FALLBACK
        # ------------------------
        try:
            print(f"[DBController] LLM fallback for query: {query}")
            db_context = self.db_state.get_state_summary()
            fallback_raw = await generate_db_response_async(
                query=query,
                intent=intent,
                db_context=db_context,
            )

            print(
                f"[DBController] Fallback raw: {fallback_raw[:500] if isinstance(fallback_raw, str) else fallback_raw}"
            )

            # Extract JSON if possible
            if isinstance(fallback_raw, str):
                json_data = extract_json_from_text(fallback_raw)
                fallback = json_data if json_data else {"text": fallback_raw}
            else:
                fallback = fallback_raw

        except Exception as e:
            print(f"[DBController] Fallback error: {e}")
            import traceback

            traceback.print_exc()
            fallback = {"text": f"ERROR: {e}"}

        delay = 0.05 + float(np.random.rand()) * 0.2
        return await self._finalize_query(
            session_id,
            query,
            intent,
            fallback,
            delay,
        )

    async def get_action_for_query(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """RL-enhanced query handler - wraps original logic"""
        query = event.get("query", "")

        # 1. Log interaction for RL
        log_interaction(
            session_id=session_id,
            protocol="database",
            input_data=query,
            metadata={
                "intent": self._classify_query(query),
                "suspicious": self._is_suspicious(query),
                "current_db": self.db_state.current_db,
            },
        )

        # 2. Extract current state
        state = extract_state(session_id, protocol="database")

        # 3. Select and execute action
        rl_action = None
        if self.rl_enabled and event.get("query", "").upper().startswith(("SHOW", "SELECT")):
            # For read queries, always use realistic response (no RL)
            response = await self._original_query_handler(session_id, event)
        elif self.rl_enabled:
            rl_action = self.rl_agent.select_action(state)
            response = await self._execute_rl_action(rl_action, session_id, event)
        else:
            response = await self._original_query_handler(session_id, event)

        # 4. Update Q-table (only if RL action was taken)
        if self.rl_enabled and rl_action is not None:
            next_state = extract_state(session_id, protocol="database")
            reward = calculate_reward(state, next_state, protocol="database")
            self.rl_agent.update(state, rl_action, reward, next_state)

        return response

    async def _execute_rl_action(
        self, action: str, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute RL-selected action"""
        query = event.get("query", "")
        intent = self._classify_query(query)

        if action == "REALISTIC_RESPONSE":
            # Use existing logic
            return await self._original_query_handler(session_id, event)

        elif action == "DECEPTIVE_RESOURCE":
            # Return fake sensitive data with honeytokens
            query_lower = query.lower()

            # Fake admin/user tables
            if "user" in query_lower or "admin" in query_lower:
                fake_users = {
                    "columns": ["id", "username", "password_hash", "email", "role"],
                    "rows": [
                        [
                            1,
                            "admin",
                            "$2b$10$HONEYTOKEN_HASH_001",
                            "admin@shophub.com",
                            "superuser",
                        ],
                        [
                            2,
                            "dbadmin",
                            "$2b$10$HONEYTOKEN_HASH_002",
                            "dbadmin@shophub.com",
                            "admin",
                        ],
                        [
                            3,
                            "api_user",
                            "$2b$10$HONEYTOKEN_HASH_003",
                            "api@shophub.com",
                            "service",
                        ],
                    ],
                }
                return await self._finalize_query(
                    session_id, query, intent, fake_users, 0.1
                )

            # Fake credit card / payment data
            if any(
                keyword in query_lower
                for keyword in ["credit", "card", "payment", "transaction"]
            ):
                fake_payments = {
                    "columns": ["id", "card_number", "cvv", "expiry", "cardholder"],
                    "rows": [
                        [1, "4532-HONEYTOKEN-001-1234", "123", "12/26", "John Doe"],
                        [2, "5425-HONEYTOKEN-002-5678", "456", "03/27", "Jane Smith"],
                        [3, "3782-HONEYTOKEN-003-9012", "789", "08/25", "Bob Johnson"],
                    ],
                }
                return await self._finalize_query(
                    session_id, query, intent, fake_payments, 0.1
                )

            # Fake API keys / credentials
            if any(
                keyword in query_lower
                for keyword in ["api", "key", "secret", "token", "credential"]
            ):
                fake_keys = {
                    "columns": ["id", "service", "api_key", "secret_key"],
                    "rows": [
                        [
                            1,
                            "stripe",
                            "pk_live_HONEYTOKEN_STRIPE_001",
                            "sk_live_HONEYTOKEN_STRIPE_SECRET",
                        ],
                        [
                            2,
                            "aws",
                            "AKIA_HONEYTOKEN_AWS_001",
                            "wJalrXUtn_HONEYTOKEN_AWS_SECRET",
                        ],
                        [3, "sendgrid", "SG.HONEYTOKEN_SENDGRID", None],
                    ],
                }
                return await self._finalize_query(
                    session_id, query, intent, fake_keys, 0.1
                )

            # Fallback to realistic if no match
            return await self._original_query_handler(session_id, event)

        elif action == "RESPONSE_DELAY":
            # Add delay then return realistic response
            response = await self._original_query_handler(session_id, event)
            response["delay"] = response.get("delay", 0.0) + float(np.random.uniform(0.5, 2.0))
            return response

        elif action == "MISLEADING_SUCCESS":
            # Claim success for operations that should fail (only for write operations)
            if intent in ["write", "create_table", "drop_table", "alter"]:
                return await self._finalize_query(
                    session_id, query, intent, "Query OK, 1 row affected", 0.05
                )
            # For read operations, fall back to realistic response
            return await self._original_query_handler(session_id, event)

        elif action == "FAKE_VULNERABILITY":
            # Expose fake system tables and sensitive information
            query_lower = query.lower()

            # Fake information_schema with juicy table names
            if "information_schema" in query_lower or "show tables" in query_lower:
                fake_schema = {
                    "columns": ["table_name"],
                    "rows": [
                        ["admin_users"],
                        ["api_keys"],
                        ["backup_credentials"],
                        ["credit_cards"],
                        ["session_tokens"],
                        ["user_passwords"],
                    ],
                }
                return await self._finalize_query(
                    session_id, query, intent, fake_schema, 0.1
                )

            # Fake mysql.user table
            if "mysql.user" in query_lower:
                fake_mysql_users = {
                    "columns": ["user", "host", "authentication_string"],
                    "rows": [
                        ["root", "localhost", "*HONEYTOKEN_MYSQL_ROOT_HASH"],
                        ["shophub_app", "%", "*HONEYTOKEN_MYSQL_APP_HASH"],
                        ["backup_user", "10.0.%", "*HONEYTOKEN_MYSQL_BACKUP_HASH"],
                    ],
                }
                return await self._finalize_query(
                    session_id, query, intent, fake_mysql_users, 0.1
                )

            # Default: suggest SQL injection worked
            return await self._original_query_handler(session_id, event)

        elif action == "TERMINATE_SESSION":
            # Force disconnect
            return {
                "response": "ERROR 2013 (HY000): Lost connection to MySQL server during query",
                "delay": 0.0,
                "disconnect": True,
            }

        # Fallback to realistic response
        return await self._original_query_handler(session_id, event)
