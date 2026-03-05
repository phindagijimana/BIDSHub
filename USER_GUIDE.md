# BIDSHub User Guide

**Complete guide to using BIDSHub for BIDS neuroimaging dataset management**

Version: 2.0 
Last Updated: February 5, 2026

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Platform Connections](#platform-connections)
3. [Browsing Datasets & Subjects](#browsing-datasets--subjects)
4. [MRI Viewer](#mri-viewer)
5. [Download Manager](#download-manager)
6. [Quality Control](#quality-control)
7. [Managing Multiple Datasets](#managing-multiple-datasets)
8. [Advanced Workflows](#advanced-workflows)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Launch BIDSHub

```bash
# From BIDSHub directory
./hub start

# Or directly
python -m streamlit run app.py
```

**BIDSHub opens in your browser**: `http://localhost:8501`

### First Launch Experience

When you first launch BIDSHub, you'll see:

**Home Page**:
- Welcome message: "BIDS Neuroimaging Platform"
- Feature overview highlighting 7 platform support
- Two navigation buttons:
 - **Home** - Current page
 - **Setup** - Configure your first dataset

**What to do first**: Click "Get Started ->" or "Setup" button

---

## Sample Datasets for Testing

BIDSHub includes 4 pre-configured sample datasets (2 OpenNeuro + 2 DANDI) perfect for testing and learning the platform without needing to set up credentials or connect to external platforms.

### Available Sample Datasets

**OpenNeuro Datasets:**

**1. OpenNeuro Sample - Minimal MRI (ds005115)**
- **Size:** 1 subject with 40 sessions over 30 days
- **Use Case:** Dense-sampling deep phenotyping study (28andHe)
- **Content:** T1w structural MRI, resting-state fMRI, physiological data
- **URL:** https://openneuro.org/datasets/ds005115
- **Best For:** First-time users, multi-session workflows, time-series analysis
- **Note:** OpenNeuro datasets require download before viewing in NIfTI viewer

**2. OpenNeuro Sample - Motor/Language fMRI (ds000114)**
- **Size:** 10 subjects, test-retest (2 sessions per subject, 2-3 days apart)
- **Use Case:** Task fMRI validation for pre-surgical planning
- **Content:** Motor, language, and spatial attention tasks + DTI + T1w
- **URL:** https://openneuro.org/datasets/ds000114
- **Best For:** QC workflows, test-retest reliability, task fMRI testing
- **Note:** OpenNeuro datasets require download before viewing in NIfTI viewer

**DANDI Datasets:**

**3. DANDI Sample - Brain Cell Census (000026)**
- **Size:** Human brain cell census for Brodmann Areas 44/45
- **Use Case:** MRI structural data with cytoarchitectural boundaries
- **Content:** Magnetic resonance imaging (MRI) structural scans
- **URL:** https://dandiarchive.org/dandiset/000026
- **Best For:** Testing DANDI integration, structural MRI workflows
- **Advantage:** Supports direct file-level access and streaming without full download

**4. DANDI Sample - 7T MR Structural (000058)**
- **Size:** 7T MRI structural images with quantitative maps
- **Use Case:** Ultra-high field MRI structural imaging
- **Content:** 7T MR structural images with B0 and B1+ parameter maps
- **URL:** https://dandiarchive.org/dandiset/000058
- **Best For:** Testing high-resolution MRI, quantitative imaging workflows
- **Advantage:** Supports direct file-level access and streaming without full download

### Using Sample Datasets (No Setup Required)

1. **Navigate to Manage Datasets**
   - Click "Manage Datasets" from the sidebar
   - You'll see the sample datasets already listed with status "active"

2. **Sync Dataset Metadata**
   - Select a sample dataset (e.g., "OpenNeuro Sample - Minimal MRI")
   - Click the "Sync" button
   - Wait for metadata indexing to complete (displays subject and scan counts)

3. **Browse and Test Features**
   - Go to "Browse Subjects" to view indexed subjects
   - Use metadata filters to practice filtering
   - View NIfTI images in the Viewer page
   - Practice QC workflows on sample scans
   - Test downloading selected scans

**Benefits:**
- No API keys or credentials required
- All OpenNeuro data is publicly accessible
- Perfect for learning before connecting your own datasets
- Test all BIDSHub features without touching real data

### Key Differences: OpenNeuro vs DANDI

**OpenNeuro:**
- All datasets are public and BIDS-compliant
- GraphQL API returns only top-level directory structure
- Individual scans require downloading dataset first (no file-level streaming)
- Best workflow: Download subjects, then use "From File System" viewer mode

**DANDI:**
- Mixed formats (NWB + BIDS), need to filter for BIDS MRI datasets
- REST API provides full file listings and direct download URLs
- Supports file-level access and streaming (no full dataset download needed)
- Best workflow: Sync metadata, then stream individual scans directly in viewer

### Managing Sample Datasets

Sample datasets can be managed using the provided script:

```bash
# Add sample datasets to database
python scripts/add_sample_datasets.py add

# List all OpenNeuro datasets in database
python scripts/add_sample_datasets.py list

# Remove sample datasets
python scripts/add_sample_datasets.py remove
```

---

## Platform Connections

### Supported Platforms

BIDSHub supports 7 neuroimaging platforms:

| Platform | Type | Access | Best For |
|----------|------|--------|----------|
| **Pennsieve** | Private research datasets | API credentials | Your institution's private data |
| **OpenNeuro** | Public BIDS repository | API token (optional) | 1000+ public datasets |
| **XNAT** | Institutional archive | Server URL + credentials | University/hospital archives |
| DANDI | Neurophysiology archive | API token (optional) | NWB neurophysiology data |
| **HCP** | Human Connectome Project | AWS credentials | High-quality multimodal MRI |
| LORIS | Longitudinal research | Server URL + credentials | Multi-site longitudinal studies |
| FITBIR | Federal TBI research | NIH credentials | Restricted TBI research data |

**Bold platforms** are most commonly used for typical neuroimaging research.

---

### Initial Setup (First Dataset)

The first time you use BIDSHub, you need to configure your first dataset connection.

#### Setup Page Walkthrough

**Step 1: Choose Platform**

Navigate to: **Setup** page

You'll see two columns:

**Left Column - Platform Selection**:
```
Choose data platform

 Pennsieve - Private research datasets <- Click dropdown


Options:
• Pennsieve - Private research datasets
• OpenNeuro - Public BIDS repository
• XNAT - Institutional neuroimaging archive
• DANDI - Neurophysiology archive
• HCP - Human Connectome Project
• LORIS - Longitudinal research system
• FITBIR - Federal TBI research (restricted)
```

**Platform Info Box**:
After selecting, you'll see info about the chosen platform:
- **Pennsieve**: "Private research datasets with upload/download support"
- **OpenNeuro**: "1000+ public BIDS datasets, free downloads"
- etc.

**Right Column - BIDS Dataset Configuration**:
```
Data location
○ Cloud only (browse & download remotely)
○ Local (BIDS data already on disk)
```

**Choose Your Mode**:

**Option A: Cloud Only** (most common)
- Browse datasets stored on the cloud platform
- Download files on-demand
- No local BIDS data needed initially
- Info box: "No local data needed - browse cloud datasets directly"

**Option B: Local** (if you have BIDS data locally)
- Work with existing BIDS dataset on your disk
- No downloads needed (already local)
- Info box: "Use existing local BIDS dataset"

---

#### Connection Examples

### Example 1: Connect to Pennsieve (Cloud Mode)

**Scenario**: You have a private dataset on Pennsieve called "TrackTBI"

**Steps**:

1. **Platform Selection** (left column):
 ```
 Choose: Pennsieve - Private research datasets
 ```

2. **Data Location** (right column):
 ```
 Select: - Cloud only (browse & download remotely)
 ```

3. **Local Working Directory** (appears below):
 ```
 Local Working Directory (optional)
 /Users/yourname/data-explorer/datasets
 ```
 This is where downloaded files will be saved. Default is fine.

4. **Pennsieve Configuration** (appears below):
   
 **Pennsieve Dataset Name**:
 ```
 TrackTBI <- Your dataset name on Pennsieve
 ```
   
 **Credentials** (two columns):
 ```
 Pennsieve API Key Pennsieve API Secret
 ****************** ********************
 ```

5. **Click**: "Initialize Dataset" button
 - Button becomes enabled once all required fields are filled
 - Shows as blue primary button

6. **Initialization Process** (watch progress):
 ```
 Initializing dataset...
 20%
 1/5 Preparing working directory...
   
 40%
 2/5 Connecting to Pennsieve...
   
 60%
 3/5 Fetching dataset structure...
   
 80%
 4/5 Parsing BIDS data...
   
 100%
 5/5 Setup complete!
   
 OK Successfully connected to Pennsieve
 OK Found 660 subjects in dataset
 OK Database initialized
 ```

7. **Success!**
 - Sidebar navigation now shows all pages:
 - Dashboard
 - Subjects
 - Downloads
 - Quality Control
 - Manage Datasets
 - You're redirected to the Dashboard

---

### Example 2: Connect to OpenNeuro (Cloud Mode)

**Scenario**: Browse public dataset "ds003974" from OpenNeuro

**Steps**:

1. **Platform**: Select "OpenNeuro - Public BIDS repository"

2. **Data Location**: Select "Cloud only"

3. **OpenNeuro Dataset ID**:
 ```
 ds003974 <- Any OpenNeuro dataset ID
 ```
 Link shown: "Browse datasets at openneuro.org"

4. **API Token**: Leave blank (optional, only for private datasets)

5. **Local Working Directory**: Accept default or customize
 ```
 /Users/yourname/data-explorer/datasets
 ```

6. **Click**: "Initialize Dataset"

7. **Initialization**:
 ```
 1/5 Preparing working directory...
 2/5 Connecting to OpenNeuro...
 3/5 Fetching dataset structure...
 4/5 Parsing BIDS data...
 5/5 Setup complete!
   
 OK Successfully connected to OpenNeuro
 OK Found 120 subjects
 ```

8. **Ready to browse!**

---

### Example 3: Add Local BIDS Dataset

**Scenario**: You have a BIDS dataset on your disk at `/data/my-study/`

**Steps**:

1. **Platform**: Select any (Pennsieve or OpenNeuro recommended)
 - Platform doesn't affect local mode, just for metadata tracking

2. **Data Location**: Select "- Local (BIDS data already on disk)"
 - Info box changes: "Use existing local BIDS dataset"

3. **BIDS Directory Path** (appears below):
 ```
 /data/my-study/ <- Absolute path to your BIDS dataset
 ```
   
 **Real-time validation** shows:
 ```
 OK Directory found
 OK dataset_description.json found (if present)
 WARNING: participants.tsv not found (if missing)
 ```

4. **Skip Credentials**: For local mode, all cloud credential fields are optional

5. **Click**: "Initialize Dataset"

6. **Local Indexing**:
 ```
 1/5 Preparing working directory...
 2/5 Scanning local BIDS structure...
 3/5 Indexing subjects...
 4/5 Parsing scan metadata...
 5/5 Setup complete!
   
 OK Indexed 150 subjects from local dataset
 OK All files marked as downloaded
 ```

7. **Done!** You can now browse your local data offline.

---

### Example 4: Connect to XNAT (Institutional Server)

**Scenario**: Your university has an XNAT server at `https://xnat.uni.edu`

**Steps**:

1. **Platform**: Select "XNAT - Institutional neuroimaging archive"
 - Info: "Institutional archive for DICOM/NIfTI neuroimaging data"

2. **Data Location**: Select "Cloud only" (most common)

3. **XNAT Configuration** (appears below):
   
 **Server URL**:
 ```
 https://xnat.uni.edu
 ```
   
 **Credentials**:
 ```
 Username: your_xnat_username
 Password: ******************
 ```
   
 **Project ID**:
 ```
 TBI_Project_2024 <- Your XNAT project
 ```

4. **Working Directory**: Accept default

5. **Click**: "Initialize Dataset"

6. **Connection Process**:
 ```
 Connecting to XNAT...
 OK Successfully authenticated
 OK Found project: TBI_Project_2024
 OK Indexed 85 subjects
 ```

---

### Complete Cloud Dataset Workflow

**End-to-end workflow for working with cloud datasets**:

```
1. Add Dataset
 Manage Datasets -> Add New Dataset -> Choose platform
 -> Enter credentials -> Click "Add Dataset"
 OK Dataset added to BIDSHub

2. Sync Subjects
 Subjects page -> Select dataset -> Click "Sync Subjects"
 -> Wait 30-60 seconds -> Refresh page (F5)
 OK Subjects list fetched with metadata

3. Filter & Browse
 Subjects page -> Apply filters (age, sex, diagnosis, modalities)
 -> View filtered subjects in table
 OK Cohort identified

4. Download Selected
 Select subjects -> Click "Queue for Download"
 -> Downloads page -> Start Queue
 OK Files downloaded locally

5. View & QC
 Subjects page -> View Details -> Click [View] on scans
 -> MRI Viewer opens -> Review quality
 OK Data reviewed and ready for analysis
```

**Time Estimate**:
- Add dataset: 1-2 minutes
- Sync subjects (100-500): 30-90 seconds
- Filter & browse: 2-5 minutes
- Download (varies by size): Minutes to hours
- QC review: 1-2 minutes per subject

---

## Browsing Datasets & Subjects

### Subjects Browser Page

**Navigate to**: Sidebar -> **Subjects**

This is your main workspace for exploring subjects across all connected datasets.

---

### Page Layout

#### Header Section

```

 BIDSHub > Subjects

 Subjects Browser

```

#### Dataset Filter (Multi-Dataset Mode)

If you have 2+ datasets, you'll see:

```
Dataset Filter

Show subjects from:

 × [Pennsieve] TrackTBI 
 × [OpenNeuro] ds003974 <- Click to select/deselect
 × [Local] My_Local_Study 


Showing: 3 datasets selected
```

**Usage**:
- Click **×** to remove a dataset from view
- Click dataset name to add it back
- Select multiple datasets to browse them together
- All subjects from selected datasets appear in unified table below

---

#### Search and Filters

```

 Search subjects QC Status Session 
 TBI011007 All ▼ All ▼ 

```

**Search Box**:
- Type any part of subject ID: `TBI011`, `sub-001`, etc.
- Searches across all selected datasets
- Real-time filtering as you type

**QC Status Filter**:
- **All** - Show all subjects (default)
- **Pending** - Not yet reviewed
- **Pass** - Passed QC
- **Fail** - Failed QC
- **Needs Review** - Flagged for re-review

**Session Filter**:
- **All** - All sessions
- **2WK** - Only 2-week timepoint
- **6MO** - Only 6-month timepoint
- **Both** - Subjects with both sessions

---

#### Subjects Table

After filters, you'll see:

```
Showing 120 of 660 subjects


 Subject ID Dataset Sessions Scans QC Status Actions 

 TBI011007 TrackTBI 2WK, 6MO 12 - Pending [View] View 
 TBI011008 TrackTBI 2WK, 6MO 12 OK Pass [View] View 
 sub-001 ds003974 ses-01 8 - Pending [View] View 
 sub-002 ds003974 ses-01 8 - Pending [View] View 
 subject-014 My_Local baseline 4 X Fail [View] View 


 Table Features:
• Sortable columns (click column headers)
• Scrollable (if many subjects)
• Color-coded QC status
• Eye icon ([View]) to view subject details
```

**QC Status Badges**:
- **- Pending** - Gray badge, not reviewed yet
- **OK Pass** - Green badge, passed QC
- **WARNING: Needs Review** - Yellow badge, flagged for attention
- **X Fail** - Red badge, failed QC

---

#### View Subject Details

Below the table:

```


View Subject Details

Select subject to view

 TBI011007 <- Click dropdown


 View Details Export Filtered List 

```

**Workflow**:
1. Select a subject from dropdown
2. Click "View Details" -> Opens subject detail page
3. Or click "Export Filtered List" -> Downloads CSV of all filtered subjects

---

### Subject Detail Page

When you click "View Details" on a subject, you see:

#### Subject Header

```

 BIDSHub > Subjects > TBI011007

 Subject: TBI011007


Dataset: TrackTBI
Platform: [Pennsieve]
Local ID: TBI011007
```

#### Subject Metadata

```
Subject Metadata


 Age Sex Sessions Total Scans 

 34 M 2 12 


Additional Fields (from participants.tsv):
• Group: TBI
• Diagnosis: Moderate TBI
• GCS: 12
• Days_Since_Injury: 14
```

#### Sessions & Scans

```


Sessions & Scans

Session: 2WK (2-week post-injury)


 Modality Suffix Downloaded Size Path Actions 

 anat T1w OK Yes 12.3 MB /path/.. [View] View 
 anat T2w OK Yes 10.8 MB /path/.. [View] View 
 anat FLAIR OK Yes 11.2 MB /path/.. [View] View 
 func rest X No 120 MB stub v Queue 
 dwi dwi X No 245 MB stub v Queue 
 fmap phasediff X No 8.5 MB stub v Queue 


Session: 6MO (6-month follow-up)


 Modality Suffix Downloaded Size Path Actions 

 anat T1w OK Yes 11.9 MB /path/.. [View] View 
 anat T2w OK Yes 10.3 MB /path/.. [View] View 
 anat FLAIR OK Yes 11.0 MB /path/.. [View] View 
 func rest X No 118 MB stub v Queue 
 dwi dwi X No 240 MB stub v Queue 
 fmap phasediff X No 8.2 MB stub v Queue 

```

**Understanding the Table**:

**Downloaded Column**:
- **OK Yes** - File is available locally, can view immediately
- **X No** - Metadata only (stub), needs download to view

**Actions Column**:
- **[View] View** - Opens in MRI Viewer (if downloaded)
- **v Queue** - Adds to Download Manager queue (if not downloaded)

---

#### Bulk Actions (Bottom of Page)

```


Bulk Actions

[ ] Select all scans from this subject


 v Queue All for Download View Files 


Selected: 0 scans (0 MB)
```

**Workflow**:
1. Check "Select all scans" box
2. Click "Queue All for Download" -> Adds all scans to download queue
3. Or click "View Files" -> Shows file paths and JSON sidecars

---

### Browsing Multiple Datasets

**Scenario**: You have 3 datasets connected

**Subjects Page**:

```
Dataset Filter

Show subjects from:
[X] [Pennsieve] TrackTBI (660 subjects)
[X] [OpenNeuro] ds003974 (120 subjects)
[X] [Local] My_Study (50 subjects)

Showing: 830 subjects total
```

**Cross-Dataset Browsing**:
- All 830 subjects shown in unified table
- "Dataset" column shows which dataset each subject is from
- Search works across all datasets
- Filters apply to all selected datasets
- QC tracking per subject (regardless of source dataset)

**Use Cases**:
- Compare subjects across datasets
- Build cohorts from multiple sources
- Unified QC workflow across datasets
- Export combined subject lists

---

### Search and Filter Examples

#### Example 1: Find Specific Subject

```
Search: TBI011007

Result: 1 subject found

 TBI011007 TrackTBI 2WK, 6MO 

```

#### Example 2: QC Filter

```
QC Status: Pass

Result: 340 subjects (all with Pass status)
```

#### Example 3: Session Filter

```
Session: both

Result: 450 subjects (only those with both 2WK and 6MO sessions)
```

#### Example 4: Combined Filters

```
Search: TBI
QC Status: Pending
Session: both

Result: 85 subjects
• Subject IDs contain "TBI"
• QC status is Pending
• Have both 2WK and 6MO sessions
```

---

### Syncing Subjects from Cloud Platforms

**New Feature**: Fetch subject lists and metadata from connected cloud datasets

#### When to Sync

After adding a cloud dataset (OpenNeuro, DANDI, Pennsieve, XNAT), you need to sync subjects to populate BIDSHub's database.

#### Sync Workflow

Navigate to: **Subjects** page

At the top, you'll see:

```


Sync Subjects from Cloud

Fetch subject lists and metadata from connected cloud platforms


 Select dataset to sync: [OpenNeuro] TBI Study 


 Sync Subjects <- Click to start

```

**Steps**:

1. **Select Dataset**: Choose which cloud dataset to sync
2. **Click "Sync Subjects"**: Initiates fetch from platform
3. **Wait**: Takes 20-60 seconds depending on dataset size
 - Progress shown: "[Sync] Fetching subject list from OpenNeuro..."
 - " Saving X subjects to database..."
4. **Refresh Page**: After sync completes, refresh browser (F5)
5. **View Results**: Subjects table now shows all synced subjects

**What Gets Synced**:
- Subject IDs
- Session information
- Demographics (age, sex, diagnosis) - if available in participants.tsv
- Modality flags (has T1w, fMRI, DWI, etc.)
- Metadata from participants.tsv

**Platform-Specific Notes**:
- **OpenNeuro**: Fetches from GraphQL API + participants.tsv
- **DANDI**: Fetches from dandiset structure (limited metadata)
- **Pennsieve**: Fetches from remote dataset structure
- **XNAT**: Fetches from project subjects with demographics

#### Manual Refresh Workaround

**Current Limitation**: UI doesn't auto-update after sync completes

**Workaround**:
```
1. Click "Sync Subjects"
2. Wait 30-60 seconds (watch for "Sync complete!" message if visible)
3. Press F5 to refresh the page
4. Subjects appear in table
```

---

### Advanced Metadata Filters

**New Feature**: Filter subjects by demographics and scan modalities

Navigate to: **Subjects** page -> Expand "Advanced Metadata Filters"

```
▼ Advanced Metadata Filters


 Min Age Max Age Sex Diagnosis 

 18 65 [X] M [X] F [ ] O TBI 


Required Modalities:
[X] Anatomical (T1/T2)
[X] Functional (fMRI)
[ ] Diffusion (DWI)
[ ] Fieldmap
```

**Filter Options**:

**Age Range**:
- Min Age: Minimum age in years (0-120)
- Max Age: Maximum age in years (0-120)
- Filters subjects within age range

**Sex**:
- M (Male), F (Female), O (Other)
- Select one or multiple
- Empty = show all

**Diagnosis**:
- Text search in diagnosis field
- Case-insensitive
- Matches partial strings (e.g., "TBI" matches "Moderate TBI")

**Required Modalities**:
- Filter subjects that MUST have selected scan types
- Multiple selections = AND logic (must have all)
- Options:
 - **Anatomical (T1/T2)**: Has T1w or T2w scans
 - **Functional (fMRI)**: Has functional MRI
 - **Diffusion (DWI)**: Has diffusion imaging
 - **Fieldmap**: Has field map scans

#### Filter Workflow Example

**Goal**: Find males aged 25-40 with TBI who have both T1w and fMRI

```
1. Expand "Advanced Metadata Filters"

2. Set filters:
 Min Age: 25
 Max Age: 40
 Sex: [X] M (only male)
 Diagnosis: "TBI"
 Required Modalities:
 [X] Anatomical (T1/T2)
 [X] Functional (fMRI)

3. Filters apply automatically as you type

4. Results:
 "Showing 42 of 660 subjects"
   
 Table shows only matching subjects
```

#### Enhanced Subject Table

After syncing, the subjects table displays metadata:

```

 Subject ID Age Sex Diagnosis Modalities QC Status 

 sub-001 34 M TBI T1/T2, fMRI Pending 
 sub-002 28 F Control T1/T2, DWI Pending 
 sub-003 45 M TBI T1/T2 Pending 

```

**Modalities Column Shows**:
- T1/T2: Has anatomical scans
- fMRI: Has functional scans
- DWI: Has diffusion scans
- FMAP: Has fieldmaps

#### Quick Actions

Below the subject table:

```
Quick Actions


 Queue All 42 for Download Subjects Avg Age 
 42 32.5 

```

**Features**:
- **Queue All for Download**: Adds all filtered subjects to download queue
- **Subjects**: Shows count of filtered subjects
- **Avg Age**: Shows average age of filtered subjects (if metadata available)

#### Export Filtered Subjects

```
View Subject Details


 Select subject to view: sub-001 


 View Details Export Filtered List 

```

**Export Filtered List**:
- Downloads CSV of all filtered subjects
- Includes: Subject ID, Age, Sex, Diagnosis, Modalities, QC Status
- Filename: `subjects_YYYYMMDD_HHMMSS.csv`
- Use for analysis pipelines or sharing with collaborators

#### Metadata Availability

**Note**: Metadata fields depend on platform and dataset:

**Full Metadata** (participants.tsv available):
- OpenNeuro datasets with participants.tsv
- Local BIDS datasets with participants.tsv
- Age, sex, diagnosis, group, handedness, site

**Limited Metadata** (no participants.tsv):
- DANDI datasets (primarily NWB, limited BIDS metadata)
- Some OpenNeuro datasets without participants.tsv
- Only subject IDs and modality flags available

**Check Metadata Availability**:
```
After sync, view the subjects table:
- If Age/Sex/Diagnosis columns show values -> Metadata available
- If columns are empty -> No participants.tsv, metadata not available
```

---

### Browse Platform Datasets (Before Adding)

**New Feature**: Browse available datasets on a platform before adding them to BIDSHub

#### How to Access

Navigate to: **Manage Datasets** page -> Scroll to "Add New Dataset"

#### Browse Workflow

**Step 1: Expand Browse Section**

```
Add New Dataset


▼ Browse Platform Datasets
  
 Preview available datasets before adding them to BIDSHub

 Platform: OpenNeuro <- Select platform to browse
  
 [If OpenNeuro selected: No credentials needed for browsing public datasets]
 [If Pennsieve/XNAT: Enter credentials below]
```

**Step 2: Enter Browse Credentials** (if required)

For Pennsieve:
```
Pennsieve API Key Pennsieve API Secret
****************** ********************
```

For XNAT:
```
XNAT Server URL: https://xnat.uni.edu
Username: your_username
Password: ******************
```

For OpenNeuro:
```
API Token (optional): [leave blank for public datasets]
```

**Step 3: Click "[Search] Browse Available Datasets"**

Loading indicator appears:
```
[Search] Browsing OpenNeuro datasets...
 Connecting...
```

**Step 4: View Results**

```
Found 1247 datasets on OpenNeuro


 ds003974
BOLD response to motion in area V5/MT
• Subjects: 120
• Modified: 2024-08-15
[Select]

 ds000246
OpenPain: A multi-center fMRI study of pain processing
• Subjects: 124
• Modified: 2023-11-20
[Select]

 ds002785
Developmental changes in resting-state functional connectivity
• Subjects: 180
• Modified: 2024-01-10
[Select]

... (more datasets)
```

**Step 5: Select a Dataset**

Click **[Select]** button on any dataset:

```
OK Selected: ds003974
 Dataset information saved for auto-fill
```

**Step 6: Form Auto-Fills**

The "Add Dataset" form below automatically fills:
```
Dataset Name: ds003974 <- Auto-filled
Dataset ID: ds003974 <- Auto-filled
```

**Step 7: Complete and Add**

- Review auto-filled information
- Adjust if needed (e.g., change dataset name to something more descriptive)
- Click "+ Add Dataset"
- Dataset is added to BIDSHub!

---

## MRI Viewer

The MRI Viewer lets you visualize NIfTI neuroimaging files interactively.

### Opening the Viewer

**Method 1: From Subject Details**
1. Navigate to **Subjects** page
2. Click "View Details" on a subject
3. In the scan table, click **[View] View** icon next to any scan
4. Viewer opens with the selected image

**Method 2: Direct Navigation**
- Sidebar -> **Viewer**
- If no image selected, shows instructions on how to select one

---

### Viewer Interface

#### Scan Information Bar

At the top, you see the scan metadata:

```

 Subject Session Modality Suffix 

 TBI011007 2WK anat T1w 

```

**Loading Status**:
```
Loading image... [Sync]

↓
OK Loaded: sub-TBI011007_ses-2WK_T1w.nii.gz
```

---

#### Image Information

```
Image Information


 Dimensions Voxel Size (mm) Data Type 

 256 × 256 × 176 1.00 × 1.00 × 1.00 float32 


Volume: 256 × 256 × 176 voxels
Resolution: 1mm isotropic
```

---

#### View Tabs (3 Anatomical Planes)

```


Select View


 Axial (Z) Sagittal(X) Coronal (Y) 

```

##### Tab 1: Axial View

```
▼ Axial (Z) [active tab]


Axial View - Looking down from the top

Slice: <-> 88
 0 176


                                                 
 [MRI Image] 
 Axial Slice 88/176 
                                                 
 Shows brain from top view 
                                                 


Slice 88 of 176 (Z-axis)
```

**Usage**:
- **Slider**: Drag to scroll through slices (0 to 176)
- **Keyboard**: Use arrow keys to navigate slices quickly
- **Mouse wheel**: Scroll through slices (if enabled)

##### Tab 2: Sagittal View

```
▼ Sagittal (X)


Sagittal View - Looking from the side

Slice: <-> 128
 0 256


                                                 
 [MRI Image] 
 Sagittal Slice 128/256 
                                                 
 Shows brain from side view (left/right) 
                                                 


Slice 128 of 256 (X-axis)
```

**Use Case**: 
- View brain laterally
- Identify left/right hemisphere structures
- Check midline structures

##### Tab 3: Coronal View

```
▼ Coronal (Y)


Coronal View - Looking from the front

Slice: <-> 128
 0 256


                                                 
 [MRI Image] 
 Coronal Slice 128/256 
                                                 
 Shows brain from front view (anterior) 
                                                 


Slice 128 of 256 (Y-axis)
```

**Use Case**:
- View brain from front/back
- Check anterior/posterior structures
- Identify symmetry issues

---

#### Display Options

Below the image viewer:

```


Display Options

Colormap

 gray ▼ 


Options: gray, viridis, plasma, hot, cool, jet


 v Save Current View [Sync] Reset View 

```

**Colormap**:
- **gray** - Standard grayscale (default, most common)
- **viridis** - Perceptually uniform, blue-green-yellow
- **plasma** - Purple-orange-yellow
- **hot** - Black-red-yellow-white
- **cool** - Cyan-magenta
- **jet** - Rainbow (blue-red)

**Actions**:
- **Save Current View** - Downloads current slice as PNG image
- **Reset View** - Returns to middle slice with gray colormap

---

#### Viewer Keyboard Shortcuts

When focused on the viewer:

| Key | Action |
|-----|--------|
| `↑` | Previous slice |
| `↓` | Next slice |
| `Home` | First slice |
| `End` | Last slice |
| `Tab` | Switch between view tabs |

---

#### Stub File Detection

If you try to view an undownloaded file:

```
WARNING: Stub File Detected

This file appears to be a metadata stub without actual image data.
To view this image, please download it first using the Download Manager.


 Go to Download Manager 

```

**What to do**:
1. Click "Go to Download Manager"
2. Queue the subject's scans for download
3. Wait for download to complete
4. Return to subject and click [View] View again
5. Image now loads successfully

---

#### Viewer Performance

**Fast Loading** (Local or Downloaded):
- Local datasets: <0.5 seconds
- Downloaded files (SSD): <1 second
- Large 4D files (fMRI): 2-5 seconds

**Slow/Error Conditions**:
- Network-mounted drives: May be slow (depends on network)
- Corrupted NIfTI: Shows error message
- Stub files: Warning message, can't view
- Missing files: Error with file path

---

### Viewer Tips

**Tip 1: Start with Middle Slice**
- Viewer opens at slice_max/2 (middle of volume)
- Best starting point for most anatomical scans
- Adjust from there to see areas of interest

**Tip 2: Use Different Views for Different Structures**
- **Axial**: Best for ventricles, basal ganglia, cortical surface
- **Sagittal**: Best for corpus callosum, midline structures, cerebellum
- **Coronal**: Best for hippocampus, amygdala, frontal-temporal lobes

**Tip 3: Gray Colormap for Anatomy**
- Use **gray** for T1w, T2w, FLAIR (anatomical scans)
- Matches radiological conventions
- Easier to identify tissues

**Tip 4: Colored Colormaps for Functional Data**
- Use **viridis** or **plasma** for fMRI activation maps
- Use **hot** for statistical maps (SPM convention)
- Highlights intensity variations

**Tip 5: Save Important Views**
- Click "Save Current View" to export as PNG
- Great for presentations, papers, or reports
- Includes slice number in filename

---

## Download Manager

### Accessing Download Manager

Navigate to: Sidebar -> **Downloads**

**Purpose**: Manage file downloads from cloud platforms (Pennsieve, OpenNeuro, XNAT, etc.)

---

### Download Manager Interface

#### Metadata Filtering Section

At the top:

```


Filter by Metadata

Note: Filter subjects by demographics before downloading to save bandwidth and storage


 Min Age Max Age 

 18 65 


Sex
[X] M [X] F

Diagnosis
[X] Moderate TBI [X] Severe TBI [X] Control


 Preview Filtered Results Clear Filters 

```

**Workflow**:
1. **Set Filters**: Age range, sex, diagnosis, etc.
2. **Preview**: Click "Preview Filtered Results"
3. **Review**: See how many subjects match
4. **Download**: Only matching subjects are queued

**Preview Results**:
```
OK 85 subjects match your criteria

▼ View Demographics
 Age: 18-65 (mean: 34.2)
 Sex: 45 M, 40 F
 Diagnosis: 60 Moderate TBI, 25 Severe TBI
```

---

#### Download Queue Section

```


Download Queue

Current Queue: 12 files (1.2 GB)


 Subject Session Modality Size Status Action 

 TBI001 2WK T1w 12 MB OK Downloaded — 
 TBI001 2WK T2w 11 MB v Downloading 45% 
 TBI001 2WK FLAIR 11 MB [Queued] Queued 
 TBI001 6MO T1w 12 MB [Queued] Queued 
 TBI002 2WK T1w 12 MB [Queued] Queued 
 TBI002 2WK T2w 11 MB [Queued] Queued 
 ... ... ... ... ... ... 


Progress: 1/12 files completed
 8%


 > Start Queue || Pause Clear Queue 

```

**Queue Status Icons**:
- **[Queued] Queued** - Waiting in queue
- **v Downloading** - Currently downloading (shows progress %)
- **OK Downloaded** - Complete
- **X Failed** - Download error (hover for details)

**Actions**:
- **** - Remove individual file from queue
- **> Start Queue** - Begin downloading
- **|| Pause** - Pause current downloads
- ** Clear Queue** - Remove all items from queue

---

### Download Workflow

#### Workflow 1: Download Specific Subject

**Scenario**: You want to download all scans for subject TBI011007

**Steps**:

1. **Navigate**: Subjects page

2. **Find Subject**: 
 - Use search: `TBI011007`
 - Or scroll through table
 - Click "View Details"

3. **Subject Detail Page Opens**:
 ```
 Subject: TBI011007
   
 Session: 2WK
   
 anat T1w X No 12 MB v Queue 
 anat T2w X No 11 MB v Queue 
 func rest X No 120 MB v Queue 
   
 ```

4. **Add to Queue**:
 - **Option A**: Click v Queue on each scan individually
 - **Option B**: Check "Select all scans" -> Click "Queue All for Download"

5. **Navigate**: Downloads page (sidebar)

6. **View Queue**:
 ```
 Download Queue
 Current Queue: 6 files (185 MB)
   
 All scans for TBI011007 (both sessions) now queued
 ```

7. **Start Download**: Click "> Start Queue"

8. **Monitor Progress**:
 ```
 v Downloading TBI011007_ses-2WK_T1w.nii.gz
 67%
   
 Progress: 2/6 files completed
 33%
 ```

9. **Completion**:
 ```
 OK All downloads complete!
 6/6 files downloaded successfully
 185 MB transferred
 ```

10. **View Files**: Return to Subject Details
 ```
 anat T1w OK Yes 12 MB [View] View 
 anat T2w OK Yes 11 MB [View] View 
 ```
 Now you can view the scans!

---

#### Workflow 2: Download Filtered Cohort

**Scenario**: Download all T1w scans for subjects aged 25-45 with TBI

**Steps**:

1. **Navigate**: Downloads page

2. **Set Metadata Filters**:
 ```
 Min Age: 25 Max Age: 45
 Sex: [X] M [X] F (both selected)
 Diagnosis: [X] Moderate TBI [X] Severe TBI
 ```

3. **Preview**:
 ```
 Click: "Preview Filtered Results"
   
 Result:
 OK 85 subjects match your criteria
   
 ▼ View Demographics
 Age: 25-45 (mean: 34.2)
 Sex: 45 M, 40 F
 ```

4. **Select Modalities**:
 ```
 Which modalities to download?
 [X] T1w
 [ ] T2w
 [ ] FLAIR
 [ ] rest (fMRI)
 [ ] dwi
 ```

5. **Select Sessions**:
 ```
 Which sessions?
 [X] 2WK
 [X] 6MO
 ```

6. **Add to Queue**:
 ```
 Click: "Add Filtered Subjects to Queue"
   
 Result:
 OK Added 170 scans to download queue
 (85 subjects × 2 sessions × 1 modality)
 Total size: 2.1 GB
 ```

7. **Estimate**:
 ```
 Note: Estimated download time: 15-20 minutes
 (Based on average 2 MB/s connection)
 ```

8. **Start Download**:
 ```
 Click: "> Start Queue"
   
 Monitor:
 v Downloading TBI011007_ses-2WK_T1w.nii.gz
 Progress: 15/170 files (9%)
 Elapsed: 3 min 15 sec
 Remaining: ~12 min
 ```

9. **Completion**:
 ```
 OK Download complete!
 170/170 files downloaded
 2.1 GB transferred in 18 min 32 sec
 ```

---

### Download Manager Features

#### Concurrent Downloads

BIDSHub downloads multiple files simultaneously:

```
v Downloading (3 concurrent):
 1. TBI011007_T1w.nii.gz - 78%
 2. TBI011008_T1w.nii.gz - 56%
 3. TBI011009_T1w.nii.gz - 23%

Queue: 167 files remaining
```

**Performance**:
- Default: 3 concurrent downloads
- Optimizes bandwidth usage
- Faster than sequential downloads

#### Automatic Retry

If download fails:

```
X Failed: TBI011007_T1w.nii.gz
 Error: Connection timeout

Auto-retry: Attempt 1 of 3
v Retrying in 5 seconds...
```

**Retry Logic**:
- Automatically retries failed downloads
- Up to 3 attempts
- Exponential backoff (5s, 10s, 20s)
- Reports permanent failures

#### Progress Tracking

```
Current Download: TBI011007_ses-2WK_T1w.nii.gz
File Progress: - 67% (8.2 MB / 12.3 MB)

Overall Progress: 45/170 files
- 26%

Downloaded: 540 MB / 2.1 GB
Speed: 2.4 MB/s
Elapsed: 4 min 15 sec
Remaining: ~12 min
```

---

### Download Storage

**Where files are saved**:

Cloud datasets:
```
{Local Working Directory}/{dataset_name}/
 sub-{subject}/
 ses-{session}/
 {modality}/
 {BIDS filename}.nii.gz
```

Example:
```
/Users/yourname/data-explorer/datasets/TrackTBI/
 dataset_description.json
 participants.tsv
 sub-TBI011007/
 ses-2WK/
 anat/
 sub-TBI011007_ses-2WK_T1w.nii.gz
 sub-TBI011007_ses-2WK_T1w.json
 sub-TBI011007_ses-2WK_T2w.nii.gz
 sub-TBI011007_ses-2WK_T2w.json
 func/
 sub-TBI011007_ses-2WK_task-rest_bold.nii.gz
 ses-6MO/
 anat/
 sub-TBI011007_ses-6MO_T1w.nii.gz
 ...
 sub-TBI011008/
 ...
```

**BIDS-compliant structure** - ready for processing pipelines!

---

## Quality Control

### QC Dashboard

Navigate to: Sidebar -> **Quality Control**

BIDSHub provides two QC modes:

```

 Manual QC Automated QC 

```

---

### Manual QC (Human Review)

#### QC Overview

```
Manual QC Overview


 Pending Pass Needs Rev. Fail 

 520 100 25 15 
 78.8% 15.2% 3.8% 2.3% 


Progress: 140/660 subjects reviewed (21.2%)
- 21%
```

**Metrics Explained**:
- **Pending**: Not yet reviewed (default status)
- **Pass**: Passed QC review (good quality)
- **Needs Review**: Flagged for re-review or second opinion
- **Fail**: Failed QC (poor quality, artifacts, etc.)

---

#### QC Filters

```
Filter


 QC Status Session Dataset 

 pending ▼ all ▼ all ▼ 


 Apply Filters 

```

**Use Case**: Focus on specific subjects for review
```
Example: Review only pending subjects from 2WK session
 QC Status: pending
 Session: 2WK
 Dataset: TrackTBI
  
 -> Shows 280 pending subjects from 2WK timepoint
```

---

#### Quick QC Interface

```
Quick QC


 Subject ID: TBI011007 


Current Status: - Pending


 Mark as: 
    
 OK Pass WARNING: Needs Rev. X Fail [Reset] Reset 
    


QC Notes (optional):

 Motion artifact in T1w, needs re-acquisition 
                                                     


 Save QC Status 


 Next Subject -> 

```

**Workflow**:
1. Subject loads automatically (first pending subject)
2. Review the subject (view scans using [View] button)
3. Mark QC status: Pass, Needs Review, or Fail
4. Add notes (optional): Describe issues or observations
5. Click "Save QC Status"
6. Click "Next Subject" -> Loads next pending subject
7. Repeat for all subjects

---

#### Bulk QC Operations

```
Bulk QC Operations

[ ] Select all pending subjects (520 subjects)


 Mark as Pass Mark as Fail Clear Selection 

```

**Use Case**: Mark multiple subjects at once
```
Example: Mark all control subjects as Pass
 1. Filter: Diagnosis = Control
 2. Check "Select all"
 3. Click "Mark as Pass"
 4. Confirm: "Mark 45 subjects as Pass?"
 5. OK Done! All 45 controls marked as Pass
```

---

### Automated QC (Computer Checks)

Switch to **Automated QC** tab

#### Automated QC Overview

```
Automated QC Overview

Note: Automated checks detect technical issues: missing files, stub files, 
 small files, missing metadata


 Pass Warnings Fail Pending 

 450 125 35 50 
 68.2% 18.9% 5.3% 7.6% 

```

**Status Meanings**:
- **Pass**: All automated checks passed
- **Warnings**: Minor issues detected (small files, optional metadata missing)
- **Fail**: Critical issues (missing required files, corrupted data)
- **Pending**: Not yet checked

---

#### Run Automated Checks

```
Run Automated Checks

Run automated quality checks on all subjects to detect technical issues


 Run Automated QC 

```

**What Happens**:

Click "Run Automated QC":

```
Checking 660 subjects...
 45%
Checking 298/660: TBI011150

Auto-checks running:
OK File existence check
OK File size validation (>1KB for real data)
OK JSON sidecar presence
OK BIDS naming convention
OK Required metadata fields
```

**Duration**: ~2-5 minutes for 660 subjects

**Results**:
```
OK Automated QC Complete!

Results:
• 450 subjects passed all checks
• 125 subjects have warnings
• 35 subjects failed critical checks
• 50 subjects pending (not enough data)


 View Detailed Report 

```

---

#### Automated QC Results

```
Detailed QC Report

Filter by: All issues ▼


 Subject Severity Issue 

 TBI001 X Fail Missing T1w scan (2WK session) 
 TBI005 WARNING: Warn T1w file size only 850 bytes 
 TBI012 WARNING: Warn JSON sidecar missing for T2w 
 TBI023 X Fail Invalid BIDS filename: T1.nii.gz 
 TBI034 WARNING: Warn Metadata field 'EchoTime' missing
 ... ... ... 


 Export QC Report (CSV) 

```

**Export Options**:
- **CSV**: Spreadsheet of all QC results
- **JSON**: Machine-readable format
- **PDF**: Human-readable report (future)

---

## Managing Multiple Datasets

### Manage Datasets Page

Navigate to: Sidebar -> **Manage Datasets**

This page lets you:
- View all connected datasets
- Add new datasets (cloud or local)
- Browse platform datasets before adding
- Update credentials
- Deactivate/reactivate datasets
- Delete datasets

---

### View Connected Datasets

```


Manage Datasets

Your Datasets (3 active)


 [Pennsieve] TrackTBI 
 Status: OK Active | Subjects: 660 | Platform: Pennsieve 
 External ID: TrackTBI | Added: 2024-12-15 
  
 Update Creds Deactivate Sync Delete 
  


 [OpenNeuro] ds003974 
 Status: OK Active | Subjects: 120 | Platform: OpenNeuro 
 External ID: ds003974 | Added: 2025-01-20 
  
 Update Creds Deactivate Sync Delete 
  


 [Local] My_Study 
 Status: OK Active | Subjects: 50 | Platform: Pennsieve 
 Path: /data/my-study/ | Added: 2026-02-01 
  
 — Deactivate Re-index Delete 
  

```

**Dataset Actions**:

**Update Creds** (cloud datasets only):
- Update API keys/secrets without re-adding dataset
- Useful when credentials expire

**Deactivate**:
- Temporarily hides dataset from browsing
- Data remains in database
- Can reactivate anytime
- Use case: Focus on specific datasets without deleting others

**Sync** (cloud) / **Re-index** (local):
- Cloud: Fetch latest subjects/scans from platform
- Local: Re-scan local directory for changes
- Updates database with new subjects

**Delete**:
- Permanently removes dataset from BIDSHub
- Downloaded files are NOT deleted (safe)
- Confirmation required: "Delete TrackTBI and all its subjects?"

---

### Add New Dataset

Scroll down to:

```


Add New Dataset

Platform Selection

Choose platform:

 Pennsieve - Private research datasets 

```

**Two ways to add**:

1. **Browse First** (recommended) - Browse platform, then select
2. **Direct Add** - Enter details manually

---

#### Method 1: Browse Platform Datasets First

**Step 1: Expand Browser**

```
▼ Browse Platform Datasets

Preview available datasets before adding them to BIDSHub

Platform already selected above: OpenNeuro
```

**Step 2: Enter Browse Credentials** (if needed)

For public platforms (OpenNeuro):
```
API Token (optional): [leave blank]
```

For private platforms (Pennsieve):
```
Pennsieve API Key Pennsieve API Secret
****************** ********************
```

**Step 3: Browse**

```

 [Search] Browse Available Datasets 


Click to fetch dataset list from platform
```

**Loading**:
```
[Search] Browsing OpenNeuro datasets...
Please wait, this may take a few moments...
```

**Results**:
```
OK Found 1247 datasets on OpenNeuro


 ds003974
BOLD response to motion in area V5/MT
• Subjects: 120
• Modified: 2024-08-15
• Size: 15 GB

 Select <- Click this


 ds000246
OpenPain: A multi-center fMRI study of pain processing
• Subjects: 124
• Modified: 2023-11-20
• Size: 42 GB

 Select 


... (more datasets)
```

**Step 4: Select Dataset**

Click **[Select]** on your chosen dataset:

```
OK Selected: ds003974
 Dataset information saved for auto-fill
```

**Step 5: Form Auto-Fills**

Scroll down to the "Add Dataset" form - it's now pre-filled!

```
Dataset Name: ds003974 <- Auto-filled
Dataset ID: ds003974 <- Auto-filled
API credentials: (if you entered them) <- Auto-filled
```

**Step 6: Adjust and Add**

- Optionally change dataset name: `Motion_Response_Study`
- Review working directory path
- Click "+ Add Dataset"

---

#### Method 2: Direct Add (Manual Entry)

**Step 1: Fill Form Manually**

```
 Add Dataset Form 
                                                     
 Dataset Name 
 
 Epilepsy_2024 
 
                                                     
  
 Data Location 
                                                     
 Where is this dataset? 
 - Cloud (browse and download from platform) 
 ○ Local (BIDS dataset already on my disk) 
                                                     
 Note: Dataset will be browsed/downloaded from cloud 
                                                     
  
 Platform Credentials 
                                                     
 Pennsieve Dataset ID 
 
 TRACK_Epilepsy 
 
                                                     
 
 API Key API Secret 
 ****************** ****************** 
 
                                                     
  
 Local Working Directory 
 
 /Users/you/data-explorer/datasets/Epilepsy_2024 
 
                                                     
  
 [ ] Validate BIDS compliance 
                                                     
 
 + Add Dataset 
 

```

**Step 2: Submit**

Click "+ Add Dataset":

**Validation** (happens automatically):
```
Validating inputs...
OK Dataset name provided
OK Platform credentials valid
OK External ID provided
OK Working directory valid
```

**Success**:
```
OK Dataset 'Epilepsy_2024' added successfully!
Note: Navigate to 'Subjects' page and click 'Sync' to fetch subject list
```

**What's Next**:
- Dataset is added to database
- Cloud datasets: Go to Subjects page -> Click "Sync" to fetch subjects
- Local datasets: Subjects are indexed automatically

---

### Adding Local Datasets in Detail

**Scenario**: Add a local BIDS dataset from your disk

#### Step-by-Step: Add Local Dataset

**Platform**: Select any (platform is just for tracking)

**Where is this dataset?**:
```
○ Cloud (browse and download from platform)
- Local (BIDS dataset already on my disk) <- Select this!
```

**Info Box Appears**:
```
Note: Point to an existing BIDS dataset on your local machine. 
 No cloud credentials needed.
```

**BIDS Directory Path**:
```
BIDS Directory Path

 /data/my-study/ 

```

**Real-Time Validation**:

As you type the path, validation runs:

```
OK Directory found: /data/my-study/
OK dataset_description.json found
OK participants.tsv found
```

Or if issues:
```
ERROR Directory not found: /data/my-study/
WARNING: dataset_description.json not found (required by BIDS)
WARNING: participants.tsv not found (recommended)
```

**For Local Mode, Credentials Section Shows**:
```

Platform Credentials

Required for cloud datasets. Optional for local datasets 
(unless you want sync features).

[All credential fields optional for local mode]
```

**Validation Option**:
```

[X] Validate BIDS compliance
```

Recommended for local datasets - checks structure

**Submit**:
```

 + Add Dataset 

```

**Processing** (automatic):
```
Validating BIDS structure...
OK BIDS validation passed!

Indexing local BIDS dataset...
- 75%

Parsing: sub-045
```

**Success**:
```
OK Dataset 'My_Study' added successfully!
OK Indexed 50 subjects from local dataset
Note: Navigate to 'Subjects' page to browse your local data
```

**Immediate Benefits**:
- All subjects indexed automatically
- No "Sync" needed (unlike cloud datasets)
- Files marked as downloaded (already local)
- Ready to browse immediately

---

## Advanced Workflows

### Workflow 1: Cross-Dataset Cohort Building

**Goal**: Create a cohort with subjects from multiple datasets

**Scenario**:
- Dataset A (Pennsieve): 200 TBI subjects
- Dataset B (OpenNeuro): 100 control subjects
- Dataset C (Local): 50 pilot subjects
- **Cohort Goal**: Ages 25-45, has T1w and fMRI

**Steps**:

1. **Navigate**: Subjects page

2. **Select Datasets**:
 ```
 Show subjects from:
 [X] [Pennsieve] TrackTBI
 [X] [OpenNeuro] ds003974
 [X] [Local] Pilot_Study
   
 Total: 350 subjects
 ```

3. **Apply Filters**:
 ```
 [Advanced filters - if available via metadata filter]
 Age: 25-45
 Has T1w: Yes
 Has fMRI: Yes
 ```

4. **Review Results**:
 ```
 Showing 120 of 350 subjects
   
 Distribution:
 • 65 from TrackTBI
 • 42 from ds003974
 • 13 from Pilot_Study
 ```

5. **Export Cohort**:
 ```
 Click: "Export Filtered List"
   
 Saves: cohort_2026-02-05.csv
   
 Contents:
 subject_id,dataset,age,sex,has_T1w,has_fmri
 TBI011007,TrackTBI,34,M,yes,yes
 sub-025,ds003974,28,F,yes,yes
 pilot-003,Pilot_Study,42,M,yes,yes
 ...
 ```

6. **Use Cohort**:
 - Import CSV into your analysis pipeline
 - Use for statistical analysis
 - Share with collaborators

---

### Workflow 2: Selective Download Strategy

**Goal**: Download only what you need (limited disk space)

**Scenario**: 
- Dataset has 660 subjects, 12 scans each = ~100 GB total
- You only have 20 GB free space
- You only need T1w and T2w from 2WK session

**Steps**:

1. **Navigate**: Downloads page

2. **Filter by Metadata**:
 ```
 Age: 18-60
 Diagnosis: Moderate TBI, Severe TBI
 ```

3. **Preview**:
 ```
 Click: "Preview Filtered Results"
 OK 150 subjects match
 ```

4. **Select Modalities**:
 ```
 Which modalities?
 [X] T1w (12 MB each)
 [X] T2w (11 MB each)
 [ ] FLAIR
 [ ] rest (fMRI) <- Skip (120 MB each!)
 [ ] dwi <- Skip (240 MB each!)
 ```

5. **Select Sessions**:
 ```
 Which sessions?
 [X] 2WK <- Only 2-week timepoint
 [ ] 6MO <- Skip 6-month
 ```

6. **Calculate**:
 ```
 Estimated download:
 150 subjects × 1 session × 2 modalities × ~12 MB
 = 3.6 GB (fits in your 20 GB space!)
 ```

7. **Queue and Download**:
 ```
 Add Filtered to Queue -> OK 300 scans added (3.6 GB)
 Start Queue -> Download completes in ~10 minutes
 ```

8. **Result**: 
 - Downloaded only what you need
 - Saved 96.4 GB of disk space
 - Can always download more later if needed

---

### Workflow 3: QC-Driven Download

**Goal**: Only download subjects that pass QC review

**Strategy**: Review metadata and scans before downloading large files

**Steps**:

1. **Browse Subjects** (cloud-only mode):
 - All subjects visible (metadata loaded)
 - Scans show as "not downloaded" (stub files)

2. **Review Metadata**:
 ```
 Subjects page -> Review participants.tsv data
 • Age, sex, diagnosis, etc.
 • Available without downloading scans
 ```

3. **Quick Visual QC** (small files):
 - Download only T1w scans first (~12 MB each)
 - Review in MRI Viewer
 - Mark subjects as Pass/Fail

4. **Identify Good Subjects**:
 ```
 QC Status filter: Pass
 Result: 450 subjects passed preliminary QC
 ```

5. **Download Full Data** (only for Pass subjects):
 ```
 Downloads page -> Add Pass subjects to queue
 Select modalities: All (T1w, T2w, FLAIR, fMRI, DWI)
   
 Result: Download 450 subjects (not 660)
 Saved: 15 GB disk space (skipped 210 failed subjects)
 ```

**Benefits**:
- Don't waste bandwidth on poor-quality data
- Save disk space
- Faster pipeline processing (no failed subjects)

---

### Workflow 4: Multi-Platform Dataset Comparison

**Goal**: Compare same subjects across platforms

**Scenario**:
- TrackTBI data on Pennsieve (private, with demographics)
- Same subjects uploaded to institutional XNAT (different processing)

**Setup**:
```
Dataset 1: [Pennsieve] TrackTBI_Original
Dataset 2: [XNAT] TrackTBI_Reprocessed

Both have same subject IDs
```

**Workflow**:

1. **Add Both Datasets** to BIDSHub

2. **Browse Side-by-Side**:
 ```
 Subjects page -> Select both datasets
   
 Subject TBI011007 appears twice:
 Row 1: TBI011007 | TrackTBI_Original | ...
 Row 2: TBI011007 | TrackTBI_Reprocessed| ...
 ```

3. **Compare**:
 - View details for each version
 - Check scan parameters (JSON sidecars)
 - Download both versions if needed
 - Track QC separately

4. **Analysis**:
 - Export both versions
 - Compare processing outputs
 - Identify pipeline differences

---

## Troubleshooting

### Connection Issues

#### Problem: "Failed to connect to Pennsieve"

**Possible Causes**:
1. Invalid credentials
2. No internet connection
3. Pennsieve service down

**Solutions**:

**Check credentials**:
```
1. Go to Pennsieve web app
2. Settings -> API Keys
3. Verify key and secret match what you entered
4. Generate new keys if needed
```

**Test connection**:
```bash
# Test outside BIDSHub
pip install pennsieve2
python
>>> from pennsieve import Pennsieve
>>> ps = Pennsieve(api_token='your-key', api_secret='your-secret')
>>> ps.datasets()
```

**Check internet**:
```bash
ping pennsieve.io
# Should show successful ping responses
```

---

#### Problem: "OpenNeuro dataset not found"

**Cause**: Invalid dataset ID

**Solutions**:

**Verify dataset ID**:
1. Go to https://openneuro.org
2. Find your dataset
3. URL shows ID: `openneuro.org/datasets/ds003974`
4. ID is: `ds003974`
5. Enter exactly this in BIDSHub (case-sensitive)

**Common mistakes**:
- Wrong: `DS003974` (uppercase)
- Wrong: `3974` (missing ds prefix)
- Right: `ds003974`

---

#### Problem: "XNAT authentication failed"

**Possible Causes**:
1. Wrong server URL
2. Incorrect username/password
3. Project ID doesn't exist or no access

**Solutions**:

**Verify server URL**:
```
Common formats:
OK https://xnat.uni.edu
OK https://central.xnat.org
OK http://xnat-server:8080

Common mistakes:
X xnat.uni.edu (missing https://)
X https://xnat.uni.edu/ (trailing slash may cause issues)
```

**Test credentials**:
```python
# Test XNAT connection
pip install xnat
python
>>> import xnat
>>> session = xnat.connect('https://xnat.uni.edu', user='username', password='password')
>>> session.projects # Should list projects
```

**Check project access**:
- Verify you have permissions for the project
- Contact XNAT administrator if access denied

---

### Browsing Issues

#### Problem: "No subjects found"

**For cloud datasets**:

**Cause**: Dataset not synced yet

**Solution**:
```
1. Subjects page (top right corner)
2. Look for "Sync" button or message
3. Click "Sync Datasets"
4. Wait for sync to complete
5. Subjects appear
```

**For local datasets**:

**Cause**: Invalid BIDS structure

**Check**:
```bash
# Verify BIDS structure
cd /path/to/dataset/
ls

Required:
OK dataset_description.json
OK participants.tsv
OK sub-001/ (at least one subject)

# Check subject folders
ls -d sub-*/
# Should show: sub-001/ sub-002/ ...
```

**Solution**: Fix BIDS structure, then Re-index:
```
Manage Datasets -> Find dataset -> Click "Re-index"
```

---

#### Problem: Subjects table is empty after filtering

**Cause**: Too restrictive filters

**Solution**:
```
1. Clear one filter at a time
2. Start broad, narrow down gradually

Example:
- Remove search query
- Set QC status to "All"
- Set session to "All"
- Click "Apply Filters"
- Subjects should reappear
```

---

### Viewer Issues

#### Problem: "Image file not found"

**For cloud datasets**:

**Cause**: File not downloaded yet (stub file)

**Solution**:
```
1. Note the file path from error
2. Navigate to: Subjects page -> Find subject
3. Click: v Queue next to the scan
4. Navigate to: Downloads page
5. Click: > Start Queue
6. Wait for download
7. Return to subject -> Click [View] View again
8. Image loads successfully
```

**For local datasets**:

**Cause**: File moved or deleted

**Solution**:
```bash
# Check if file exists
ls /path/from/error/message

# If dataset was moved:
1. Manage Datasets -> Remove dataset
2. Add dataset again with correct path
3. Re-index will find files
```

---

#### Problem: "Stub file detected" warning

**Message shown**:
```
WARNING: Stub File Detected

This file appears to be a metadata stub without actual image data.
To view this image, please download it first using the Download Manager.
```

**Explanation**:
- Cloud-only mode creates "stub files" (small placeholder files)
- Stub has metadata (JSON) but no actual image data
- File size: <1 KB (real images are 10+ MB)

**Solution**:
```
1. Click "Go to Download Manager" (in warning box)
2. Or navigate manually to Downloads page
3. Queue the scan for download
4. Start download
5. Wait for completion
6. Return to viewer -> Image loads
```

---

#### Problem: Viewer is slow or unresponsive

**Possible Causes**:

**Large 4D file** (fMRI with 200+ volumes):
```
Loading image...
[Progress bar] - 65%
Taking longer than usual...
```

**Solution**: Wait (4D files take 10-30 seconds to load)

**Network storage with high latency**:
- Local datasets on NAS may be slow
- Copy to local SSD for better performance

**Low memory**:
- Very large images (>2 GB) may struggle
- Close other applications
- Restart BIDSHub

---

### Download Issues

#### Problem: Downloads fail repeatedly

**Error shown**:
```
X Failed: TBI011007_T1w.nii.gz
 Error: Connection timeout
  
Auto-retry: Attempt 3 of 3 failed
```

**Solutions**:

**Check internet**:
```bash
# Test download speed
speedtest-cli

# Should have: >5 Mbps download speed
```

**Check disk space**:
```bash
# Mac/Linux
df -h /path/to/download/directory

# Should show: Sufficient free space
```

**Retry manually**:
```
1. Clear failed items from queue
2. Re-queue them
3. Start queue again
4. If still fails: Check platform status
```

**Check platform status**:
- Pennsieve: Check status.pennsieve.io
- OpenNeuro: Check openneuro.org (website loading?)
- XNAT: Contact your institution's IT

---

#### Problem: "Insufficient disk space" error

**Message**:
```
ERROR Cannot download: Insufficient disk space

Required: 15 GB
Available: 8 GB
```

**Solutions**:

**Free up space**:
```bash
# Check current usage
df -h

# Delete unnecessary files
# Empty trash
# Move old datasets to external drive
```

**Download to different location**:
```
1. Manage Datasets -> Find dataset -> Update Creds
2. Change "Local Working Directory" to drive with more space
3. Re-sync dataset
4. Downloads go to new location
```

**Download selectively**:
```
1. Downloads page -> Use metadata filters
2. Download fewer subjects or modalities
3. Download in batches (50 subjects at a time)
```

---

### Performance Issues

#### Problem: Slow browsing with many datasets

**Symptom**: Subjects table takes 5+ seconds to load

**Cause**: Too many datasets selected (10+)

**Solutions**:

**Deselect unused datasets**:
```
Dataset Filter
[ ] [Pennsieve] Old_Study_2020 <- Uncheck unused datasets
[ ] [OpenNeuro] Test_Dataset
[X] [Local] Current_Project <- Keep only current work
```

**Or deactivate temporarily**:
```
Manage Datasets -> Find dataset -> Click "Deactivate"
-> Dataset hidden from all views
-> Can reactivate later
```

---

#### Problem: Viewer takes long to load

**Cause**: Large file or network storage

**Solutions**:

**For large 4D files** (fMRI):
- Wait patiently (may take 30-60 seconds)
- Consider downsampling files if viewing only

**For network storage**:
```bash
# Copy to local disk first
cp /mnt/nas/dataset/sub-001/...T1w.nii.gz /tmp/
# Then view from /tmp/ (much faster)
```

**For compressed files**:
- BIDSHub handles .nii.gz natively
- No need to decompress manually

---

## Tips and Best Practices

### General Tips

**1. Start with One Dataset**
- Get familiar with BIDSHub using one dataset first
- Add more datasets as you learn the interface
- Avoid information overload

**2. Use Dataset Naming Conventions**
```
Good names:
OK TrackTBI_Main
OK Epilepsy_Study_2024
OK Control_Subjects_Batch1

Avoid:
X Dataset1 (not descriptive)
X test (confusing)
X NEW (not informative)
```

**3. Document Your Datasets**
- Use QC notes to track dataset-specific information
- Keep external documentation (README files)
- Note any known issues or anomalies

---

### Browsing Tips

**1. Use Search for Known IDs**
```
If you know subject ID: Type directly in search
-> Faster than scrolling through 660 subjects
```

**2. Combine Filters for Precision**
```
Powerful combinations:
• QC Status: Pending + Session: both
 -> Find subjects needing review with complete data
  
• Search: "TBI011" + QC Status: Fail
 -> Find specific subjects that failed QC
```

**3. Export Early, Export Often**
```
Working on a cohort?
-> Export subject list immediately
-> Save as CSV for your records
-> Re-import for analysis pipelines
```

---

### Download Tips

**1. Download Anatomical Scans First**
```
T1w, T2w, FLAIR: Small files (10-15 MB each)
-> Download these first
-> Run QC immediately
-> Decide if subject is worth downloading functional/diffusion data
```

**2. Batch Downloads Overnight**
```
Large downloads (500+ subjects, 50+ GB):
-> Queue in evening
-> Start downloads
-> Let run overnight
-> Check completion in morning
```

**3. Use Metadata Filters Aggressively**
```
Don't download everything blindly:
-> Filter by age, sex, diagnosis first
-> Preview results
-> Download only matching subjects
-> Saves bandwidth, time, storage
```

**4. Monitor Queue Regularly**
```
First few downloads:
-> Watch for errors
-> Ensure files download correctly
-> Check file sizes (should be >1 MB for real scans)
-> Verify BIDS structure
```

---

### QC Tips

**1. Use Both Manual and Automated QC**
```
Workflow:
1. Run Automated QC first
 -> Catches technical issues (missing files, stubs)
   
2. Filter to Automated Pass subjects
 -> Focus manual QC on subjects with valid data
   
3. Manual QC on passed subjects
 -> Check image quality, artifacts, protocol compliance
```

**2. QC Notes Are Your Friend**
```
Good QC notes:
OK "Motion artifact in T1w, moderate impact"
OK "Incomplete FOV, missing cerebellum"
OK "Excellent quality, all sequences"
OK "Ghost artifacts in T2w, likely patient movement"

Bad QC notes:
X "bad" (not descriptive)
X "?" (unclear)
X "" (empty - add context!)
```

**3. Use QC Status Strategically**
```
Pending: Default, not reviewed yet
Pass: Good quality, ready for analysis
Needs Review: Uncertain, ask colleague or re-review later
Fail: Poor quality, exclude from analysis
```

**4. Bulk Operations for Efficiency**
```
Example: 50 control subjects, all expected to be good
-> Review 2-3 samples manually
-> If consistent quality, bulk mark as Pass
-> Saves time for large cohorts
```

---

### Viewer Tips

**1. Learn Keyboard Shortcuts**
```
Faster navigation:
↑↓ arrows: Scroll through slices
Home/End: Jump to first/last slice
Tab: Switch view planes
```

**2. Use Views Strategically**
```
Quick QC workflow:
1. Axial view -> Check for motion, coverage
2. Sagittal view -> Check midline, protocol
3. Coronal view -> Check hippocampus, temporal lobes

Takes 30 seconds per subject
```

**3. Colormap for Purpose**
```
Grayscale (gray): Standard QC, anatomical review
Viridis/Plasma: Functional data, activation maps
Hot: Statistical maps, thresholded images
```

---

## Summary Cheat Sheet

### Quick Navigation

```
Launch: ./hub start -> http://localhost:8501

First Time: Home -> Setup -> Configure first dataset

Add Dataset: Manage Datasets -> Add New Dataset
 -> Choose local or cloud mode

Browse: Subjects -> Filter -> View Details

View MRI: Subject Details -> Click [View] on scan

Download: Downloads -> Filter -> Queue -> Start

QC: Quality Control -> Manual/Automated tabs
```

### Platform Connection Quick Reference

| Platform | Required Credentials | Optional | ID Format |
|----------|---------------------|----------|-----------|
| Pennsieve | API Key, Secret | — | Dataset name |
| OpenNeuro | — | API token | `ds000246` |
| XNAT | Server URL, Username, Password | — | Project ID |
| DANDI | — | API token | 6-digit dandiset |
| HCP | AWS Access Key, Secret Key | — | `HCP_1200` |
| LORIS | Server URL, Username, Password | — | Project name |
| FITBIR | NIH Username, Password | Approval checkbox | Study ID |

### Common Tasks

**Add cloud dataset & sync subjects**:
```
Manage Datasets -> Add New
-> Select platform (OpenNeuro, DANDI, etc.)
-> Enter credentials and dataset ID
-> Add Dataset
Subjects -> Select dataset -> Sync Subjects
-> Wait 30-60s -> Refresh (F5)
OK Subjects synced with metadata
```

**Add local dataset**:
```
Manage Datasets -> Add New
-> Select "Local" mode
-> Enter BIDS path
-> Skip credentials
-> Add Dataset
OK Indexed immediately
```

**Filter subjects by metadata**:
```
Subjects -> Expand "Advanced Metadata Filters"
-> Set age range, sex, diagnosis, modalities
-> Filters apply automatically
-> View filtered results in table
-> Export Filtered List (CSV)
```

**Browse multiple datasets**:
```
Subjects -> Select datasets in multiselect
-> All subjects shown together
-> Filter/search across all
```

**Download specific subjects**:
```
Subjects -> Find subjects
-> View Details -> Queue scans
Downloads -> Start Queue
```

**Run QC**:
```
Quality Control -> Automated QC tab
-> Run Automated QC (technical checks)
-> Manual QC tab
-> Review subjects individually
-> Mark Pass/Fail/Needs Review
```

**View MRI**:
```
Subjects -> View Details
-> Click [View] next to scan
Viewer -> Use slider to scroll
-> Switch tabs for different planes
```

---

## Performance & Scalability

BIDSHub is optimized for large-scale neuroimaging datasets with hundreds to thousands of subjects.

### Performance Features (v3.1.1+)

**Pagination**:
- Subject lists paginated at 50 subjects per page (adjustable: 25/50/100/200)
- Reduces initial load time from 5+ seconds to <1 second
- Navigate pages with Previous/Next or jump to specific page

**Metadata Caching**:
- Frequently accessed data cached in memory (5-minute TTL)
- Reduces database queries by 60-80% during browsing
- Automatic cache invalidation on data changes

**Batch Processing**:
- Downloads processed in optimized batches (10 subjects at a time)
- 30-40% throughput improvement over sequential downloads
- Intelligent queue management for large cohorts

**SSH Connection Pooling** (HPC/Remote Server):
- Persistent SSH connections reduce overhead by 50%
- Automatic reconnection on timeout
- Graceful cleanup on shutdown

### Scalability Benchmarks

**Tested Configurations**:

Small Dataset (50-100 subjects):
- Load time: <1 second
- Browse: Instant
- Sync: 10-20 seconds

Medium Dataset (200-500 subjects):
- Load time: 1-2 seconds
- Browse with filters: <1 second
- Sync: 30-60 seconds
- Download (T1w only): 15-30 minutes

Large Dataset (1000+ subjects):
- Load time: 2-3 seconds (with pagination)
- Browse with filters: 1-2 seconds
- Sync: 2-5 minutes
- Download (T1w only): 1-2 hours

Multi-Dataset (5-10 datasets, 2000+ subjects total):
- Load time: 3-5 seconds
- Cross-dataset search: <2 seconds
- Recommended: Use dataset filter to focus on 1-3 at a time

### Performance Tips

**For Large Datasets**:
```
1. Use pagination controls (25 per page for fastest loading)
2. Apply filters early (reduces result set size)
3. Deactivate unused datasets (Manage Datasets -> Deactivate)
4. Use search for known subject IDs (instant results)
```

**For Slow Connections**:
```
1. Enable batch downloads (default on, 10 subjects/batch)
2. Download overnight for large cohorts (50+ GB)
3. Start with T1w only (smallest files, ~12 MB each)
4. Use metadata filters to reduce download size
```

**For Multi-Dataset Workflows**:
```
1. Select only 2-3 datasets at a time in subject browser
2. Use cache manager (automatically enabled)
3. Run database maintenance weekly (Manage Datasets -> Database Maintenance)
4. Export filtered lists for offline analysis
```

### Resource Usage

**Memory**:
- Baseline: 100-200 MB
- With 50 subjects loaded: 200-300 MB
- With 1000 subjects (paginated): 300-500 MB
- Viewer active: +200-500 MB per image

**Disk Space**:
- Database: 10-50 MB per 1000 subjects
- Downloaded data: 150-300 MB per subject (full scans)
- Cache: Negligible (<1 MB)

**Network**:
- Sync (metadata only): 1-5 MB per 100 subjects
- Download (per subject): 150-300 MB (all modalities)
- Download (T1w only): 12-15 MB per subject

### Database Maintenance

For optimal performance with large datasets:

```
Manage Datasets -> Database Maintenance
-> Check Integrity (diagnose issues)
-> Run Maintenance (fix orphaned records, duplicates)

Recommended frequency:
- Light use (1-2 datasets): Monthly
- Heavy use (5+ datasets): Weekly
- After bulk operations: Immediately
```

**Maintenance Operations**:
- Remove duplicate subjects (preserves latest)
- Clean orphaned scans/sessions
- Fix download state mismatches
- Verify QC consistency

---

## Support and Resources

### Documentation

- **USER_GUIDE.md** - This complete user guide
- **TROUBLESHOOTING.md** - Common issues and solutions
- **README.md** - Quick start and installation

### Getting Help

**Check Documentation First**:
1. Read relevant guide for your use case
2. Check troubleshooting sections
3. Review examples

**Platform-Specific Issues**:
- Pennsieve: Contact your institution's Pennsieve admin
- XNAT: Contact your XNAT server administrator
- OpenNeuro: Check openneuro.org for status
- HCP: Review ConnectomeDB credentials

**BIDS Validation**:
```bash
# Use official BIDS validator
pip install bids-validator
bids-validator /path/to/dataset/

# Shows detailed errors and warnings
```

### Command Line Reference

```bash
# Launch BIDSHub
./hub start

# Check status
./hub status

# Stop BIDSHub
./hub stop

# Restart (after code changes)
./hub restart

# View logs
tail -f ~/data-explorer/logs/app.log
```

---

## Appendix: UI Component Reference

### Status Badges

Throughout BIDSHub, you'll see color-coded status badges:

**QC Status**:
- **- Pending** - Gray - Not reviewed
- **OK Pass** - Green - Passed QC
- **WARNING: Needs Review** - Yellow - Flagged
- **X Fail** - Red - Failed QC

**Download Status**:
- **OK Downloaded** - Green - File available locally
- **X Not Downloaded** - Gray - Stub file only
- **v Downloading** - Blue - In progress
- **X Failed** - Red - Download error

**Dataset Status**:
- **OK Active** - Green - Currently active
- **|| Inactive** - Gray - Deactivated
- **[Sync] Syncing** - Blue - Updating from platform

### Icons Reference

**Action Icons**:
- **[View]** - View (subject details or MRI scan)
- **v** - Download / Queue for download
- **** - Delete / Remove from queue
- **** - Edit
- **[Sync]** - Sync / Refresh / Reload
- **** - View files / Open folder
- **** - Dataset / Data icon
- **[Settings]** - Settings / Configure

**Navigation Icons**:
- **>** - Start / Next / Go
- **||** - Pause
- **[]** - Stop
- **[Reload]** - Reload / Refresh
- **<-** - Back / Previous

**Status Icons**:
- **OK** - Success / Complete / Yes
- **X** - Error / Fail / No
- **WARNING:** - Warning / Attention
- **Note:** - Information
- **-** - Status indicator

---

## Glossary

**BIDS** - Brain Imaging Data Structure, standardized format for neuroimaging data

**Subject** - Individual participant in a study (e.g., `sub-001`, `TBI011007`)

**Session** - Timepoint or visit (e.g., `ses-01`, `2WK`, `6MO`)

**Modality** - Type of scan (e.g., `anat` for anatomical, `func` for functional MRI)

**Suffix** - Specific scan type (e.g., `T1w`, `T2w`, `FLAIR`, `bold`)

**Stub File** - Small placeholder file with metadata but no actual image data (cloud-only mode)

**Cloud-Only Mode** - Browse datasets remotely, download files on-demand

**Local Mode** - Work with BIDS dataset already on your local disk

**QC** - Quality Control, process of reviewing data quality

**NIfTI** - Neuroimaging Informatics Technology Initiative, standard image format (`.nii` or `.nii.gz`)

**Sidecar JSON** - JSON file with scan metadata (parameters, acquisition details)

**participants.tsv** - Tab-separated file with subject demographics (age, sex, etc.)

**PyBIDS** - Python library for working with BIDS datasets

**Dataset Root** - Top-level directory of a BIDS dataset (contains `dataset_description.json`)

---

**End of User Guide**

For troubleshooting, see: `TROUBLESHOOTING.md`
