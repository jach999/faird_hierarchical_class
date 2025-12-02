# 🐝 Insect Taxonomy Pipeline

Automated tools to standardize insect classification data and generate hierarchical visualization trees from Excel datasets.

## 📂 Project Structure

```
project_root/
├── ClassificationClasses_[version].csv  # Master taxonomy reference file
├── config.py                            # Configuration settings
├── faird_reclass.py                     # Data processing script
├── tree_scheme.py                       # Tree visualization script
├── environment.yaml                     # Conda environment specification
├── source_tables/                       # Input: Raw Excel files
├── reclass/                             # Output: Processed CSV files
└── scheme/                              # Output: Visualization diagrams
```

## 🧬 Master Taxonomy File

The `ClassificationClasses_[version].csv` file is the authoritative source for all classification rules. It defines:

- **Taxonomic mappings**: How biological taxonomy (e.g., *Syrphidae*) maps to your classification system (e.g., *hoverfly*)
- **Hierarchical structure**: The complete lineage from Class down to Family
- **Leaf definitions**: Which categories appear as terminal nodes (yellow) in the visualization

To modify classification rules, edit this CSV file. The scripts will automatically apply your changes.

## ⚙️ Installation

This project uses Conda to manage dependencies, particularly Graphviz for tree visualization.

1. Create the environment:
   ```bash
   conda env create -f environment.yaml
   ```

2. Activate the environment:
   ```bash
   conda activate reclass_env
   ```

## 🚀 Usage

### Configuration

Edit `config.py` to specify your master taxonomy file:

```python
MASTER_FILE = "ClassificationClasses_long.csv"
MASTER_LEAF_COL = "Leave"
```

The version suffix (e.g., `_long`) is automatically extracted and applied to all output files, allowing you to maintain multiple classification approaches simultaneously.

### Step 1: Process Raw Data

Place your Excel files in the `source_tables/` directory, then run:

```bash
python faird_reclass.py
```

**What it does:**
- Reads Excel files from `source_tables/`
- Applies taxonomic classification rules from the master file
- Handles manual assignments (if "Manual assignment" column exists)
- Generates cleaned CSV files in `reclass/` with the format: `filename_[version].csv`

**Interactive prompt:**
If unclassified rows are found (marked as `#N/C`), you'll be asked whether to remove them:
- `y`: Remove unclassified rows (recommended for production)
- `n`: Keep them for debugging

### Step 2: Generate Visualization

```bash
python tree_scheme.py
```

**What it does:**
- Reads processed CSV files from `reclass/` matching the current version
- Combines all data into a single hierarchical structure
- Generates a tree diagram highlighting true leaf categories (yellow) vs intermediate nodes (white)
- Saves the visualization as `taxonomy_tree_[version].png` in `scheme/`

## 📊 Working with Multiple Versions

The pipeline supports multiple classification strategies through version suffixes:

```
ClassificationClasses_detailed.csv  → outputs: *_detailed.csv, *_detailed.png
ClassificationClasses_simple.csv    → outputs: *_simple.csv, *_simple.png
ClassificationClasses_v2.csv        → outputs: *_v2.csv, *_v2.png
```

All versions coexist in the same `reclass/` and `scheme/` folders, making it easy to compare different approaches side-by-side.

**To switch between versions:**
1. Edit `config.py` to change `MASTER_FILE`
2. Re-run both scripts
3. New version files are created without overwriting existing ones

## 📋 Input Requirements

### Excel Files
- Must contain a sheet named "Monitoring" (or the default first sheet is used)
- Should include taxonomic columns matching your hierarchy (e.g., Family, Order, Class)
- May include a "Manual assignment" column for explicit classifications

### Master Classification File
- CSV format with columns for each taxonomic level
- Must include the leaf category column (specified in `config.py`)
- Defines the complete lineage for each classification category

## 📤 Output Files

### Processed CSVs (`reclass/`)
- Semicolon-separated files (`;`)
- UTF-8 encoding with BOM
- Includes original data plus:
  - `Classification class refined`: Final assigned category
  - `Parent folder 1-6`: Hierarchical lineage

### Tree Diagrams (`scheme/`)
- PNG format, high resolution
- Left-to-right layout (LR)
- Color coding:
  - Yellow: True leaf categories (from master file)
  - White: Intermediate taxonomic nodes
- Node labels include classification counts `(n=X)`

## 🔍 Classification Logic

The pipeline uses a three-tier classification strategy:

1. **Hierarchical search (Bottom-Up)**: Searches from Family → Superfamily → Infraorder → Suborder → Order → Class
2. **Manual assignment**: Uses values from the "Manual assignment" column if present
3. **Taxonomic fallback**: Assigns the deepest known taxonomic level if no specific rule matches

This ensures maximum classification coverage while maintaining taxonomic accuracy.

## 🛠️ Verification

Run the test script to verify your setup:

```bash
python test_version.py
```

This displays your current configuration, expected output paths, and examples of how different version names would be processed.

## 💡 Example Workflow

```bash
# Initial setup
conda activate reclass_env

# Process data with detailed taxonomy
# (config.py: MASTER_FILE = "ClassificationClasses_detailed.csv")
python faird_reclass.py
python tree_scheme.py

# Switch to simplified taxonomy
# (config.py: MASTER_FILE = "ClassificationClasses_simple.csv")
python faird_reclass.py
python tree_scheme.py

# Compare results
ls reclass/          # Shows: dataset_detailed.csv, dataset_simple.csv
ls scheme/           # Shows: taxonomy_tree_detailed.png, taxonomy_tree_simple.png
```

## 📝 Notes

- The master file name format `ClassificationClasses_[version].csv` is recommended but not required
- If no version suffix is detected, "default" is used automatically
- CSV outputs use semicolon separators for compatibility with European Excel formats
- Tree visualizations require Graphviz to be installed system-wide (handled by Conda)
