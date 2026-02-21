# Metadata Filtering Guide

**Feature**: Filter subjects by demographics before downloading  
**Benefit**: Save bandwidth, storage, and time by downloading only relevant subjects

---

## UI Location

**Page**: Download Manager → Top section (before Storage Estimation)

---

## Filter Controls

### 1. Age Range Filter
```
Min Age: [0] ←────────→ [120]
Max Age: [0] ←────────→ [120]
```

**Example**:
- Set Min Age = 18, Max Age = 65
- Only subjects aged 18-65 will be selected

---

### 2. Sex Filter
```
Sex: [☑ M] [☑ F] [☐ Other]
```

**Example**:
- Uncheck "F" to get only males
- Check only "F" to get only females

---

### 3. Diagnosis Filter
```
Diagnosis: [Dropdown - Multiple Select]
Options: mild-TBI, moderate-TBI, severe-TBI, Control
```

**Example**:
- Select only "severe-TBI" and "moderate-TBI"
- Excludes mild cases and controls

---

## Workflow

### Step 1: Set Filters
Navigate to Download Manager and configure your criteria:

```
🎯 Filter by Metadata
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Filter subjects by demographics before downloading 
to save bandwidth and storage

Min Age: [25]      Max Age: [40]

Sex: [☑ M] [☐ F]

Diagnosis: [☑ moderate-TBI] [☑ severe-TBI]

[📊 Preview Filtered Results]  [🗑️ Clear Filters]  Filtered: 28 subjects
```

---

### Step 2: Preview Results
Click "📊 Preview Filtered Results" to see:

```
✓ 28 subjects match your criteria

Demographics ▼
  Age: 25-40 (mean: 32.5)
  Sex: {'M': 28}
  Diagnosis: {'moderate-TBI': 15, 'severe-TBI': 13}

Active filters: Age ≥ 25 | Age ≤ 40 | Sex: M | Diagnosis: moderate-TBI, severe-TBI
```

---

### Step 3: Download Filtered Subjects
The Quick Select buttons now respect your filters:

```
Quick Select
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Filters active: 28 subjects selected

[Select Filtered Subjects]  [Select Complete (Filtered)]  Session: [All ▼]
```

- **Select Filtered Subjects**: Adds scans from all 28 filtered subjects
- **Select Complete (Filtered)**: Adds only subjects with both 2WK and 6MO sessions
- **Session dropdown**: Further filter by session (2WK/6MO/All)

---

## Comparison

### Without Filtering:
```
Download Manager
├─ Storage Estimation
│  ├─ Queued Items: 400 files
│  ├─ Total Size: 1.2 TB
│  └─ Available Space: 500 GB ❌ INSUFFICIENT
│
└─ Quick Select
   └─ [Select All Subjects] → Downloads ALL 200 subjects
```

### With Filtering:
```
Download Manager
├─ 🎯 Filter by Metadata (NEW)
│  ├─ Age: 25-40
│  ├─ Sex: Male only
│  ├─ Diagnosis: moderate/severe-TBI
│  └─ Preview: 28 subjects match
│
├─ Storage Estimation
│  ├─ Queued Items: 56 files
│  ├─ Total Size: 168 GB
│  └─ Available Space: 500 GB ✅ SUFFICIENT
│
└─ Quick Select
   └─ [Select Filtered Subjects] → Downloads ONLY 28 subjects
```

**Savings**: 85% less data (168 GB vs 1.2 TB)

---

## Use Cases

### 1. Exploratory Analysis
*"I want to test my analysis pipeline on a small subset first"*
- Filter: Age 30-35, Males only
- Result: 8 subjects instead of 200
- Quick iteration without full download

### 2. Hypothesis-Driven Research
*"My study compares young vs old adults with severe TBI"*
- Cohort 1: Age 18-30, Diagnosis: severe-TBI
- Cohort 2: Age 60-80, Diagnosis: severe-TBI
- Downloads only relevant subjects for comparison

### 3. Grant-Specific Data
*"My grant funds female-only TBI research"*
- Filter: Sex: Female
- Downloads only applicable subjects
- Stays within scope of funding

### 4. Storage-Constrained Labs
*"Our server only has 200 GB available"*
- Preview different filter combinations
- Find subset that fits within storage limits
- Download strategically

---

## Technical Details

### Backend: `src/metadata_filter.py`

```python
class MetadataFilter:
    def __init__(self, bids_root: str):
        """Loads participants.tsv with subject metadata"""
    
    def filter_subjects(self, criteria: Dict) -> List[str]:
        """Returns subject IDs matching criteria"""
        # Example criteria:
        # {'age': {'min': 25, 'max': 40}, 'sex': ['M'], 'diagnosis': ['severe-TBI']}
    
    def get_filter_summary(self, criteria: Dict) -> Dict:
        """Returns demographics summary of filtered subjects"""
```

### Integration: `app.py` → `page_downloads()`

```python
# Initialize filter
metadata_filter = MetadataFilter(st.session_state.bids_root)

# Build criteria from UI inputs
filter_criteria = {}
if min_age > 0 or max_age < 120:
    filter_criteria['age'] = {'min': min_age, 'max': max_age}
if selected_sex != all_sex_values:
    filter_criteria['sex'] = selected_sex
# ... etc

# Get filtered subject IDs
filtered_ids = metadata_filter.filter_subjects(filter_criteria)

# Modify Quick Select to use filtered_ids
if filter_active:
    subjects = [db.get_subject(sid) for sid in filtered_ids]
else:
    subjects = db.get_all_subjects()
```

---

## Dependencies

### Required File: `participants.tsv`

Standard BIDS file at dataset root:

```
participant_id    age    sex    diagnosis         site
sub-001          28     M      moderate-TBI      UCSF
sub-002          34     F      severe-TBI        Stanford
sub-003          45     M      mild-TBI          UCSF
...
```

**If missing**: Filter UI shows warning, falls back to downloading all subjects

---

## Future Enhancements (v2.0+)

### Advanced Filters:
- Custom metadata fields (e.g., `handedness`, `education_years`)
- Date ranges (e.g., `scan_date between 2020-2022`)
- Multi-dataset filtering (cross-dataset cohorts)

### Smart Previews:
- Estimated download time
- Modality breakdown per filtered cohort
- QC status distribution

### Saved Filters:
- Save common filter combinations
- Share filters with collaborators
- Apply filters to exports

---

## Summary

**Value Proposition**: 
Research-driven downloads - get exactly the data you need, nothing more.

**Time to Implement**: ~3 hours (already done!)

**Impact**: 
- 50-90% reduction in download size for targeted studies
- Faster iteration during analysis development
- Better resource utilization for storage-constrained labs
