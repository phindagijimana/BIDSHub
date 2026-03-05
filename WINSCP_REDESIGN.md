# Data Transfer Page - WinSCP-Style Redesign

**Date:** February 5, 2026  
**Version:** 3.1.1+  
**Commits:** ae151df, 081e12d

## Overview

Redesigned the Data Transfer page with a WinSCP-inspired dual-pane interface for intuitive bidirectional data transfers between platforms.

## New Interface Layout

### 1. Connection Settings (Collapsible)

**Location:** Top of page  
**State:** Collapsed by default  
**Purpose:** Configure platform connections without cluttering main interface

**Features:**
- Shows connection status for source and destination
- Links to Manage Datasets for editing credentials
- Dual-column layout (source left, destination right)
- Only expands when user needs connection details

### 2. File Browser (Dual-Pane Layout)

**Layout:** WinSCP-style three-column design

```
|  SOURCE PLATFORM  |  ARROWS  |  DESTINATION PLATFORM  |
|      (Left)       |  (→ ←)   |        (Right)         |
|    Dropd own      |          |      Dropdown          |
|    Platform badge |          |   Platform badge       |
|    Subject list   |          |   Subject list         |
|   (Checkboxes)    |          |   (View only)          |
```

**Left Pane - Source:**
- Platform/dataset dropdown selector
- Platform badge showing type and subject count
- File browser with checkboxes for selection
- Subject list with scan counts
- Tree-view style display

**Middle - Transfer Controls:**
- `→` button: Transfer from source to destination (primary action)
- `←` button: Transfer from destination to source (bidirectional)
- Centered between panes
- Clear visual transfer direction

**Right Pane - Destination:**
- Platform/dataset dropdown selector
- Platform badge showing type and subject count
- Read-only view of current subjects
- Shows what will be on destination after transfer
- No selection checkboxes (destination is target)

### 3. Transfer Options (Collapsible)

**Location:** Below file browser  
**State:** Expanded by default  
**Purpose:** Configure transfer behavior

**Options:**
- **Transfer Mode:**
  - Direct Stream (platform-to-platform)
  - Via Local Cache (download first, then upload)
  
- **Preserve BIDS Structure:** Checkbox (default: ON)
  - Maintains subject/session/modality folder structure
  
- **Verify Integrity:** Checkbox (default: ON)
  - Validates checksums after transfer

### 4. Transfer Summary

**Location:** Below options (appears when subjects selected)  
**Purpose:** Show transfer details before execution

**Displays:**
- Number of subjects
- Total scans
- Estimated data size
- Transfer mode
- Transfer route (source → destination)

**Action:** "Start Transfer" button (primary color, full width)

### 5. Recent Transfers

**Location:** Bottom of page  
**Purpose:** Show transfer history

**Displays:**
- Date, source, destination, subject count, status
- Last 10 transfers
- Success/failure indicators

## Key Features

### WinSCP-Style Elements

1. **Dual-Pane Layout**
   - Visual separation between source and destination
   - Easy to understand data flow
   - Familiar to users of file transfer tools

2. **Transfer Direction Controls**
   - Arrow buttons make direction explicit
   - Supports bidirectional transfers
   - Intuitive visual metaphor

3. **File Browser Interface**
   - Tree-view style subject display
   - Checkbox-based selection
   - Folder icons (📁, 📂)
   - Shows item counts

4. **Collapsible Sections**
   - Connection Settings: collapsed by default (clean interface)
   - Transfer Options: expanded by default (users need to see)
   - Reduces visual clutter

### UX Improvements

**Before:**
- Linear form layout (top to bottom)
- All options always visible
- No visual representation of transfer direction
- Connection details mixed with transfer controls

**After:**
- Side-by-side comparison of source/destination
- Clear transfer direction with arrow buttons
- Collapsible sections reduce clutter
- Connection details hidden until needed
- More compact and organized

## User Workflow

1. **Expand Connection Settings** (if needed)
   - Check/edit platform credentials
   - Verify connection status

2. **Select Source Platform**
   - Choose dataset from dropdown
   - View available subjects in left pane

3. **Select Subjects**
   - Check boxes next to subjects to transfer
   - See scan counts for each subject

4. **Select Destination Platform**
   - Choose target dataset from dropdown
   - View existing subjects in right pane

5. **Configure Options** (optional)
   - Expand/collapse Transfer Options
   - Choose transfer mode, integrity checks

6. **Review Summary**
   - Check subject count, scan count, size
   - Verify transfer route

7. **Execute Transfer**
   - Click "Start Transfer" button
   - Monitor progress (real-time updates)

## Technical Implementation

### Collapsible Sections

```python
with st.expander("Connection Settings", expanded=False):
    # Connection details here
    # Collapsed by default to keep UI clean
```

```python
with st.expander("Transfer Options", expanded=True):
    # Transfer mode, checkboxes
    # Expanded by default so users see options
```

### Dual-Pane Columns

```python
# Create three columns: left pane, arrows, right pane
col1, col_arrow, col2 = st.columns([10, 1, 10])

with col1:
    # Source file browser
    
with col_arrow:
    # Transfer direction buttons (→ ←)
    
with col2:
    # Destination file browser
```

### File Browser Display

```python
# Tree-view style with checkboxes
for subject in subjects:
    if st.checkbox(f"📂 {subject['id']} ({scan_count} scans)"):
        selected.append(subject['id'])
```

## Benefits

### For Users

1. **Intuitive Interface**
   - Familiar dual-pane layout (like WinSCP, FileZilla)
   - Visual representation of transfer direction
   - Easy to understand source vs destination

2. **Reduced Clutter**
   - Connection details hidden until needed
   - Transfer options collapsible
   - Focus on main task (selecting and transferring)

3. **Better Space Utilization**
   - Side-by-side comparison
   - More efficient use of screen width
   - Easier to compare source and destination

4. **Clearer Actions**
   - Arrow buttons make direction explicit
   - Transfer button only appears when ready
   - Visual feedback at each step

### For Development

1. **Modular Design**
   - Collapsible sections easy to maintain
   - Clear separation of concerns
   - Expandable to add more options

2. **Consistent with Platform Standards**
   - Uses established file transfer UI patterns
   - Reduces learning curve
   - Professional appearance

## Comparison

### Traditional Form Layout (Old)
```
Source Dropdown      | Destination Dropdown
[Select Platform]    | [Select Platform]
                     |
Subject List         | 
[Multiselect]        |
                     |
Options              |
[Various checkboxes] |
                     |
[Transfer Button]    |
```

### WinSCP-Style Layout (New)
```
[Connection Settings]      (Collapsed)
=====================================

SOURCE              →  ←          DESTINATION
[Platform dropdown]              [Platform dropdown]
PENNSIEVE | 5 subj                XNAT | 3 subj
                    
📂 sub-001 (10 scans) []           📂 sub-010 (8 scans)
📂 sub-002 (12 scans) []           📂 sub-015 (10 scans)
📂 sub-003 (8 scans)  [✓]          📂 sub-020 (12 scans)

[Transfer Options]         (Expanded)
- Transfer Mode: Direct / Cached
- Preserve BIDS: [✓]
- Verify: [✓]

SUMMARY: 1 subject, 8 scans, 2.5 GB
SOURCE → DESTINATION

[Start Transfer]
```

## Screenshots

See attached screenshots:
- `data-transfer-page.png` - Full page with collapsed connections
- `data-transfer-with-connections.png` - With Connection Settings expanded

## Future Enhancements

1. **Drag-and-Drop** (requires custom JavaScript)
   - Drag subjects from left to right pane
   - Visual feedback during drag

2. **Search/Filter in Each Pane**
   - Quick search within source subjects
   - Filter by modality, session, etc.

3. **Preview Before Transfer**
   - Expandable file tree for each subject
   - Show individual scans that will transfer

4. **Batch Selection**
   - "Select All" / "Deselect All" buttons
   - Select by criteria (e.g., all T1w scans)

5. **Real-time Destination Preview**
   - Show what destination will look like after transfer
   - Detect potential conflicts/duplicates

## Conclusion

The new WinSCP-style interface provides a more intuitive, visual, and professional data transfer experience. The collapsible sections keep the interface clean while maintaining full functionality. Users familiar with file transfer tools will immediately understand the layout and workflow.
