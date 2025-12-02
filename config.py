# --- CONFIGURATION ---
# ...
MASTER_FILE = "ClassificationClasses_long.csv"
MASTER_LEAF_COL = "Leave"

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
