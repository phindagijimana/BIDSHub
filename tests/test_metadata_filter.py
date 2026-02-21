"""
Unit tests for Metadata Filter.
"""

import pytest
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metadata_filter import MetadataFilter


@pytest.fixture
def sample_participants_tsv(tmp_path):
    """Create sample participants.tsv file."""
    data = """participant_id\tage\tsex\tdiagnosis\tsite
sub-001\t28\tM\tmoderate-TBI\tUCSF
sub-002\t34\tF\tsevere-TBI\tYale
sub-003\t45\tM\tmild-TBI\tUCSF
sub-004\t32\tM\tsevere-TBI\tYale
sub-005\t52\tF\tcontrol\tUCSF
sub-006\t29\tF\tmoderate-TBI\tYale
"""
    
    participants_file = tmp_path / "participants.tsv"
    participants_file.write_text(data)
    
    return tmp_path


class TestMetadataFilter:
    
    def test_init_with_valid_file(self, sample_participants_tsv):
        """Test initialization with valid participants.tsv."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        assert mf.is_available() is True
        assert mf.participants_df is not None
        assert len(mf.participants_df) == 6
    
    def test_init_without_file(self, tmp_path):
        """Test initialization when participants.tsv missing."""
        mf = MetadataFilter(str(tmp_path))
        
        assert mf.is_available() is False
        assert mf.participants_df is None
    
    def test_get_available_fields(self, sample_participants_tsv):
        """Test getting available metadata fields."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        fields = mf.get_available_fields()
        
        assert 'age' in fields
        assert 'sex' in fields
        assert 'diagnosis' in fields
        assert 'site' in fields
        assert 'participant_id' not in fields  # Should be excluded
    
    def test_get_field_values(self, sample_participants_tsv):
        """Test getting unique field values."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        sex_values = mf.get_field_values('sex')
        assert set(sex_values) == {'M', 'F'}
        
        dx_values = mf.get_field_values('diagnosis')
        assert 'moderate-TBI' in dx_values
        assert 'severe-TBI' in dx_values
        assert 'control' in dx_values
    
    def test_get_field_type(self, sample_participants_tsv):
        """Test field type detection."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        assert mf.get_field_type('age') == 'numeric'
        assert mf.get_field_type('sex') == 'categorical'
        assert mf.get_field_type('diagnosis') == 'categorical'
    
    def test_filter_no_criteria(self, sample_participants_tsv):
        """Test filtering with no criteria returns all subjects."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        result = mf.filter_subjects({})
        assert len(result) == 6
    
    def test_filter_by_age_range(self, sample_participants_tsv):
        """Test filtering by age range."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        result = mf.filter_subjects({'age': {'min': 30, 'max': 40}})
        
        assert len(result) == 2  # sub-002 (34), sub-004 (32) - sub-003 (45) is outside range
        assert '002' in result
        assert '004' in result
    
    def test_filter_by_sex(self, sample_participants_tsv):
        """Test filtering by sex."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        result = mf.filter_subjects({'sex': ['M']})
        
        assert len(result) == 3  # sub-001, sub-003, sub-004
        assert '001' in result
        assert '003' in result
        assert '004' in result
    
    def test_filter_by_diagnosis(self, sample_participants_tsv):
        """Test filtering by diagnosis."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        result = mf.filter_subjects({'diagnosis': ['severe-TBI']})
        
        assert len(result) == 2  # sub-002, sub-004
        assert '002' in result
        assert '004' in result
    
    def test_filter_combined_criteria(self, sample_participants_tsv):
        """Test filtering with multiple criteria."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        result = mf.filter_subjects({
            'age': {'min': 25, 'max': 40},
            'sex': ['M'],
            'diagnosis': ['severe-TBI']
        })
        
        assert len(result) == 1  # Only sub-004 matches all criteria
        assert '004' in result
    
    def test_get_filter_summary(self, sample_participants_tsv):
        """Test filter summary statistics."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        summary = mf.get_filter_summary({'sex': ['M']})
        
        assert summary['total_subjects'] == 3
        assert 'demographics' in summary
        assert 'age' in summary['demographics']
        assert summary['demographics']['age']['mean'] == pytest.approx(35.0)
    
    def test_export_filtered_list(self, sample_participants_tsv, tmp_path):
        """Test exporting filtered subject list."""
        mf = MetadataFilter(str(sample_participants_tsv))
        
        output_file = tmp_path / "filtered.csv"
        result = mf.export_filtered_list(
            {'sex': ['M']},
            str(output_file)
        )
        
        assert result is True
        assert output_file.exists()
        
        # Read exported file
        exported_df = pd.read_csv(output_file, sep='\t')
        assert len(exported_df) == 3
        assert all(exported_df['participant_id'].str.startswith('sub-'))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
