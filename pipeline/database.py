import sqlite3
import os

class PipelineDatabase:
    def __init__(self, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        self.db_path = os.path.join(output_dir, "output.sqlite")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                entity_type TEXT,
                mention_text TEXT,
                is_new_entity INTEGER
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_entity_id TEXT,
                relation_type TEXT,
                to_entity_id TEXT
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT,
                property_name TEXT,
                property_value TEXT,
                reported_at TEXT,
                email_id TEXT
            )
            """)
            conn.commit()

    def insert_entity(self, entity_id: str, entity_type: str, mention_text: str, is_new: bool):
        with sqlite3.connect(self.db_path) as conn:
            conn.cursor().execute(
                "INSERT OR IGNORE INTO entities VALUES (?, ?, ?, ?)",
                (entity_id, entity_type, mention_text, 1 if is_new else 0)
            )

    def insert_relation(self, from_id: str, relation_type: str, to_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.cursor().execute(
                "INSERT INTO relations (from_entity_id, relation_type, to_entity_id) VALUES (?, ?, ?)",
                (from_id, relation_type, to_id)
            )

    def insert_observation(self, entity_id: str, prop_name: str, prop_value: str, reported_at: str, email_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.cursor().execute(
                "INSERT INTO observations (entity_id, property_name, property_value, reported_at, email_id) VALUES (?, ?, ?, ?, ?)",
                (entity_id, prop_name, prop_value, reported_at, email_id)
            )