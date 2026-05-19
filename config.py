# --- CONFIGURATION ---
# ...
MASTER_FILE = "ClassificationClasses_paper_latin.csv"
MASTER_LEAF_COL = "Leaf"

# Taxonomic columns in the master CSV (general → specific, excluding Leaf)
TAXONOMY_COLS = ["Class", "Order", "Suborder", "Infraorder", "Superfamily", "Family"]

# --- RECLASSIFICATION OPTIONS ---
# Automatically delete rows that cannot be classified (#N/C)
# True: Remove unclassified rows automatically
# False: Keep unclassified rows in output
DELETE_UNCLASSIFIED_ROWS = True

# --- TREE VISUALIZATION OPTIONS ---
# Collapse 1:1 parent-leaf relationships in the tree visualization
# (does not modify CSV outputs, only affects the diagram)
# NOTE: Auto-disabled at runtime when no leaf proxies are detected.
COLLAPSE_LEAF_ALIAS = True

# Label format when collapsing (only used if COLLAPSE_LEAF_ALIAS = True)
# Options: "taxonomic_common" or "common_taxonomic"
# Examples: "Orthoptera (grasshopper)" or "grasshopper (Orthoptera)"
LABEL_FORMAT = "common_taxonomic"

# Center widest subtrees in the paper-style tree diagram
# True: Nodes with the most descendants are placed in the center of each level
# False: Nodes are sorted alphabetically at each level
CENTERED = True

# Show sample counts (n=X) in each node of the tree diagram
# True: Display counts below node labels
# False: Show only node labels
SHOW_COUNTS = False


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


# =====================================================================
# FLEXIBLE LEAF HELPERS
# =====================================================================
# These handle two modes transparently:
#   - Proxy mode: Leaf column has a vernacular name (e.g. "grasshopper")
#   - Latin mode: Leaf column is empty → deepest taxonomic column is the leaf
# =====================================================================

import pandas as pd


def get_effective_leaf(row, leaf_col=None, tax_cols=None):
    """
    Returns the effective leaf name for a master CSV row.

    If Leaf is populated → returns it (proxy mode).
    If Leaf is empty/NaN → returns the deepest non-empty taxonomic column value.
    """
    if leaf_col is None:
        leaf_col = MASTER_LEAF_COL
    if tax_cols is None:
        tax_cols = TAXONOMY_COLS

    leaf_val = row.get(leaf_col)
    if pd.notna(leaf_val) and str(leaf_val).strip():
        return str(leaf_val).strip()

    # Leaf is empty: use the deepest taxonomic column
    for col in reversed(tax_cols):
        val = row.get(col)
        if pd.notna(val) and str(val).strip():
            return str(val).strip()

    return None


def has_leaf_proxies(df, leaf_col=None, tax_cols=None):
    """
    Returns True if ANY row in the master CSV has a Leaf value
    that differs from its deepest taxonomic column (= proxy mode).
    Returns False if all Leaf values are empty or identical to the
    deepest taxonomic column (= Latin mode).
    """
    if leaf_col is None:
        leaf_col = MASTER_LEAF_COL
    if tax_cols is None:
        tax_cols = TAXONOMY_COLS

    for _, row in df.iterrows():
        leaf_val = row.get(leaf_col)
        if pd.notna(leaf_val) and str(leaf_val).strip():
            # Find deepest taxonomic value in this row
            for col in reversed(tax_cols):
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    if str(leaf_val).strip() != str(val).strip():
                        return True  # Found a proxy
                    break  # Leaf == last taxonomic node, not a proxy
    return False
