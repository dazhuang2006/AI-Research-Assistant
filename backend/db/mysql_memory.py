"""
基于 MySQL 的对话记忆模块

持久化保存会话与聊天消息，替代原项目里的 SQLite 实现。
对外提供的方法名与原项目保持一致，方便上层调用。
"""
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import pymysql

import config


class MySQLConversationMemory:
    """使用 MySQL 持久化保存会话与聊天历史"""

    def __init__(self):
        self.host = config.MYSQL_HOST
        self.port = config.MYSQL_PORT
        self.user = config.MYSQL_USER
        self.password = config.MYSQL_PASSWORD
        self.database = config.MYSQL_DATABASE

        # 确保数据库和表存在
        self._ensure_database()
        self._init_tables()

    @staticmethod
    def _now() -> str:
        """返回适合写入 MySQL DATETIME 的当前时间字符串"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    def _ensure_database(self):
        """先连接 MySQL 服务器本身，数据库不存在时自动创建"""
        server = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset="utf8mb4",
            autocommit=True,
        )
        with server.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        server.close()

    def _connect(self):
        """创建指向目标数据库的连接，并返回 DictCursor 结果"""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

    def _init_tables(self):
        """创建 sessions 和 messages 两张表（如果表不存在）"""
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    created_at DATETIME NOT NULL,
                    last_updated DATETIME NOT NULL,
                    message_count INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    content LONGTEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    metadata TEXT,
                    KEY idx_messages_session (session_id),
                    CONSTRAINT fk_messages_session FOREIGN KEY (session_id)
                        REFERENCES sessions(session_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        conn.close()

    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        创建新的对话会话

        Args:
            session_id: 可选的自定义会话 ID，未提供时自动生成 UUID

        Returns:
            session_id: 创建出的会话 ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT session_id FROM sessions WHERE session_id = %s",
                (session_id,),
            )
            existing = cursor.fetchone()

            if not existing:
                now = self._now()
                cursor.execute(
                    """
                    INSERT INTO sessions (session_id, created_at, last_updated, message_count)
                    VALUES (%s, %s, %s, 0)
                    """,
                    (session_id, now, now),
                )
        conn.close()
        return session_id

    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在

        Args:
            session_id: 会话标识

        Returns:
            会话存在返回 True，否则返回 False
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM sessions WHERE session_id = %s LIMIT 1",
                (session_id,),
            )
            exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ):
        """
        向会话历史中添加一条消息

        Args:
            session_id: 会话标识
            role: 'user'（用户）或 'assistant'（助手）
            content: 消息内容
            metadata: 可选的元数据（sources、workflow_log 等）
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT session_id FROM sessions WHERE session_id = %s",
                (session_id,),
            )
            if not cursor.fetchone():
                conn.close()
                self.create_session(session_id)
                conn = self._connect()

            now = self._now()
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO messages (session_id, role, content, timestamp, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session_id, role, content, now, metadata_json),
                )
                cursor.execute(
                    """
                    UPDATE sessions
                    SET last_updated = %s, message_count = message_count + 1
                    WHERE session_id = %s
                    """,
                    (now, session_id),
                )
        conn.close()

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        获取某个会话的历史记录

        Args:
            session_id: 会话标识
            limit: 可选，限制返回的最近消息条数

        Returns:
            按时间顺序排列的消息列表
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            if limit:
                cursor.execute(
                    """
                    SELECT role, content, timestamp, metadata
                    FROM messages
                    WHERE session_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (session_id, limit),
                )
                rows = list(cursor.fetchall())
                rows.reverse()
            else:
                cursor.execute(
                    """
                    SELECT role, content, timestamp, metadata
                    FROM messages
                    WHERE session_id = %s
                    ORDER BY id ASC
                    """,
                    (session_id,),
                )
                rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            metadata = row["metadata"]
            messages.append({
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "metadata": json.loads(metadata) if metadata else {},
            })
        return messages

    def get_context(
        self,
        session_id: str,
        max_messages: int = 10,
    ) -> str:
        """
        获取适合拼接到 LLM 提示词中的对话上下文

        Args:
            session_id: 会话标识
            max_messages: 最多包含的最近消息条数

        Returns:
            格式化后的会话历史字符串
        """
        messages = self.get_history(session_id, limit=max_messages)
        if not messages:
            return ""

        context_parts = ["Previous conversation:"]
        for msg in messages:
            role = msg["role"].capitalize()
            context_parts.append(f"{role}: {msg['content']}")

        return "\n".join(context_parts)

    def clear_session(self, session_id: str):
        """
        清空某个会话的历史记录

        Args:
            session_id: 会话标识
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM messages WHERE session_id = %s",
                (session_id,),
            )
            cursor.execute(
                "DELETE FROM sessions WHERE session_id = %s",
                (session_id,),
            )
        conn.close()

    def get_all_sessions(self) -> List[str]:
        """
        获取所有有效会话的 ID 列表

        Returns:
            会话 ID 列表
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT session_id FROM sessions ORDER BY last_updated DESC"
            )
            rows = cursor.fetchall()
        conn.close()
        return [row["session_id"] for row in rows]

    def get_session_metadata(self, session_id: str) -> Optional[Dict]:
        """
        获取某个会话的元数据

        Args:
            session_id: 会话标识

        Returns:
            会话元数据；会话不存在时返回 None
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT created_at, last_updated, message_count
                FROM sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        return {
            "created_at": row["created_at"],
            "last_updated": row["last_updated"],
            "message_count": row["message_count"],
        }

    def get_stats(self) -> Dict:
        """
        获取数据库统计信息

        Returns:
            包含数据库统计信息的字典
        """
        conn = self._connect()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM sessions")
            total_sessions = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM messages")
            total_messages = cursor.fetchone()["total"]

            cursor.execute("SELECT AVG(message_count) AS avg_count FROM sessions")
            avg_messages = cursor.fetchone()["avg_count"] or 0
        conn.close()

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "avg_messages_per_session": round(float(avg_messages), 2),
        }


# 全局单例：后续 FastAPI 统一使用这一个实例
conversation_memory = MySQLConversationMemory()
