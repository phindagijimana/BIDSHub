# Data Explorer Connection Flow

## Initial Setup (First Dataset)

### 1. Launch App
```bash
streamlit run app.py
# OR
./explorer
```

### 2. Setup Page Appears
```
┌─────────────────────────────────────┐
│   Data Explorer - Setup             │
├─────────────────────────────────────┤
│                                     │
│ Platform Selection:                 │
│ ○ 🔐 Pennsieve (Private)            │
│ ○ 🌍 OpenNeuro (Public)             │
│                                     │
│ Data Location:                      │
│ ○ ☁️  Cloud only                    │
│ ○ 💻 Local (existing BIDS)          │
│                                     │
│ Configuration:                      │
│ ┌─────────────────────────────────┐ │
│ │ Dataset Name: ____________      │ │
│ │ API Key: **********             │ │
│ │ API Secret: **********          │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Initialize Dataset]                │
└─────────────────────────────────────┘
```

### 3. Initialization Process
```
Progress: [████████████████████] 100%

1/5 ✓ Preparing working directory...
2/5 ✓ Connecting to Pennsieve...
3/5 ✓ Getting dataset structure...
4/5 ✓ Initializing database...
5/5 ✓ Indexing subjects...

✅ Successfully initialized dataset with 245 subjects!
```

**What happens in database:**
```sql
-- Creates first dataset
INSERT INTO datasets (id, name, platform, api_key_encrypted, status)
VALUES (1, 'TrackTBI Main', 'pennsieve', '...', 'active');

-- Links all subjects to dataset_id=1
INSERT INTO subjects (dataset_id, subject_id, local_subject_id, ...)
VALUES (1, 'sub-001', '001', ...),
       (1, 'sub-002', '002', ...),
       ...
```

### 4. Redirects to Dashboard
After initialization → **Dashboard** page loads
- Shows stats from your first dataset
- Sidebar now has "📚 Manage Datasets" button

---

## Adding Additional Datasets

### 1. Navigate to Manage Datasets
```
Sidebar → [📚 Manage Datasets]
```

### 2. Manage Datasets Page
```
┌─────────────────────────────────────────────┐
│   Manage Datasets                            │
├─────────────────────────────────────────────┤
│                                              │
│ Connected Datasets (1/5)                     │
│                                              │
│ ▼ 🔐 TrackTBI Main                          │
│   ├─ Subjects: 245                          │
│   ├─ Platform: Pennsieve                    │
│   ├─ Status: 🟢 Active                      │
│   ├─ Created: 2026-02-21                    │
│   └─ [🔄 Sync] [⏸️ Deactivate] [🗑️ Remove] │
│                                              │
│ ─────────────────────────────────────────── │
│                                              │
│ Add New Dataset                              │
│                                              │
│ Platform:                                    │
│ ○ 🔐 Pennsieve  ○ 🌍 OpenNeuro              │
│                                              │
│ ┌──────────────────────────────────────┐    │
│ │ Dataset Name: TrackTBI Validation    │    │
│ │ Dataset ID: N:dataset:xyz            │    │
│ │ API Key: **********                  │    │
│ │ API Secret: **********               │    │
│ │ Local Path: /data/validation         │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ [ ] Validate BIDS structure                  │
│                                              │
│ [Add Dataset]                                │
└─────────────────────────────────────────────┘
```

### 3. Click "Add Dataset"
```
Processing...
✓ Validating credentials...
✓ Connecting to dataset...
✓ Indexing subjects...
✓ Creating database entries...

✅ Successfully added "TrackTBI Validation" with 103 subjects!
```

**What happens in database:**
```sql
-- Creates second dataset
INSERT INTO datasets (id, name, platform, api_key_encrypted, status)
VALUES (2, 'TrackTBI Validation', 'pennsieve', '...', 'active');

-- Links new subjects to dataset_id=2
INSERT INTO subjects (dataset_id, subject_id, local_subject_id, ...)
VALUES (2, 'sub-201', '201', ...),
       (2, 'sub-202', '202', ...),
       ...
```

### 4. Can Add More (Up to 5 Total)
```
Connected Datasets (2/5)

▼ 🔐 TrackTBI Main (245 subjects)
▼ 🔐 TrackTBI Validation (103 subjects)

Add New Dataset...
```

Continue adding until you reach the limit:
```
Connected Datasets (5/5)

▼ 🔐 TrackTBI Main (245 subjects)
▼ 🔐 TrackTBI Validation (103 subjects)  
▼ 🌍 OpenNeuro ds000246 (89 subjects)
▼ 🌍 OpenNeuro ds000247 (156 subjects)
▼ 🔐 TrackTBI Pilot (47 subjects)

⚠️ Maximum of 5 datasets supported in v1.5.
```

---

## How UI Changes With Multiple Datasets

### Before Adding Datasets (1 Dataset)

**Subjects Browser:**
```
┌────────────────────────────────────────────┐
│ Subjects Browser                           │
├────────────────────────────────────────────┤
│ Search: [_____________]  QC: [All▾]       │
│                                            │
│ Showing 245 subjects                       │
│                                            │
│ Subject ID    QC Status   Sessions  Scans │
│ ──────────────────────────────────────────│
│ TBI011007     Pending     2WK, 6MO    12  │
│ TBI011008     Pass        2WK, 6MO    11  │
│ TBI011009     Pass        2WK         6   │
│ ...                                        │
└────────────────────────────────────────────┘
```

### After Adding Datasets (3+ Datasets)

**NEW Dataset Filter appears:**
```
┌────────────────────────────────────────────┐
│ Subjects Browser                           │
├────────────────────────────────────────────┤
│ Dataset Filter ◄── NEW!                    │
│ Show subjects from:                        │
│ ☑ 🔐 TrackTBI Main                         │
│ ☑ 🔐 TrackTBI Validation                   │
│ ☑ 🌍 OpenNeuro ds000246                    │
│ ─────────────────────────────────────────  │
│                                            │
│ Search: [_____________]  QC: [All▾]       │
│                                            │
│ Showing 437 of 437 subjects                │
│                                            │
│ Dataset           Subject ID   QC   Scans │ ◄── NEW Column!
│ ──────────────────────────────────────────│
│ 🔐 TrackTBI M..  TBI011007    Pass    12  │
│ 🔐 TrackTBI M..  TBI011008    Pass    11  │
│ 🔐 TrackTBI V..  VAL001001    Pend    8   │
│ 🌍 ds000246      sub-01       Pass    15  │
│ ...                                        │
└────────────────────────────────────────────┘
```

**Key UI Changes:**
1. ✨ **Dataset Filter** (multiselect) appears when 2+ datasets
2. ✨ **Dataset Column** added to subject table with platform icon
3. ✨ Filter to view specific datasets or all at once
4. ✨ Subject count shows filtered vs total

---

## How Tables Change

### Database Schema

**Single Dataset (v1.0):**
```sql
subjects
├─ subject_id (PK)
├─ has_2wk
├─ has_6mo
└─ ...

-- No dataset tracking
```

**Multi-Dataset (v1.5):**
```sql
datasets
├─ id (PK)              ← Each dataset gets unique ID
├─ name
├─ platform
└─ ...

subjects
├─ id (PK, auto-increment)
├─ dataset_id (FK) ←──────── Links to datasets.id
├─ subject_id      ← Full ID (sub-001)
├─ local_subject_id ← Short ID (001)
├─ has_2wk
├─ has_6mo
└─ ...

-- Each subject knows which dataset it belongs to
```

### Example Data Flow

**Adding 3 datasets creates this structure:**

```
datasets table:
┌────┬─────────────────────┬────────────┬──────────┐
│ id │ name                │ platform   │ status   │
├────┼─────────────────────┼────────────┼──────────┤
│ 1  │ TrackTBI Main       │ pennsieve  │ active   │
│ 2  │ TrackTBI Validation │ pennsieve  │ active   │
│ 3  │ ds000246            │ openneuro  │ active   │
└────┴─────────────────────┴────────────┴──────────┘

subjects table:
┌────┬────────────┬─────────────┬───────────────────┐
│ id │ dataset_id │ subject_id  │ local_subject_id  │
├────┼────────────┼─────────────┼───────────────────┤
│ 1  │ 1          │ sub-TBI001  │ TBI001           │ ← Dataset 1
│ 2  │ 1          │ sub-TBI002  │ TBI002           │ ← Dataset 1
│ 3  │ 2          │ sub-VAL001  │ VAL001           │ ← Dataset 2
│ 4  │ 2          │ sub-VAL002  │ VAL002           │ ← Dataset 2
│ 5  │ 3          │ sub-01      │ 01               │ ← Dataset 3
│ 6  │ 3          │ sub-02      │ 02               │ ← Dataset 3
└────┴────────────┴─────────────┴───────────────────┘
```

---

## Query Examples

### View all subjects from Dataset 2:
```python
db.get_subjects_by_dataset(dataset_id=2)
# Returns: subjects with dataset_id = 2
```

### View subjects across multiple datasets:
```python
for dataset_id in [1, 2, 3]:
    subjects = db.get_subjects_by_dataset(dataset_id)
    for subj in subjects:
        dataset = db.get_dataset(dataset_id)
        subj['_dataset_name'] = dataset['name']
        subj['_dataset_platform'] = dataset['platform']
```

### Filter subjects in UI:
```python
# If multi-dataset: show dataset selector
if len(datasets) > 1:
    selected_ids = st.multiselect("Show subjects from:", 
                                   [d['id'] for d in datasets])
    
    # Fetch only from selected datasets
    subjects = []
    for ds_id in selected_ids:
        subjects.extend(db.get_subjects_by_dataset(ds_id))
```

---

## Summary

### Connection Flow:
1. **First time**: Setup page → Choose platform → Add 1st dataset → Dashboard
2. **Additional**: Manage Datasets → Add New → Configure → Repeat (up to 5)

### UI Evolution:
- **1 Dataset**: Standard subject list
- **2+ Datasets**: 
  - ✨ Dataset filter appears
  - ✨ Dataset column added to tables
  - ✨ Platform icons (🔐/🌍) show source
  - ✨ Can filter by specific datasets

### Database Changes:
- Each dataset gets unique ID in `datasets` table
- All subjects link back via `dataset_id` foreign key
- Query by dataset to separate/combine data as needed
