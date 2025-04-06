import logging
import json
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from typing import Dict, Any, Optional, Union

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

class DatabaseTool(BaseTool):
    name = "database"
    description = (
        "Interacts with databases to execute SQL queries. "
        "Input is a dictionary with: 'query' (SQL statement), 'connection' (optional connection name from config), "
        "and 'params' (optional parameters for SQL query). "
        "Returns query results as formatted text. Use responsibly."
    )
    is_dangerous: bool = True

    def __init__(self, connection_strings: Dict[str, str] = None, max_results: int = 100):
        """
        Initializes the DatabaseTool.
        
        Args:
            connection_strings: Dictionary mapping connection names to connection strings.
                Default connection is 'default'.
            max_results: Maximum number of rows to return.
        """
        self.max_results = max_results
        self.connection_strings = connection_strings or {"default": "sqlite:///workspace/agent.db"}
        self.engines = {}  # Lazy load engines
        logger.info(f"DatabaseTool initialized with {len(self.connection_strings)} connection strings")
        
        # Create default SQLite DB if it doesn't exist
        if "default" in self.connection_strings and self.connection_strings["default"].startswith("sqlite:///"):
            db_path = self.connection_strings["default"].replace("sqlite:///", "")
            try:
                conn = sqlite3.connect(db_path)
                conn.close()
                logger.info(f"Verified access to default SQLite database at {db_path}")
            except Exception as e:
                logger.warning(f"Could not access default SQLite database: {e}")
    
    def _get_engine(self, connection_name: str):
        """Gets or creates a SQLAlchemy engine for the specified connection."""
        if connection_name not in self.connection_strings:
            raise ValueError(f"Connection '{connection_name}' not defined in configuration.")
            
        if connection_name not in self.engines:
            try:
                self.engines[connection_name] = create_engine(self.connection_strings[connection_name])
                logger.info(f"Created database engine for connection '{connection_name}'")
            except Exception as e:
                logger.error(f"Failed to create database engine for '{connection_name}': {e}")
                raise
                
        return self.engines[connection_name]
    
    def execute(self, query: str, connection: str = "default", params: Optional[Dict[str, Any]] = None) -> str:
        """
        Executes a SQL query against the specified database.
        
        Args:
            query: The SQL query to execute.
            connection: The name of the connection to use (from configuration).
            params: Optional parameters for the SQL query.
            
        Returns:
            The query results as formatted text.
        """
        if not query:
            return "Error: No SQL query provided."
        
        if params is None:
            params = {}
            
        try:
            logger.info(f"Executing SQL query on connection '{connection}'")
            logger.debug(f"Query: {query}")
            
            engine = self._get_engine(connection)
            
            # Determine if this is a SELECT query or a modification query
            is_select = query.strip().lower().startswith(("select", "show", "describe", "explain"))
            
            if is_select:
                # For SELECT queries, return results
                df = pd.read_sql(query, engine, params=params)
                
                if len(df) > self.max_results:
                    logger.warning(f"Query returned {len(df)} rows, truncating to {self.max_results}")
                    df = df.head(self.max_results)
                    truncated = True
                else:
                    truncated = False
                
                # Format results
                if len(df) == 0:
                    result = "Query executed successfully. No results returned."
                else:
                    result = f"Query returned {len(df)} rows:\n"
                    # Format as markdown table
                    result += df.to_markdown(index=False)
                    if truncated:
                        result += f"\n(Results truncated to {self.max_results} rows)"
            else:
                # For INSERT, UPDATE, DELETE, etc.
                with engine.begin() as conn:
                    result = conn.execute(query, params)
                    row_count = result.rowcount
                result = f"Query executed successfully. Rows affected: {row_count}"
            
            logger.info(f"SQL query executed successfully on '{connection}'")
            return result
            
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}", exc_info=True)
            return f"Error executing SQL query: {str(e)}"
