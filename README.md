# 🐝 Insect Taxonomy Pipeline

Tools to standardize insect classification data and generate hierarchical visualization trees.

## 📂 Project Structure

Ensure your project folder looks exactly like this:
```
project_root/
├── ClassificationClasses.csv    # [REQUIRED] Master taxonomy file
├── faird_reclass.py             # Script 1: Cleaning & Reclassification
├── tree_scheme.py               # Script 2: Visual Tree Generator
├── environment.yaml             # Conda environment config
├── source_tables/               # [INPUT] Place your raw Excel files here (.xlsx)
├── reclass/                     # [OUTPUT 1] Processed CSVs appear here
└── scheme/                      # [OUTPUT 2] Final diagrams appear here
```

## 🧬 Master Taxonomy & Customization (Crucial!)

The file `ClassificationClasses.csv` is the **single source of truth** for this entire pipeline.

* **It defines the logic:** It tells the scripts how to map biological taxonomy (e.g., *Syrphidae*) to your specific classes (e.g., *hoverfly*).
* **It controls the hierarchy:** The parent folders (1-6) are generated exclusively based on the lineage defined in this file.
* **It defines visualization:** Only the classes listed in this file will be highlighted as "True Leaves" (yellow nodes) in the final tree.

**⚠️ Important:**
If you need to change the structure of the tree, correct a phylogenetic relationship, or add new insect categories, **you must edit `ClassificationClasses.csv`**. Modifying the scripts is not necessary; simply update the CSV and re-run the pipeline.

---

## ⚙️ Installation

This project requires Conda to handle Graphviz dependencies correctly.

1. Open your terminal/Anaconda Prompt.

2. Create the environment:
```bash
   conda env create -f environment.yaml
```

3. Activate the environment:
```bash
   conda activate taxonomy_env
```

# 🚀 Usage

Run the scripts in the following order:

### Step 1: Standardize Data

This script reads raw Excel files from `/source_tables`, applies strict taxonomy rules based on the Master CSV, handles manual assignments, and fixes hierarchy gaps.
```bash
python faird_reclass_final.py
```

**Interactive Filtering:** If the script finds rows that cannot be classified (result `#N/C`), it will pause and ask you:
```
>> DELETE these rows? (y/n):
```

- **Type `y` (Yes):** Recommended for final output. It removes unclassified rows to keep the dataset clean.
- **Type `n` (No):** Useful for debugging. It keeps the rows so you can open the CSV and inspect why they failed (e.g., missing taxonomy in the Excel).
  - **Note:** Even if you keep them, the next script (`tree_scheme`) will safely ignore these `#N/C` rows.

**Output:** Clean, semicolon-separated CSV files generated in the `/reclass` folder.

### Step 2: Generate Tree

This script reads the processed files from /reclass, combines the data, and draws a phylogenetic tree highlighting true leaf nodes.
```bash
python tree_scheme.py
```

**Output:** A high-resolution image (`taxonomy_tree.png`) generated in the `/scheme`folder.

