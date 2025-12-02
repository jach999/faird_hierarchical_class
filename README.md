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

Edit `config.py` to specify your settings:

```python
# Master taxonomy file
MASTER_FILE = "ClassificationClasses_long.csv"
MASTER_LEAF_COL = "Leave"

# Tree visualization options
COLLAPSE_LEAF_ALIAS = True              # Collapse 1:1 parent-leaf relationships
LABEL_FORMAT = "common_taxonomic"       # Label format for collapsed nodes
```

**Version suffix** (e.g., `_long`) is automatically extracted from the master file name and applied to all outputs.

**Collapse settings:**
- `COLLAPSE_LEAF_ALIAS = True`: Merges redundant 1:1 relationships in the tree visualization (e.g., `Syrphidae → hoverfly` becomes `hoverfly (Syrphidae)`)
- `COLLAPSE_LEAF_ALIAS = False`: Shows complete taxonomic hierarchy with all levels
- `LABEL_FORMAT`: Choose `"common_taxonomic"` for "hoverfly (Syrphidae)" or `"taxonomic_common"` for "Syrphidae (hoverfly)"

**Note:** Collapsing only affects visualization—CSV outputs remain unchanged and preserve complete taxonomic information.

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

## 🎨 Tree Visualization Options

### Understanding Hierarchy Collapse

The `COLLAPSE_LEAF_ALIAS` setting controls how the tree visualization handles redundant taxonomic relationships.

#### What Gets Collapsed?

**1:1 Redundant Relationships** - When a single parent taxonomic level maps directly to a single leaf:

```
WITHOUT COLLAPSE:                WITH COLLAPSE:
Muscoidea → Syrphidae → hoverfly    Muscoidea → hoverfly (Syrphidae)
Apoidea → Apidae → bee              Apoidea → bee (Apidae)
Culicomorpha → Culicidae → mosquito Culicomorpha → mosquito (Culicidae)
```

These are collapsed because `Syrphidae` and `hoverfly` represent the same entity—the family name is essentially an alias for the common name.

#### What Does NOT Get Collapsed?

**Taxonomic Convergences** - When multiple parent taxa share the same common name leaf:

```
EXAMPLE: Multiple families → digger_wasp

WITHOUT COLLAPSE:                    WITH COLLAPSE:
Apoidea → Sphecidae ──┐             Apoidea → Sphecidae ──┐
Apoidea → Astatidae ──┼→ digger_wasp  Apoidea → Astatidae ──┼→ digger_wasp
Apoidea → Crabronidae ┘             Apoidea → Crabronidae ┘
```

These convergences are **preserved** because they represent meaningful taxonomic diversity—multiple distinct families that share the same common name. This is scientifically important and valuable for machine learning models.

### Configuration Options

Edit `config.py`:

```python
# Enable/disable collapsing
COLLAPSE_LEAF_ALIAS = True   # True: collapse 1:1 aliases, False: show complete hierarchy

# Label format (only applies when COLLAPSE_LEAF_ALIAS = True)
LABEL_FORMAT = "common_taxonomic"  # or "taxonomic_common"
```

#### Label Format Options

- **`"common_taxonomic"`** (default): `hoverfly (Syrphidae)`
  - Prioritizes common name for readability
  - Recommended for general use and ML applications

- **`"taxonomic_common"`**: `Syrphidae (hoverfly)`
  - Prioritizes scientific name
  - Recommended for scientific publications or taxonomic review

### Benefits for Machine Learning

**With collapsing enabled:**
- Eliminates redundant hierarchy levels that don't add information
- Creates more efficient tree structures for hierarchical classification models
- Highlights actual decision points vs taxonomic aliases
- Reduces model parameters without losing information

**Example:** A model doesn't need separate learned representations for both "Syrphidae" (family) and "hoverfly" (common name) when they're synonymous—one combined node is more efficient.

**Convergences preserved:** When multiple families map to the same common name (e.g., digger_wasp), this represents real taxonomic diversity and is preserved as it provides valuable information for classification.

### How It Works

The collapse logic automatically:

1. **Detects 1:1 relationships**: Finds parent nodes with exactly one child that is a true leaf
2. **Checks for convergence**: Skips collapsing if multiple parents point to the same leaf
3. **Merges redundant pairs**: Combines parent and leaf into a single labeled node
4. **Preserves counts**: Maintains accurate classification counts (n=X) for all nodes

**Console output during tree generation:**
```
[INFO] Detecting and collapsing 1:1 parent-leaf relationships...
  - Collapsing: Syrphidae → hoverfly => hoverfly (Syrphidae)
  - Collapsing: Apidae → bee => bee (Apidae)
  - Skipping: Sphecidae → digger_wasp (converges with 2 other parent(s))
  Collapsed 15 node pairs
```

### Important Notes

- **CSV files unchanged**: The collapse setting only affects the tree visualization. All processed CSV files retain complete hierarchical information in the `Parent folder 1-6` columns
- **Reversible**: You can generate both collapsed and non-collapsed versions by changing the config setting
- **Scientifically accurate**: Convergences (multiple parents → one leaf) are always preserved to maintain taxonomic meaning

### Comparing Visualization Modes

To generate and compare both versions:

```bash
# Generate collapsed version
# Edit config.py: COLLAPSE_LEAF_ALIAS = True
python tree_scheme.py
mv scheme/taxonomy_tree_long.png scheme/tree_collapsed.png

# Generate full hierarchy version
# Edit config.py: COLLAPSE_LEAF_ALIAS = False
python tree_scheme.py
mv scheme/taxonomy_tree_long.png scheme/tree_full.png

# Compare both visualizations side-by-side
```

Run `python demo_collapse.py` to see your current settings and examples of how different taxonomies would be displayed.

### When to Use Each Mode

**Use COLLAPSE_LEAF_ALIAS = True when:**
- Training hierarchical machine learning models
- Analyzing decision structure and information flow
- Presenting to non-taxonomist audiences
- Optimizing model architecture

**Use COLLAPSE_LEAF_ALIAS = False when:**
- Need complete taxonomic lineage for reference
- Creating figures for scientific publications
- Performing taxonomic review or verification
- Teaching taxonomy or creating educational materials
