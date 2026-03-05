"""
Agent Factory for Per-Dataset Platform Agents.

Creates platform-specific agents with per-dataset credentials, solving
the credential conflict problem in multi-dataset workflows.

Architecture:
- Each dataset gets its own agent instance
- Agents are cached to avoid recreating
- Credentials are isolated per dataset
- No more singleton agent conflicts
"""

import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating platform-specific agents with per-dataset credentials.
    
    Replaces singleton agent pattern with per-dataset instances, ensuring
    each dataset uses its own credentials without conflicts.
    
    Usage:
        factory = AgentFactory(database)
        agent = factory.get_agent(dataset_id)
        agent.download_file(...)  # Uses correct dataset credentials
    """
    
    def __init__(self, database):
        """
        Initialize agent factory.
        
        Args:
            database: Database instance for fetching dataset credentials
        """
        self.db = database
        self._agent_cache: Dict[int, object] = {}
        
    def get_agent(self, dataset_id: int):
        """
        Get or create agent for a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Platform-specific agent instance (PennsieveAgent, OpenNeuroAgent, etc.)
            
        Raises:
            ValueError: If dataset not found or platform unsupported
        """
        # Check cache first
        if dataset_id in self._agent_cache:
            logger.debug(f"Using cached agent for dataset {dataset_id}")
            return self._agent_cache[dataset_id]
        
        # Get dataset from database
        dataset = self.db.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found in database")
        
        # Create platform-specific agent
        platform = dataset['platform'].lower()
        logger.info(f"Creating {platform} agent for dataset {dataset_id} ({dataset['name']})")
        
        agent = self._create_agent(dataset, platform)
        
        # Cache and return
        if agent:
            self._agent_cache[dataset_id] = agent
        
        return agent
    
    def _create_agent(self, dataset: Dict, platform: str):
        """
        Create platform-specific agent with dataset credentials.
        
        Args:
            dataset: Dataset dictionary from database
            platform: Platform name (lowercase)
            
        Returns:
            Agent instance or None for local datasets
            
        Raises:
            ValueError: If platform is unsupported
        """
        if platform == 'pennsieve':
            from src.pennsieve_agent import PennsieveAgent
            
            api_key = dataset.get('api_key_encrypted')
            api_secret = dataset.get('api_secret_encrypted')
            
            if not api_key or not api_secret:
                logger.warning(f"Missing Pennsieve credentials for dataset {dataset['id']}")
                return None
            
            agent = PennsieveAgent()
            agent.credentials = {
                'api_key': api_key,
                'api_secret': api_secret,
                'dataset_name': dataset.get('dataset_id_external')
            }
            
            logger.debug(f"Created PennsieveAgent for dataset: {dataset.get('dataset_id_external')}")
            return agent
        
        elif platform == 'openneuro':
            from src.openneuro_agent import OpenNeuroAgent
            
            api_token = dataset.get('api_key_encrypted')  # Optional for public datasets
            
            agent = OpenNeuroAgent(api_token=api_token)
            logger.debug(f"Created OpenNeuroAgent for dataset: {dataset.get('dataset_id_external')}")
            return agent
        
        elif platform == 'dandi':
            from src.dandi_agent import DANDIAgent
            
            api_token = dataset.get('api_key_encrypted')  # Optional for public dandisets
            
            agent = DANDIAgent(api_token=api_token)
            logger.debug(f"Created DANDIAgent for dandiset: {dataset.get('dataset_id_external')}")
            return agent
        
        elif platform == 'xnat':
            from src.xnat_agent import XNATAgent
            
            server_url = dataset.get('server_url')
            username = dataset.get('api_key_encrypted')
            password = dataset.get('api_secret_encrypted')
            
            if not server_url:
                logger.error(f"Missing XNAT server URL for dataset {dataset['id']}")
                return None
            
            if not username or not password:
                logger.warning(f"Missing XNAT credentials for dataset {dataset['id']}")
                return None
            
            agent = XNATAgent(
                server_url=server_url,
                username=username,
                password=password
            )
            logger.debug(f"Created XNATAgent for server: {server_url}")
            return agent
        
        elif platform == 'hpc':
            from src.hpc_agent import HPCAgent
            
            server_url = dataset.get('server_url')  # HPC hostname
            username = dataset.get('api_key_encrypted')  # SSH username
            password = dataset.get('api_secret_encrypted')  # SSH password (or None if using key)
            
            if not server_url or not username:
                logger.error(f"Missing HPC connection details for dataset {dataset['id']}")
                return None
            
            # Check for SSH key file (stored in root_path if provided)
            key_file = dataset.get('root_path')  # Path to SSH private key
            
            agent = HPCAgent(
                host=server_url,
                username=username,
                password=password,
                key_file=key_file
            )
            logger.debug(f"Created HPCAgent for host: {server_url}")
            return agent
        
        elif platform == 'remote_server':
            from src.remote_server_agent import RemoteServerAgent
            
            server_url = dataset.get('server_url')  # Remote server hostname/IP
            username = dataset.get('api_key_encrypted')  # SSH username
            password = dataset.get('api_secret_encrypted')  # SSH password (or None if using key)
            
            if not server_url or not username:
                logger.error(f"Missing remote server connection details for dataset {dataset['id']}")
                return None
            
            # Check for SSH key file (stored in root_path if provided)
            key_file = dataset.get('root_path')  # Path to SSH private key
            
            agent = RemoteServerAgent(
                host=server_url,
                username=username,
                password=password,
                key_file=key_file
            )
            logger.debug(f"Created RemoteServerAgent for host: {server_url}")
            return agent
        
        elif platform == 'local':
            # Local datasets don't need agents (files already on disk)
            logger.debug(f"Local dataset {dataset['id']}, no agent needed")
            return None
        
        else:
            raise ValueError(f"Unsupported platform: {platform}")
    
    def clear_cache(self, dataset_id: Optional[int] = None):
        """
        Clear cached agent(s).
        
        Useful when dataset credentials are updated or dataset is removed.
        
        Args:
            dataset_id: Specific dataset to clear, or None to clear all
        """
        if dataset_id:
            if dataset_id in self._agent_cache:
                logger.info(f"Clearing cached agent for dataset {dataset_id}")
                del self._agent_cache[dataset_id]
        else:
            logger.info("Clearing all cached agents")
            self._agent_cache.clear()
    
    def get_cached_agent_count(self) -> int:
        """
        Get number of cached agents.
        
        Returns:
            Number of agents currently cached
        """
        return len(self._agent_cache)
    
    def verify_agent(self, dataset_id: int) -> bool:
        """
        Verify agent can be created and credentials work.
        
        Args:
            dataset_id: Dataset ID to verify
            
        Returns:
            True if agent can connect, False otherwise
        """
        try:
            agent = self.get_agent(dataset_id)
            
            if agent is None:
                # Local dataset, no agent needed
                return True
            
            # Check if agent has verify_connection method
            if hasattr(agent, 'verify_connection'):
                return agent.verify_connection()
            
            # If no verify method, assume OK if agent was created
            return True
            
        except Exception as e:
            logger.error(f"Agent verification failed for dataset {dataset_id}: {e}")
            return False
    
    def refresh_agent(self, dataset_id: int):
        """
        Refresh agent by clearing cache and recreating.
        
        Useful after credential updates.
        
        Args:
            dataset_id: Dataset ID to refresh
        """
        self.clear_cache(dataset_id)
        return self.get_agent(dataset_id)
    
    def cleanup_all(self):
        """
        Disconnect all SSH agents (v3.1.1+ connection pooling).
        
        Call this on application shutdown to gracefully close connections.
        """
        for dataset_id, agent in self._agent_cache.items():
            if hasattr(agent, 'disconnect'):
                try:
                    agent.disconnect()
                    logger.info(f"Disconnected agent for dataset {dataset_id}")
                except Exception as e:
                    logger.warning(f"Error disconnecting agent {dataset_id}: {e}")


def create_agent_factory(database) -> AgentFactory:
    """
    Convenience function to create agent factory.
    
    Args:
        database: Database instance
        
    Returns:
        AgentFactory instance
    """
    return AgentFactory(database)
