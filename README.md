# 🐝 Insect Taxonomy Pipeline

Tools to standardize insect classification data and generate hierarchical visualization trees.

## 📂 Project Structure

```
project_root/
├── config.py                        # [REQUIRED] Configuration settings
├── ClassificationClasses_xx.csv     # [REQUIRED] Master taxonomy file
├── faird_reclass.py                 # Script 1: Cleaning & Reclassification
├── tree_scheme.py                   # Script 2: Visual Tree Generator
├── environment.yaml                 # Conda environment config
├── source_tables/                   # [INPUT] Place raw Excel files here
├── reclass/                         # [OUTPUT 1] Processed CSVs
└── scheme/                          # [OUTPUT 2] PNG diagrams
```

## 🧬 Master Taxonomy File

`ClassificationClasses_xx.csv` is the **single source of truth**:

**Structure:**
```csv
Class,Order,Suborder,Infraorder,Superfamily,Family,Leaf
Insecta,Diptera,Brachycera,Muscomorpha,Muscoidea,,fly
Insecta,Diptera,Brachycera,Muscomorpha,Syrphoidea,Syrphidae,hoverfly
```

**What it controls:**
- Classification logic (taxonomy → leaf mappings)
- Hierarchical relationships
- True leaf definitions (yellow nodes in trees)

**To modify:** Edit the CSV and re-run. No code changes needed.

---

## ⚙️ Configuration (`config.py`)

```python
MASTER_FILE = "ClassificationClasses_long.csv"
MASTER_LEAF_COL = "Leaf"
VERSION_SUFFIX = "long"              # Appears in output filenames
DELETE_UNCLASSIFIED_ROWS = True      # Auto-delete rows with no taxonomy
COLLAPSE_LEAF_ALIAS = True           # Collapse 1:1 parent-leaf pairs
LABEL_FORMAT = "common_taxonomic"    # or "taxonomic_common"
```

**Versioning:** Use different suffixes (e.g., "long", "short") to test multiple approaches simultaneously.

---

## 🔧 Installation

```bash
conda env create -f environment.yaml
conda activate reclass_env
```

---

## 🚀 Usage

### Step 1: Reclassification

```bash
python faird_reclass.py
```

**What it does:**
- Reads Excel files from `/source_tables`
- Applies hierarchical classification rules
- Classifies at most specific level possible (Leaf → Family → ... → Class)

**Output columns:**
- `Leaf_reclass` - True leaves only (from master file)
- `Family_reclass`, `Superfamily_reclass`, `Infraorder_reclass`
- `Suborder_reclass`, `Order_reclass`, `Class_reclass`

**Statistics example:**
```
==================================================
CLASSIFICATION STATISTICS
==================================================
  767 classified at Leaf level
    0 classified at Family level
    1 classified at Superfamily level
  331 classified at Suborder level
  335 classified at Order level
--------------------------------------------------
    5 unclassified (no taxonomic level)
==================================================
```

**Output:** CSVs in `/reclass` folder (format: `filename_{VERSION}.csv`)

---

### Step 2: Tree Visualization

```bash
python tree_scheme.py
```

**Generates TWO versions:**

1. **Endpoint** (`taxonomy_tree_{version}.png`)
   - Counts only final classifications
   
2. **Cumulative** (`taxonomy_tree_{version}_cml.png`)
   - Counts all flow-through (cumulative)

**Features:**
- Yellow nodes = True leaves
- White nodes = Higher levels
- Deterministic layout (same data = same graph)
- Optional 1:1 alias collapsing

**Output:** PNGs in `/scheme` folder

---

## 🔬 Key Features

### Hierarchical Classification

Observations classified at **most specific level possible**:

```
Example: Order=Diptera, Suborder=Brachycera, Family=#N/C

Result:
  Leaf_reclass: (empty)          ← Not a true leaf
  Suborder_reclass: Brachycera   ← Most specific available
  Order_reclass: Diptera
  Class_reclass: Insecta
```

### Deepest-Level Indexing

Prevents classification conflicts when rules share parent levels:

```csv
# Both have Superfamily=Muscoidea
Insecta,Diptera,Brachycera,Muscomorpha,Muscoidea,,fly
Insecta,Diptera,Brachycera,Muscomorpha,Muscoidea,Scathophagidae,dung_fly
```

**Solution:** Index by most specific defined level
- Rule 1 indexed at Superfamily → fly
- Rule 2 indexed at Family → dung_fly
- No conflicts ✅

### Version Management

```bash
# Test approach 1
MASTER_FILE = "ClassificationClasses_long.csv"
VERSION_SUFFIX = "long"
# Run → generates data_long.csv, taxonomy_tree_long.png

# Test approach 2
MASTER_FILE = "ClassificationClasses_short.csv"  
VERSION_SUFFIX = "short"
# Run → generates data_short.csv, taxonomy_tree_short.png

# Both coexist for comparison!
```

---

## 🐛 Troubleshooting

**"0 classified at Leaf level" but many at higher levels**
- Expected behavior! Observations lack specific taxonomy.

**Different tree layouts each run**
- Fixed in current version (sorted nodes/edges).

**Graphviz render failed**
- Install system Graphviz: `conda install graphviz` + system package

**Too many generic classifications**
- Add more specific rules to master file

---

## 📝 Notes

- Output CSVs use `;` delimiter (not `,`)
- Looks for "Monitoring" sheet, falls back to first
- "Manual assignment" column used as fallback if present
- Memory-efficient for ~10K rows

---

## 📚 Documentation

- `FIX_TAXONOMIC_MAPPING.md` - Deepest-level logic
- `FIXED_COLUMNS_STRUCTURE.md` - Column design rationale
