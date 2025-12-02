# --- CONFIGURATION ---
# ...
MASTER_FILE = "ClassificationClasses_simplified.csv"
MASTER_LEAF_COL = "Leaf"

# --- TREE VISUALIZATION OPTIONS ---
# Collapse 1:1 parent-leaf relationships in the tree visualization
# (does not modify CSV outputs, only affects the diagram)
COLLAPSE_LEAF_ALIAS = True

# Label format when collapsing (only used if COLLAPSE_LEAF_ALIAS = True)
# Options: "taxonomic_common" or "common_taxonomic"
# Examples: "Orthoptera (grasshopper)" or "grasshopper (Orthoptera)"
LABEL_FORMAT = "common_taxonomic"


# Extract version suffix from master file name
# Example: "ClassificationClasses_long.csv" -> "long"
import re

VERSION_SUFFIX = ""
match = re.search(r"ClassificationClasses_(.+)\.csv", MASTER_FILE)
if match:
    VERSION_SUFFIX = match.group(1)
else:
    # Fallback if no suffix found
    VERSION_SUFFIX = "default"
