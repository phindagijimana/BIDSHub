"""
Unit tests for Pennsieve Agent.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pennsieve_agent import PennsieveAgent, check_available_space


class TestPennsieveAgent:
    
    @patch('src.pennsieve_agent.shutil.which')
    def test_init_finds_agent(self, mock_which):
        """Test agent initialization when pennsieve CLI is available."""
        mock_which.return_value = '/usr/bin/pennsieve'
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            agent = PennsieveAgent()
            assert agent.agent_path == '/usr/bin/pennsieve'
    
    @patch('src.pennsieve_agent.shutil.which')
    def test_init_fails_when_agent_missing(self, mock_which):
        """Test agent initialization fails when CLI not found."""
        mock_which.return_value = None
        
        with pytest.raises(RuntimeError, match="Pennsieve Agent not found"):
            PennsieveAgent()
    
    def test_build_env(self):
        """Test environment variable building."""
        with patch('src.pennsieve_agent.shutil.which') as mock_which:
            mock_which.return_value = '/usr/bin/pennsieve'
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                agent = PennsieveAgent()
        
        env = agent._build_env('test_key', 'test_secret')
        
        assert 'PENNSIEVE_API_KEY' in env
        assert env['PENNSIEVE_API_KEY'] == 'test_key'
        assert 'PENNSIEVE_API_SECRET' in env
        assert env['PENNSIEVE_API_SECRET'] == 'test_secret'
    
    @patch('src.pennsieve_agent.shutil.which')
    @patch('subprocess.run')
    def test_verify_connection_success(self, mock_run, mock_which):
        """Test successful connection verification."""
        mock_which.return_value = '/usr/bin/pennsieve'
        mock_run.return_value = Mock(returncode=0)
        
        agent = PennsieveAgent()
        result = agent.verify_connection('key', 'secret')
        
        assert result is True
    
    @patch('src.pennsieve_agent.shutil.which')
    @patch('subprocess.run')
    def test_verify_connection_failure(self, mock_run, mock_which):
        """Test failed connection verification."""
        mock_which.return_value = '/usr/bin/pennsieve'
        
        # First call for init, second for verify
        mock_run.side_effect = [
            Mock(returncode=0),  # Init check
            Mock(returncode=1)   # Verify fails
        ]
        
        agent = PennsieveAgent()
        result = agent.verify_connection('bad_key', 'bad_secret')
        
        assert result is False
    
    def test_is_stub_file(self, tmp_path):
        """Test stub file detection."""
        with patch('src.pennsieve_agent.shutil.which') as mock_which:
            mock_which.return_value = '/usr/bin/pennsieve'
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                agent = PennsieveAgent()
        
        # Create stub file (0 bytes)
        stub_file = tmp_path / "stub.nii.gz"
        stub_file.touch()
        
        # Create real file (>0 bytes)
        real_file = tmp_path / "real.nii.gz"
        real_file.write_bytes(b"data")
        
        assert agent.is_stub_file(str(stub_file)) is True
        assert agent.is_stub_file(str(real_file)) is False
    
    def test_get_file_status(self, tmp_path):
        """Test file status detection."""
        with patch('src.pennsieve_agent.shutil.which') as mock_which:
            mock_which.return_value = '/usr/bin/pennsieve'
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                agent = PennsieveAgent()
        
        # Test not_mapped
        status = agent.get_file_status(str(tmp_path / "nonexistent.nii.gz"))
        assert status['status'] == 'not_mapped'
        assert status['exists'] is False
        
        # Test mapped (stub)
        stub = tmp_path / "stub.nii.gz"
        stub.touch()
        status = agent.get_file_status(str(stub))
        assert status['status'] == 'mapped'
        assert status['exists'] is True
        assert status['size'] == 0
        
        # Test downloaded
        real = tmp_path / "real.nii.gz"
        real.write_bytes(b"x" * 1000)
        status = agent.get_file_status(str(real))
        assert status['status'] == 'downloaded'
        assert status['exists'] is True
        assert status['size'] == 1000


def test_check_available_space(tmp_path):
    """Test disk space checking."""
    space = check_available_space(str(tmp_path))
    assert space > 0
    assert isinstance(space, int)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
