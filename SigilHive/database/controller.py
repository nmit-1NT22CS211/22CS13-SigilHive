# controller_intelligent.py
import re
from typing import Dict, Any, List, Optional
from llm_gen import generate_db_response_async


class DatabaseState:
    """Maintains virtual database state"""

    def __init__(self, db_type: str):
        self.db_type = db_type
        self.databases = {}
        self.current_db = None

        # Initialize with some default databases
        if db_type == "mysql":
            self.databases = {
                "information_schema": {
                    "tables": {
                        "schemata": {
                            "columns": ["schema_name", "default_character_set"]
                        },
                        "tables": {
                            "columns": ["table_schema", "table_name", "table_type"]
                        },
                    }
                },
                "mysql": {
                    "tables": {
                        "user": {"columns": ["host", "user", "authentication_string"]},
                    }
                },
                "test": {"tables": {}},
            }
            self.current_db = "test"
        else:  # postgresql
            self.databases = {
                "postgres": {
                    "tables": {
                        "pg_database": {"columns": ["datname", "datdba"]},
                        "pg_tables": {"columns": ["schemaname", "tablename"]},
                    }
                },
                "template0": {"tables": {}},
                "template1": {"tables": {}},
            }
            self.current_db = "postgres"

    def create_database(self, db_name: str) -> bool:
        """Create a new database"""
        if db_name.lower() not in self.databases:
            self.databases[db_name.lower()] = {"tables": {}}
            return True
        return False

    def drop_database(self, db_name: str) -> bool:
        """Drop a database"""
        if db_name.lower() in self.databases and db_name.lower() not in [
            "information_schema",
            "mysql",
            "postgres",
        ]:
            del self.databases[db_name.lower()]
            return True
        return False

    def use_database(self, db_name: str) -> bool:
        """Switch to a database"""
        if db_name.lower() in self.databases:
            self.current_db = db_name.lower()
            return True
        return False

    def create_table(self, table_name: str, columns: List[str]) -> bool:
        """Create a new table in current database"""
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
        """Drop a table"""
        if (
            self.current_db
            and table_name.lower() in self.databases[self.current_db]["tables"]
        ):
            del self.databases[self.current_db]["tables"][table_name.lower()]
            return True
        return False

    def insert_into_table(self, table_name: str, values: List[Any]) -> bool:
        """Insert a row into table"""
        if (
            self.current_db
            and table_name.lower() in self.databases[self.current_db]["tables"]
        ):
            self.databases[self.current_db]["tables"][table_name.lower()][
                "rows"
            ].append(values)
            return True
        return False

    def get_table_data(self, table_name: str) -> Optional[Dict]:
        """Get table structure and data"""
        if (
            self.current_db
            and table_name.lower() in self.databases[self.current_db]["tables"]
        ):
            return self.databases[self.current_db]["tables"][table_name.lower()]
        return None

    def list_databases(self) -> List[str]:
        """List all databases"""
        return list(self.databases.keys())

    def list_tables(self, db_name: str = None) -> List[str]:
        """List tables in a database"""
        db = db_name.lower() if db_name else self.current_db
        if db and db in self.databases:
            return list(self.databases[db]["tables"].keys())
        return []

    def get_state_summary(self) -> str:
        """Get a summary of current state for LLM context"""
        summary = f"Current DB: {self.current_db}\n"
        summary += f"Available DBs: {', '.join(self.list_databases())}\n"
        if self.current_db:
            tables = self.list_tables()
            summary += f"Tables in {self.current_db}: {', '.join(tables) if tables else 'none'}\n"
            for table in tables[:5]:  # Limit to 5 tables
                table_info = self.get_table_data(table)
                if table_info:
                    summary += f"  - {table}: {len(table_info.get('rows', []))} rows, columns: {', '.join(table_info.get('columns', []))}\n"
        return summary


class IntelligentDBController:
    """
    Intelligent controller that maintains database state and uses LLM for realistic responses
    """

    def __init__(self, db_type: str = "postgresql", persona: str = None):
        self.db_type = db_type
        self.persona = persona or f"{db_type}-default"
        self.sessions = {}
        self.db_state = DatabaseState(db_type)

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        """Get or create session state"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "query_history": [],
                "suspicious_count": 0,
            }
        return self.sessions[session_id]

    def _classify_query(self, query: str) -> str:
        """Classify query intent"""
        q_upper = query.upper().strip()

        if any(
            x in q_upper for x in ["SELECT", "SHOW", "DESCRIBE", "DESC", "\\D", "\\L"]
        ):
            return "read"
        elif any(x in q_upper for x in ["INSERT", "UPDATE", "DELETE"]):
            return "write"
        elif any(x in q_upper for x in ["CREATE DATABASE", "CREATE SCHEMA"]):
            return "create_db"
        elif any(x in q_upper for x in ["DROP DATABASE", "DROP SCHEMA"]):
            return "drop_db"
        elif any(x in q_upper for x in ["CREATE TABLE"]):
            return "create_table"
        elif any(x in q_upper for x in ["DROP TABLE"]):
            return "drop_table"
        elif any(x in q_upper for x in ["ALTER"]):
            return "alter"
        elif any(x in q_upper for x in ["GRANT", "REVOKE"]):
            return "admin"
        elif any(x in q_upper for x in ["USE", "\\C"]):
            return "use_db"
        else:
            return "other"

    def _is_suspicious(self, query: str) -> bool:
        """Detect suspicious patterns"""
        q_upper = query.upper()
        suspicious_patterns = [
            "UNION SELECT",
            "OR 1=1",
            "AND 1=1",
            "' OR '",
            "'; DROP",
            "LOAD_FILE",
            "INTO OUTFILE",
            "BENCHMARK(",
            "SLEEP(",
            "PG_SLEEP(",
            "WAITFOR DELAY",
            "XP_CMDSHELL",
            "../",
        ]
        return any(pattern in q_upper for pattern in suspicious_patterns)

    def _parse_create_database(self, query: str) -> Optional[str]:
        """Extract database name from CREATE DATABASE"""
        match = re.search(
            r'CREATE\s+(?:DATABASE|SCHEMA)\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?',
            query,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _parse_drop_database(self, query: str) -> Optional[str]:
        """Extract database name from DROP DATABASE"""
        match = re.search(
            r'DROP\s+(?:DATABASE|SCHEMA)\s+(?:IF\s+EXISTS\s+)?[`"]?(\w+)[`"]?',
            query,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _parse_use_database(self, query: str) -> Optional[str]:
        """Extract database name from USE"""
        match = re.search(r'USE\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        return match.group(1) if match else None

    def _parse_create_table(self, query: str) -> Optional[tuple]:
        """Extract table name and columns from CREATE TABLE"""
        match = re.search(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?\s*\((.*?)\)',
            query,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table_name = match.group(1)
            columns_str = match.group(2)
            # Extract column names (simplified)
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
        """Extract table name from DROP TABLE"""
        match = re.search(
            r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?[`"]?(\w+)[`"]?', query, re.IGNORECASE
        )
        return match.group(1) if match else None

    def _parse_insert(self, query: str) -> Optional[tuple]:
        """Extract table name and values from INSERT"""
        match = re.search(
            r'INSERT\s+INTO\s+[`"]?(\w+)[`"]?.*?VALUES\s*\((.*?)\)',
            query,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table_name = match.group(1)
            values_str = match.group(2)
            # Simple value extraction
            values = [v.strip().strip("'\"") for v in values_str.split(",")]
            return (table_name, values)
        return None

    def _parse_select(self, query: str) -> Optional[str]:
        """Extract table name from SELECT"""
        match = re.search(r'FROM\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        return match.group(1) if match else None

    def _execute_state_change(self, query: str, intent: str) -> tuple[bool, str]:
        """
        Execute state-changing operations and return (success, message)
        """
        if intent == "create_db":
            db_name = self._parse_create_database(query)
            if db_name:
                success = self.db_state.create_database(db_name)
                if success:
                    return True, "Query OK, 1 row affected"
                else:
                    return (
                        False,
                        f"ERROR 1007 (HY000): Can't create database '{db_name}'; database exists",
                    )

        elif intent == "drop_db":
            db_name = self._parse_drop_database(query)
            if db_name:
                success = self.db_state.drop_database(db_name)
                if success:
                    return True, "Query OK, 0 rows affected"
                else:
                    return (
                        False,
                        f"ERROR 1008 (HY000): Can't drop database '{db_name}'; database doesn't exist",
                    )

        elif intent == "use_db":
            db_name = self._parse_use_database(query)
            if db_name:
                success = self.db_state.use_database(db_name)
                if success:
                    return True, "Database changed"
                else:
                    return False, f"ERROR 1049 (42000): Unknown database '{db_name}'"

        elif intent == "create_table":
            table_info = self._parse_create_table(query)
            if table_info:
                table_name, columns = table_info
                success = self.db_state.create_table(table_name, columns)
                if success:
                    return True, "Query OK, 0 rows affected"
                else:
                    return (
                        False,
                        f"ERROR 1050 (42S01): Table '{table_name}' already exists",
                    )

        elif intent == "drop_table":
            table_name = self._parse_drop_table(query)
            if table_name:
                success = self.db_state.drop_table(table_name)
                if success:
                    return True, "Query OK, 0 rows affected"
                else:
                    return False, f"ERROR 1051 (42S02): Unknown table '{table_name}'"

        elif intent == "write":
            insert_info = self._parse_insert(query)
            if insert_info:
                table_name, values = insert_info
                success = self.db_state.insert_into_table(table_name, values)
                if success:
                    return True, "Query OK, 1 row affected"
                else:
                    return (
                        False,
                        f"ERROR 1146 (42S02): Table '{table_name}' doesn't exist",
                    )

        return False, "Query OK"

    def _build_context_for_llm(self, query: str, intent: str) -> str:
        """Build rich context for LLM including current database state"""
        context = self.db_state.get_state_summary()

        # Add specific context based on query
        if intent == "read":
            table_name = self._parse_select(query)
            if table_name:
                table_data = self.db_state.get_table_data(table_name)
                if table_data:
                    context += f"\nQuerying table '{table_name}':\n"
                    context += f"  Columns: {', '.join(table_data['columns'])}\n"
                    context += f"  Rows: {len(table_data['rows'])}\n"
                    if table_data["rows"]:
                        context += "  Sample data:\n"
                        for i, row in enumerate(table_data["rows"][:5]):
                            context += f"    Row {i + 1}: {row}\n"

        return context

    async def get_action_for_query(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main method: receives query event, returns action dict.
        Now with intelligent state management!
        """
        query = event.get("query", "")
        session = self._get_session(session_id)

        # Update session history
        session["query_history"].append(query)
        if len(session["query_history"]) > 20:
            session["query_history"] = session["query_history"][-20:]

        # Classify and check for suspicious activity
        intent = self._classify_query(query)
        is_suspicious = self._is_suspicious(query)

        if is_suspicious:
            session["suspicious_count"] += 1

        # Handle state-changing queries FIRST
        if intent in [
            "create_db",
            "drop_db",
            "use_db",
            "create_table",
            "drop_table",
            "write",
        ]:
            success, message = self._execute_state_change(query, intent)

            delay = 0.1 if is_suspicious else 0.05

            return {
                "response": message,
                "delay": delay,
                "disconnect": session["suspicious_count"] > 10,
            }

        # For read queries, generate response using LLM with current state
        db_context = self._build_context_for_llm(query, intent)

        delay = 0.0
        if is_suspicious:
            delay = min(0.5 + session["suspicious_count"] * 0.2, 2.0)

        should_disconnect = session["suspicious_count"] > 10

        # Generate response using LLM
        try:
            response = await generate_db_response_async(
                query=query,
                db_type=self.db_type,
                intent=intent,
                db_context=db_context,
                table_hint=None,
                persona=self.persona,
            )
        except Exception as e:
            response = f"ERROR: Internal server error - {str(e)}"

        action = {
            "response": response,
            "delay": delay,
        }

        if should_disconnect:
            action["disconnect"] = True

        return action
