"""Repository for agent-related database operations."""

from typing import Optional

from agent.types.agent_info import AgentInfo
from .connection import DatabaseConnection


class AgentRepository:
    """Handles database operations related to agents."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize the agent repository.

        Args:
            db_connection: Database connection manager instance
        """
        self._db = db_connection

    def fetch_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Fetch agent data from the database.

        Args:
            agent_id: The unique identifier of the agent

        Returns:
            Optional[AgentInfo]: Agent information if found, None otherwise

        Raises:
            DatabaseConnectionError: If database connection fails
        """
        query = """
            SELECT a.id, m.user_id, a.wallet_id, a.name, a.wallet_address
            FROM agents a
            JOIN user_agent_mapping m ON a.id = m.agent_id
            WHERE a.id = %s
        """

        with self._db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (agent_id,))
                result = cur.fetchone()

                if result:
                    return AgentInfo(
                        id=result[0],
                        user_id=result[1],
                        wallet_id=result[2],
                        name=result[3],
                        wallet_address=result[4],
                    )
                return None
