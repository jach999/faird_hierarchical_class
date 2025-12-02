import pandas as pd
from pathlib import Path
import os
import sys
import config

# --- CONFIGURATION ---
HOME = os.path.dirname(__file__)
MASTER_FILE = config.MASTER_FILE  # Use from config.py
TARGET_SHEET = "Monitoring"
MANUAL_COL_NAME = "Manual assignment"

# Folder Configuration
INPUT_FOLDER_NAME = "source_tables"  # Where raw Excels are located
OUTPUT_FOLDER_NAME = "reclass"  # Where processed CSVs will be saved

# Strict order: From most specific (Family) to most general (Class)
TAXONOMIC_HIERARCHY = [
    "Family",
    "Superfamily",
    "Infraorder",
    "Suborder",
    "Order",
    "Class",
]


def normalize_value(val: any) -> str:
    """
    Standardizes text values: lowercase, removes extra spaces/newlines.
    Returns '#n/c' for empty/null values.
    """
    if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "#n/c":
        return "#n/c"
    return str(val).strip().replace("\xa0", " ").replace("\n", "").lower()


def build_knowledge_base(ref_df):
    """
    Builds the classification rules indexed by their 'Definition Level'.
    Also builds lookup maps for manual assignment and taxonomic lineage.
    """
    rules_by_level = {level.lower(): {} for level in TAXONOMIC_HIERARCHY}
    class_lookup = {}
    taxon_lineage_map = {}

    print(f"  [INFO] Building knowledge base (Bottom-Up Logic)...")

    for _, row in ref_df.iterrows():
        # 1. Determine the deepest level defined in this rule
        deepest_level = None
        deepest_value = None

        for level in TAXONOMIC_HIERARCHY:
            col_name = level
            if col_name in ref_df.columns:
                val = normalize_value(row[col_name])
                if val != "#n/c":
                    deepest_level = level.lower()
                    deepest_value = val
                    break

        # Build full parent path
        full_path = []
        cols_ordered = TAXONOMIC_HIERARCHY[::-1]  # Class -> Family
        for col in cols_ordered:
            if col in ref_df.columns:
                val = str(row[col]).strip()
                if normalize_value(val) != "#n/c":
                    full_path.append(val)

        # Reverse for [Family, ..., Class] (Specific -> General)
        full_parents_reversed = full_path[::-1]

        rule_obj = {
            "result_class": row[config.MASTER_LEAF_COL],
            "parents": full_parents_reversed,
        }

        if deepest_level and deepest_value:
            rules_by_level[deepest_level][deepest_value] = rule_obj

        cls_key = normalize_value(row[config.MASTER_LEAF_COL])
        if cls_key != "#n/c":
            class_lookup[cls_key] = full_parents_reversed

        for i, taxon in enumerate(full_path):
            taxon_key = normalize_value(taxon)
            if taxon_key != "#n/c":
                parents_of_taxon = full_path[:i][::-1]
                if taxon_key not in taxon_lineage_map:
                    taxon_lineage_map[taxon_key] = parents_of_taxon

    return rules_by_level, class_lookup, taxon_lineage_map


def find_best_match_bottom_up(row, rules_by_level, taxonomic_map):
    """
    Searches for matches starting from Family up to Class.
    If a match is found at a specific level, it returns that rule immediately.
    """
    for level in TAXONOMIC_HIERARCHY:
        level_key = level.lower()
        excel_col = None
        for col_orig, col_std in taxonomic_map.items():
            if col_std.lower() == level_key:
                excel_col = col_orig
                break

        if excel_col and excel_col in row:
            val_in_row = normalize_value(row[excel_col])
            if val_in_row != "#n/c":
                if val_in_row in rules_by_level[level_key]:
                    return rules_by_level[level_key][val_in_row]
    return None


def find_taxonomic_fallback(row, taxonomic_map, taxon_lineage_map):
    """
    Fallback: Finds the deepest valid taxonomic anchor known in the lineage map.
    """
    for level in TAXONOMIC_HIERARCHY:
        level_key = level.lower()
        col_name_in_excel = None
        for col_orig, col_std in taxonomic_map.items():
            if col_std.lower() == level_key:
                col_name_in_excel = col_orig
                break

        if col_name_in_excel and col_name_in_excel in row:
            val = row[col_name_in_excel]
            val_norm = normalize_value(val)
            if val_norm != "#n/c" and val_norm in taxon_lineage_map:
                return {
                    "result_class": str(val).strip(),
                    "parents": taxon_lineage_map[val_norm],
                }
    return None


def reorder_columns(df):
    """Moves 'Refined' and 'Parent folders 1-6' next to the original Class column."""
    original_cls_col = None
    for col in df.columns:
        c_lower = str(col).lower()
        if (
            "classification" in c_lower
            and "class" in c_lower
            and "refined" not in c_lower
        ):
            original_cls_col = col
            break

    if original_cls_col:
        cols = list(df.columns)
        cols_to_move = ["Classification class refined"] + [
            f"Parent folder {i}" for i in range(1, 7)
        ]
        cols_to_move = [c for c in cols_to_move if c in cols]

        for c in cols_to_move:
            cols.remove(c)

        insert_idx = cols.index(original_cls_col) + 1
        for i, c in enumerate(cols_to_move):
            cols.insert(insert_idx + i, c)
        return df[cols]
    return df


def process_excel_file(
    file_path: Path, rules_by_level: dict, class_lookup: dict, taxon_lineage_map: dict
) -> bool:
    print(f"\n{'=' * 60}")
    print(f"PROCESSING: {file_path.name}")
    print(f"{'=' * 60}")

    try:
        try:
            df = pd.read_excel(file_path, sheet_name=TARGET_SHEET)
            print(f"  [OK] Sheet '{TARGET_SHEET}' loaded.")
        except ValueError:
            print(
                f"  [WARN] Sheet '{TARGET_SHEET}' not found. Using default sheet (0)."
            )
            df = pd.read_excel(file_path, sheet_name=0)

        # Remove ghost columns (Unnamed)
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        initial_rows = len(df)

        # Map Excel columns to Standard Taxonomy
        taxonomic_map = {}
        for col in df.columns:
            clean_col = str(col).strip()
            for tax_level in TAXONOMIC_HIERARCHY:
                if clean_col.lower() == tax_level.lower():
                    taxonomic_map[col] = tax_level
                    break

        # Check for Manual Assignment column
        manual_col_found = None
        for c in df.columns:
            if str(c).strip().lower() == MANUAL_COL_NAME.lower():
                manual_col_found = c
                break

        if manual_col_found:
            print(f"  [OK] Manual assignment column found: '{manual_col_found}'")
        else:
            print(f"  [WARNING] Column '{MANUAL_COL_NAME}' not found.")

        new_classes = []
        new_parents = []

        print(f"  [INFO] Classifying {initial_rows} rows...")

        for idx, row in df.iterrows():
            cls_res = "#N/C"
            parents = []

            # 1. HIERARCHICAL SEARCH (Bottom-Up)
            match = find_best_match_bottom_up(row, rules_by_level, taxonomic_map)

            if match:
                cls_res = match["result_class"]
                parents = match["parents"]

            # 2. MANUAL ASSIGNMENT
            if cls_res == "#N/C" and manual_col_found:
                manual_val = row[manual_col_found]
                norm_manual = normalize_value(manual_val)
                is_valid = (
                    norm_manual != "#n/c"
                    and norm_manual != "0"
                    and norm_manual != "nan"
                )

                if is_valid:
                    cls_res = str(manual_val).strip()
                    if norm_manual in class_lookup:
                        parents = class_lookup[norm_manual]
                    else:
                        parents = []

            # 3. GENERIC FALLBACK
            if cls_res == "#N/C":
                fallback = find_taxonomic_fallback(
                    row, taxonomic_map, taxon_lineage_map
                )
                if fallback:
                    cls_res = fallback["result_class"]
                    parents = fallback["parents"]

            new_classes.append(cls_res)

            row_parents = {}
            for i in range(1, 7):
                val = parents[i - 1] if i <= len(parents) else "#N/C"
                row_parents[f"Parent folder {i}"] = val
            new_parents.append(row_parents)

        # Assign new columns
        df["Classification class refined"] = new_classes
        parents_df = pd.DataFrame(new_parents)
        for col in parents_df.columns:
            df[col] = parents_df[col]

        # Reorder for visual clarity
        df = reorder_columns(df)

        # Interactive Filtering
        unclassified_mask = df["Classification class refined"] == "#N/C"
        count_unclassified = unclassified_mask.sum()
        df_final = df

        if count_unclassified > 0:
            print(f"\n  {'!' * 40}")
            print(f"  [RESULT] Found {count_unclassified} unclassified rows (#N/C).")
            while True:
                user_response = (
                    input(f"  >> DELETE these rows? (y/n): ").strip().lower()
                )
                if user_response == "y":
                    df_final = df[~unclassified_mask]
                    break
                elif user_response == "n":
                    break
        else:
            print(f"  [OK] All rows classified successfully.")

        if df_final.empty:
            return False

        # --- SAVE OUTPUT ---
        # Save to HOME/reclass/filename.csv
        output_dir = Path(HOME) / OUTPUT_FOLDER_NAME
        output_dir.mkdir(parents=True, exist_ok=True)

        # Add version suffix to the output filename
        base_name = file_path.stem  # filename without extension
        output_name = output_dir / f"{base_name}_{config.VERSION_SUFFIX}.csv"

        df_final.to_csv(output_name, index=False, sep=";", encoding="utf-8-sig")
        print(f"  [SUCCESS] Saved to: {output_name}")
        return True

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    script_dir = Path(HOME)
    ref_file = script_dir / MASTER_FILE

    # --- PATH FIX: Use correct pathlib joining ---
    input_dir = script_dir / INPUT_FOLDER_NAME

    if not ref_file.exists():
        print(f"Error: Missing master file {MASTER_FILE}")
        return

    # Check input directory exists
    if not input_dir.exists():
        print(f"Error: Source folder '{INPUT_FOLDER_NAME}' does not exist.")
        print(f"Expected at: {input_dir}")
        return

    # Find Excel files
    excel_files = sorted(
        [
            f
            for f in input_dir.glob("*")
            if f.suffix.lower() in [".xlsx", ".xls"] and not f.name.startswith("~$")
        ]
    )

    try:
        ref_df = pd.read_csv(ref_file)
        rules_by_level, class_lookup, taxon_lineage_map = build_knowledge_base(ref_df)
    except Exception as e:
        print(f"Error loading master file: {e}")
        return

    if not excel_files:
        print(f"No Excel files found in {input_dir}")
        return

    print(
        f"Found {len(excel_files)} files in '{INPUT_FOLDER_NAME}'. Starting process..."
    )

    for f in excel_files:
        process_excel_file(f, rules_by_level, class_lookup, taxon_lineage_map)


if __name__ == "__main__":
    main()
