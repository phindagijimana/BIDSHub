"""
Unit tests for OpenNeuro Agent.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestOpenNeuroAgent:
    
    @patch('openneuro.download')
    def test_init_success(self, mock_download):
        """Test agent initialization."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        assert agent.api_token is None
    
    @patch('openneuro.download')
    def test_init_with_token(self, mock_download):
        """Test agent initialization with API token."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent(api_token='test_token')
        assert agent.api_token == 'test_token'
    
    @patch('openneuro.download')
    def test_validate_dataset_id_valid(self, mock_download):
        """Test dataset ID validation with valid IDs."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        assert agent.validate_dataset_id('ds000246') is True
        assert agent.validate_dataset_id('ds123456') is True
        assert agent.validate_dataset_id('ds000001') is True
    
    @patch('openneuro.download')
    def test_validate_dataset_id_invalid(self, mock_download):
        """Test dataset ID validation with invalid IDs."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        assert agent.validate_dataset_id('invalid') is False
        assert agent.validate_dataset_id('ds12345') is False  # Too short
        assert agent.validate_dataset_id('ds1234567') is False  # Too long
        assert agent.validate_dataset_id('DS000246') is False  # Uppercase
    
    @patch('openneuro.download')
    def test_download_dataset_success(self, mock_download):
        """Test successful dataset download."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        result = agent.download_dataset(
            dataset_id='ds000246',
            target_dir='/tmp/test'
        )
        
        assert result is True
        mock_download.assert_called_once()
    
    @patch('openneuro.download')
    def test_download_with_include_patterns(self, mock_download):
        """Test download with include patterns."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        agent.download_dataset(
            dataset_id='ds000246',
            target_dir='/tmp/test',
            include_patterns=['sub-001/**', 'sub-002/**']
        )
        
        call_kwargs = mock_download.call_args[1]
        assert 'include' in call_kwargs
        assert call_kwargs['include'] == ['sub-001/**', 'sub-002/**']
    
    @patch('openneuro.download')
    def test_download_with_exclude_patterns(self, mock_download):
        """Test download with exclude patterns."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        agent.download_dataset(
            dataset_id='ds000246',
            target_dir='/tmp/test',
            exclude_patterns=['**/sourcedata/**']
        )
        
        call_kwargs = mock_download.call_args[1]
        assert 'exclude' in call_kwargs
    
    @patch('openneuro.download')
    def test_download_subject_with_prefix(self, mock_download):
        """Test subject download adds 'sub-' prefix."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        agent.download_subject(
            dataset_id='ds000246',
            subject_id='001',  # No prefix
            target_dir='/tmp/test'
        )
        
        call_kwargs = mock_download.call_args[1]
        assert 'include' in call_kwargs
        assert 'sub-001/**' in call_kwargs['include']
    
    @patch('openneuro.download')
    def test_download_subject_with_sessions(self, mock_download):
        """Test subject download with specific sessions."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        agent.download_subject(
            dataset_id='ds000246',
            subject_id='sub-001',
            target_dir='/tmp/test',
            sessions=['01', '02']
        )
        
        call_kwargs = mock_download.call_args[1]
        include = call_kwargs['include']
        assert 'sub-001/ses-01/**' in include
        assert 'sub-001/ses-02/**' in include
    
    @patch('openneuro.download')
    def test_download_by_modality(self, mock_download):
        """Test download filtered by modality."""
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        agent.download_by_modality(
            dataset_id='ds000246',
            target_dir='/tmp/test',
            modalities=['anat', 'func']
        )
        
        call_kwargs = mock_download.call_args[1]
        include = call_kwargs['include']
        assert '**/anat/**' in include
        assert '**/func/**' in include


@patch('requests.get')
def test_check_openneuro_connection_success(mock_get):
    """Test OpenNeuro connection check succeeds."""
    from src.openneuro_agent import check_openneuro_connection
    mock_get.return_value = Mock(status_code=200)
    
    result = check_openneuro_connection()
    assert result is True


@patch('requests.get')
def test_check_openneuro_connection_failure(mock_get):
    """Test OpenNeuro connection check fails."""
    from src.openneuro_agent import check_openneuro_connection
    mock_get.side_effect = Exception("Network error")
    
    result = check_openneuro_connection()
    assert result is False


def test_participants_tsv_requests_only_tsv():
    """Regression: download_participants_tsv must request only participants.tsv.

    Many OpenNeuro datasets (e.g. ds000001) ship no participants.json, and
    openneuro-py aborts the whole download if an included path is missing —
    which previously dropped all demographic metadata (age/sex) silently.
    """
    with patch('openneuro.download'):
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        with patch.object(agent, 'download_dataset', return_value=True) as mock_dl:
            agent.download_participants_tsv('ds000001', '/tmp/x')
        _, kwargs = mock_dl.call_args
        assert kwargs.get('include_patterns') == ['participants.tsv']


def test_import_neutralizes_vscode_pid(monkeypatch):
    """Regression: the agent clears VSCODE_PID so openneuro-py doesn't switch to
    Jupyter-notebook progress bars, which raise "IProgress not found" outside a
    notebook (e.g. when BIDSHub is launched from a VS Code terminal)."""
    import importlib
    import os
    monkeypatch.setenv('VSCODE_PID', '12345')
    import src.openneuro_agent as mod
    importlib.reload(mod)
    assert 'VSCODE_PID' not in os.environ


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
