# shophub_db_controller.py
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from llm_gen import generate_db_response_async


class ShopHubDatabase:
    """Maintains ShopHub e-commerce database state"""

    def __init__(self):
        self.databases = {}
        self.current_db = None
        self._initialize_shophub()

    def _initialize_shophub(self):
        """Initialize ShopHub e-commerce databases and tables"""

        # System databases
        self.databases = {
            "information_schema": {
                "tables": {
                    "schemata": {
                        "columns": ["SCHEMA_NAME", "DEFAULT_CHARACTER_SET_NAME"],
                        "rows": [
                            ["information_schema", "utf8"],
                            ["mysql", "utf8"],
                            ["shophub", "utf8mb4"],
                            ["shophub_logs", "utf8mb4"],
                        ],
                    },
                    "tables": {
                        "columns": ["TABLE_SCHEMA", "TABLE_NAME", "TABLE_TYPE"],
                        "rows": [
                            ["shophub", "users", "BASE TABLE"],
                            ["shophub", "products", "BASE TABLE"],
                            ["shophub", "categories", "BASE TABLE"],
                            ["shophub", "orders", "BASE TABLE"],
                            ["shophub", "order_items", "BASE TABLE"],
                            ["shophub", "cart", "BASE TABLE"],
                            ["shophub", "payments", "BASE TABLE"],
                            ["shophub", "reviews", "BASE TABLE"],
                            ["shophub", "addresses", "BASE TABLE"],
                            ["shophub", "admin_users", "BASE TABLE"],
                        ],
                    },
                }
            },
            "mysql": {
                "tables": {
                    "user": {
                        "columns": ["Host", "User", "authentication_string"],
                        "rows": [
                            ["localhost", "root", "*[REDACTED]"],
                            ["localhost", "shophub_app", "*[REDACTED]"],
                        ],
                    }
                }
            },
            "shophub": {
                "tables": {
                    "users": {
                        "columns": [
                            "id",
                            "email",
                            "password_hash",
                            "first_name",
                            "last_name",
                            "created_at",
                            "last_login",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["email", "varchar(100)", "NO", "UNI", None, ""],
                            ["password_hash", "varchar(255)", "NO", "", None, ""],
                            ["first_name", "varchar(50)", "YES", "", None, ""],
                            ["last_name", "varchar(50)", "YES", "", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                            ["last_login", "timestamp", "YES", "", None, ""],
                        ],
                        "rows": [],
                    },
                    "categories": {
                        "columns": [
                            "id",
                            "name",
                            "slug",
                            "description",
                            "parent_id",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["name", "varchar(100)", "NO", "", None, ""],
                            ["slug", "varchar(100)", "NO", "UNI", None, ""],
                            ["description", "text", "YES", "", None, ""],
                            ["parent_id", "int", "YES", "MUL", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "products": {
                        "columns": [
                            "id",
                            "name",
                            "slug",
                            "category_id",
                            "price",
                            "stock",
                            "description",
                            "image_url",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["name", "varchar(200)", "NO", "", None, ""],
                            ["slug", "varchar(200)", "NO", "UNI", None, ""],
                            ["category_id", "int", "YES", "MUL", None, ""],
                            ["price", "decimal(10,2)", "NO", "", None, ""],
                            ["stock", "int", "NO", "", "0", ""],
                            ["description", "text", "YES", "", None, ""],
                            ["image_url", "varchar(255)", "YES", "", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "orders": {
                        "columns": [
                            "id",
                            "user_id",
                            "total_amount",
                            "status",
                            "payment_status",
                            "shipping_address_id",
                            "created_at",
                            "updated_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["user_id", "int", "NO", "MUL", None, ""],
                            ["total_amount", "decimal(10,2)", "NO", "", None, ""],
                            ["status", "varchar(50)", "NO", "", "pending", ""],
                            ["payment_status", "varchar(50)", "NO", "", "pending", ""],
                            ["shipping_address_id", "int", "YES", "MUL", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                            [
                                "updated_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED on update CURRENT_TIMESTAMP",
                            ],
                        ],
                        "rows": [],
                    },
                    "order_items": {
                        "columns": [
                            "id",
                            "order_id",
                            "product_id",
                            "quantity",
                            "price",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["order_id", "int", "NO", "MUL", None, ""],
                            ["product_id", "int", "NO", "MUL", None, ""],
                            ["quantity", "int", "NO", "", "1", ""],
                            ["price", "decimal(10,2)", "NO", "", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "cart": {
                        "columns": [
                            "id",
                            "user_id",
                            "product_id",
                            "quantity",
                            "added_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["user_id", "int", "NO", "MUL", None, ""],
                            ["product_id", "int", "NO", "MUL", None, ""],
                            ["quantity", "int", "NO", "", "1", ""],
                            [
                                "added_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "payments": {
                        "columns": [
                            "id",
                            "order_id",
                            "amount",
                            "payment_method",
                            "transaction_id",
                            "status",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["order_id", "int", "NO", "MUL", None, ""],
                            ["amount", "decimal(10,2)", "NO", "", None, ""],
                            ["payment_method", "varchar(50)", "NO", "", None, ""],
                            ["transaction_id", "varchar(100)", "NO", "UNI", None, ""],
                            ["status", "varchar(50)", "NO", "", "pending", ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "reviews": {
                        "columns": [
                            "id",
                            "product_id",
                            "user_id",
                            "rating",
                            "title",
                            "comment",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["product_id", "int", "NO", "MUL", None, ""],
                            ["user_id", "int", "NO", "MUL", None, ""],
                            ["rating", "int", "NO", "", None, ""],
                            ["title", "varchar(200)", "YES", "", None, ""],
                            ["comment", "text", "YES", "", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "addresses": {
                        "columns": [
                            "id",
                            "user_id",
                            "type",
                            "street",
                            "city",
                            "state",
                            "zip_code",
                            "country",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["user_id", "int", "NO", "MUL", None, ""],
                            ["type", "varchar(20)", "NO", "", "shipping", ""],
                            ["street", "varchar(200)", "NO", "", None, ""],
                            ["city", "varchar(100)", "NO", "", None, ""],
                            ["state", "varchar(100)", "NO", "", None, ""],
                            ["zip_code", "varchar(20)", "NO", "", None, ""],
                            ["country", "varchar(100)", "NO", "", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "admin_users": {
                        "columns": [
                            "id",
                            "username",
                            "password_hash",
                            "email",
                            "role",
                            "last_login",
                            "created_at",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["username", "varchar(50)", "NO", "UNI", None, ""],
                            ["password_hash", "varchar(255)", "NO", "", None, ""],
                            ["email", "varchar(100)", "NO", "UNI", None, ""],
                            ["role", "varchar(50)", "NO", "", "viewer", ""],
                            ["last_login", "timestamp", "YES", "", None, ""],
                            [
                                "created_at",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                }
            },
            "shophub_logs": {
                "tables": {
                    "access_logs": {
                        "columns": [
                            "id",
                            "user_id",
                            "ip_address",
                            "action",
                            "endpoint",
                            "timestamp",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["user_id", "int", "YES", "MUL", None, ""],
                            ["ip_address", "varchar(45)", "NO", "", None, ""],
                            ["action", "varchar(100)", "NO", "", None, ""],
                            ["endpoint", "varchar(255)", "NO", "", None, ""],
                            [
                                "timestamp",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                    "error_logs": {
                        "columns": [
                            "id",
                            "error_type",
                            "message",
                            "stack_trace",
                            "timestamp",
                        ],
                        "column_defs": [
                            ["id", "int", "NO", "PRI", None, "auto_increment"],
                            ["error_type", "varchar(100)", "NO", "", None, ""],
                            ["message", "text", "NO", "", None, ""],
                            ["stack_trace", "text", "YES", "", None, ""],
                            [
                                "timestamp",
                                "timestamp",
                                "NO",
                                "",
                                "CURRENT_TIMESTAMP",
                                "DEFAULT_GENERATED",
                            ],
                        ],
                        "rows": [],
                    },
                }
            },
        }

        self.current_db = "shophub"

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
        summary = f"ShopHub E-commerce Database System\n"
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
                    # Add column names for DESCRIBE queries
                    cols = table_info.get("columns", [])
                    summary += f"    Columns: {', '.join(cols)}\n"

        return summary


class ShopHubDBController:
    """Intelligent controller for ShopHub MySQL honeypot"""

    def __init__(self):
        self.db_state = ShopHubDatabase()
        self.sessions = {}

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

        if any(x in q_upper for x in ["DESCRIBE", "DESC"]):
            return "describe"
        elif any(x in q_upper for x in ["SELECT", "SHOW", "EXPLAIN"]):
            return "read"
        elif any(x in q_upper for x in ["INSERT", "UPDATE", "DELETE"]):
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
        elif any(x in q_upper for x in ["GRANT", "REVOKE"]):
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

    async def get_action_for_query(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        query = event.get("query", "")
        session = self._get_session(session_id)

        session["query_history"].append(query)
        if len(session["query_history"]) > 20:
            session["query_history"] = session["query_history"][-20:]

        intent = self._classify_query(query)
        is_suspicious = self._is_suspicious(query)

        if is_suspicious:
            session["suspicious_count"] += 1

        # Handle state-changing queries
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

        # Handle DESCRIBE queries directly
        if intent == "describe":
            table_name = self._parse_describe(query)
            if table_name:
                table_info = self.db_state.get_table_data(table_name)
                if table_info and "column_defs" in table_info:
                    return {
                        "response": {
                            "columns": [
                                "Field",
                                "Type",
                                "Null",
                                "Key",
                                "Default",
                                "Extra",
                            ],
                            "rows": table_info["column_defs"],
                        },
                        "delay": 0.0,
                        "disconnect": session["suspicious_count"] > 10,
                    }

        # Handle read queries
        if intent == "read":
            q_upper = query.upper()

            # SHOW DATABASES
            if "SHOW DATABASES" in q_upper or "SHOW SCHEMAS" in q_upper:
                return {
                    "response": {
                        "columns": ["Database"],
                        "rows": [[db] for db in self.db_state.list_databases()],
                    },
                    "delay": 0.0,
                    "disconnect": session["suspicious_count"] > 10,
                }

            # SHOW TABLES
            if "SHOW TABLES" in q_upper:
                tables = self.db_state.list_tables()
                colname = f"Tables_in_{self.db_state.current_db}"
                return {
                    "response": {"columns": [colname], "rows": [[t] for t in tables]},
                    "delay": 0.0,
                    "disconnect": session["suspicious_count"] > 10,
                }

            # SELECT DATABASE()
            if "DATABASE()" in q_upper or "SCHEMA()" in q_upper:
                return {
                    "response": {
                        "columns": ["DATABASE()"],
                        "rows": [[self.db_state.current_db]],
                    },
                    "delay": 0.0,
                    "disconnect": session["suspicious_count"] > 10,
                }

            # SELECT ... FROM table
            table_name = self._parse_select(query)
            if table_name:
                table_info = self.db_state.get_table_data(table_name)
                if table_info:
                    columns = table_info.get("columns", [])
                    rows = table_info.get("rows", [])

                    # If table is empty or has very few rows, use LLM to generate data
                    if len(rows) < 5:
                        print(
                            f"[controller] Table '{table_name}' has {len(rows)} rows, using LLM to generate data"
                        )
                        # Use LLM for data generation
                        db_context = self.db_state.get_state_summary()
                        delay = (
                            min(0.5 + session["suspicious_count"] * 0.2, 2.0)
                            if is_suspicious
                            else 0.0
                        )

                        try:
                            raw_response = await generate_db_response_async(
                                query=query,
                                intent=intent,
                                db_context=db_context,
                            )

                            print(
                                f"[controller] LLM raw response type: {type(raw_response)}"
                            )
                            print(
                                f"[controller] LLM raw response (first 200 chars): {str(raw_response)[:200]}"
                            )

                            # Try to parse as JSON
                            if isinstance(raw_response, str):
                                raw_response = raw_response.strip()
                                if raw_response.startswith("{"):
                                    try:
                                        response = json.loads(raw_response)
                                        print(
                                            f"[controller] Successfully parsed JSON with keys: {response.keys()}"
                                        )
                                        # Validate it has the right structure
                                        if "columns" in response and "rows" in response:
                                            print(
                                                f"[controller] Valid result set: {len(response['columns'])} columns, {len(response['rows'])} rows"
                                            )
                                        else:
                                            print(
                                                f"[controller] WARNING: JSON missing columns/rows keys"
                                            )
                                            response = {"text": raw_response}
                                    except json.JSONDecodeError as e:
                                        print(f"[controller] JSON parse failed: {e}")
                                        response = {"text": raw_response}
                                else:
                                    response = {"text": raw_response}
                            else:
                                response = raw_response

                        except Exception as e:
                            print(f"[controller] LLM generation error: {e}")
                            response = {
                                "text": f"ERROR: Internal server error - {str(e)}"
                            }

                        return {
                            "response": response,
                            "delay": delay,
                            "disconnect": session["suspicious_count"] > 10,
                        }

                    # Simple LIMIT support for existing data
                    limit_match = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
                    if limit_match:
                        limit = int(limit_match.group(1))
                        rows = rows[:limit]

                    return {
                        "response": {"columns": columns, "rows": rows},
                        "delay": 0.0,
                        "disconnect": session["suspicious_count"] > 10,
                    }
