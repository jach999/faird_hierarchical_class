import pandas as pd
from pathlib import Path
import os
import config

# --- CONFIGURATION ---
HOME = os.path.dirname(__file__)
MASTER_FILE = config.MASTER_FILE
TARGET_SHEET = "Monitoring"
MANUAL_COL_NAME = "Manual assignment"
INPUT_FOLDER_NAME = "source_tables"
OUTPUT_FOLDER_NAME = "reclass"

TAXONOMIC_HIERARCHY = [
    "Family",
    "Superfamily",
    "Infraorder",
    "Suborder",
    "Order",
    "Class",
]


def normalize_value(val) -> str:
    if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "#n/c":
        return "#n/c"
    return str(val).strip().replace("\xa0", " ").replace("\n", "").lower()


def build_knowledge_base(ref_df):
    rules_by_level = {level.lower(): {} for level in TAXONOMIC_HIERARCHY}
    class_lookup = {}
    taxon_lineage_map = {}
    print(f"  [INFO] Building knowledge base (deepest_level indexing)...")

    for _, row in ref_df.iterrows():
        deepest_level = None
        deepest_value = None
        for level in TAXONOMIC_HIERARCHY:
            if level in ref_df.columns:
                val = normalize_value(row[level])
                if val != "#n/c":
                    deepest_level = level.lower()
                    deepest_value = val
                    break

        parent_dict = {}
        for col in TAXONOMIC_HIERARCHY[::-1]:
            if col in ref_df.columns:
                val = row[col]
                if not pd.isna(val) and normalize_value(val) != "#n/c":
                    parent_dict[col] = str(val).strip()
                else:
                    parent_dict[col] = None

        full_path = [v for v in parent_dict.values() if v is not None]
        full_parents_reversed = full_path[::-1]

        rule_obj = {
            "result_class": row[config.MASTER_LEAF_COL],
            "parents": full_parents_reversed,
            "parent_dict": parent_dict,
        }

        if deepest_level and deepest_value:
            rules_by_level[deepest_level][deepest_value] = rule_obj

        cls_key = normalize_value(row[config.MASTER_LEAF_COL])
        if cls_key != "#n/c":
            class_lookup[cls_key] = {"list": full_parents_reversed, "dict": parent_dict}

        for i, taxon in enumerate(full_path):
            taxon_key = normalize_value(taxon)
            if taxon_key != "#n/c":
                parents_of_taxon = full_path[:i][::-1]
                if taxon_key not in taxon_lineage_map:
                    taxon_lineage_map[taxon_key] = parents_of_taxon

    return rules_by_level, class_lookup, taxon_lineage_map


def find_best_match_bottom_up(row, rules_by_level, taxonomic_map):
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
                parent_dict = {}
                for tax_level in TAXONOMIC_HIERARCHY:
                    excel_col = None
                    for col_orig, col_std in taxonomic_map.items():
                        if col_std.lower() == tax_level.lower():
                            excel_col = col_orig
                            break
                    if excel_col and excel_col in row:
                        cell_val = row[excel_col]
                        if (
                            not pd.isna(cell_val)
                            and normalize_value(cell_val) != "#n/c"
                        ):
                            parent_dict[tax_level] = str(cell_val).strip()
                        else:
                            parent_dict[tax_level] = None
                    else:
                        parent_dict[tax_level] = None
                return {
                    "result_class": str(val).strip(),
                    "parents": taxon_lineage_map[val_norm],
                    "parent_dict": parent_dict,
                }
    return None


def process_excel_file(
    file_path: Path,
    rules_by_level: dict,
    class_lookup: dict,
    taxon_lineage_map: dict,
    true_leaves: set,
) -> bool:
    print(f"\n{'=' * 60}\nPROCESSING: {file_path.name}\n{'=' * 60}")
    try:
        try:
            df = pd.read_excel(file_path, sheet_name=TARGET_SHEET)
            print(f"  [OK] Sheet '{TARGET_SHEET}' loaded.")
        except ValueError:
            df = pd.read_excel(file_path, sheet_name=0)
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        initial_rows = len(df)
        taxonomic_map = {}
        for col in df.columns:
            clean_col = str(col).strip()
            for tax_level in TAXONOMIC_HIERARCHY:
                if clean_col.lower() == tax_level.lower():
                    taxonomic_map[col] = tax_level
                    break
        manual_col_found = None
        for c in df.columns:
            if str(c).strip().lower() == MANUAL_COL_NAME.lower():
                manual_col_found = c
                break
        if manual_col_found:
            print(f"  [OK] Manual assignment: '{manual_col_found}'")
        new_taxonomy = []
        print(f"  [INFO] Classifying {initial_rows} rows...")
        for idx, row in df.iterrows():
            cls_res = "#N/C"
            parent_dict = {}
            match = find_best_match_bottom_up(row, rules_by_level, taxonomic_map)
            if match:
                cls_res = match["result_class"]
                parent_dict = match.get("parent_dict", {})
            if cls_res == "#N/C" and manual_col_found:
                manual_val = row[manual_col_found]
                norm_manual = normalize_value(manual_val)
                if norm_manual not in ["#n/c", "0", "nan"]:
                    cls_res = str(manual_val).strip()
                    if norm_manual in class_lookup:
                        lookup_data = class_lookup[norm_manual]
                        parent_dict = (
                            lookup_data.get("dict", {})
                            if isinstance(lookup_data, dict)
                            else {}
                        )
            if cls_res == "#N/C":
                fallback = find_taxonomic_fallback(
                    row, taxonomic_map, taxon_lineage_map
                )
                if fallback:
                    cls_res = fallback["result_class"]
                    parent_dict = fallback.get("parent_dict", {})
            is_true_leaf = cls_res in true_leaves if cls_res != "#N/C" else False
            taxonomic_data = {"Leaf_reclass": cls_res if is_true_leaf else pd.NA}
            for level_name in TAXONOMIC_HIERARCHY:
                val = parent_dict.get(level_name, None)
                if val and str(val).strip().lower() not in ["nan", "#n/c", ""]:
                    taxonomic_data[f"{level_name}_reclass"] = str(val).strip()
                else:
                    taxonomic_data[f"{level_name}_reclass"] = pd.NA
            # CRITICAL: If cls_res is not a leaf but matches a taxonomic level, fill it
            if not is_true_leaf and cls_res != "#N/C":
                for level_name in TAXONOMIC_HIERARCHY:
                    parent_val = parent_dict.get(level_name, None)
                    if parent_val and normalize_value(parent_val) == normalize_value(
                        cls_res
                    ):
                        taxonomic_data[f"{level_name}_reclass"] = cls_res
                        break
            new_taxonomy.append(taxonomic_data)
        taxonomy_df = pd.DataFrame(new_taxonomy)
        old_cols = [col for col in df.columns if "_reclass" in col]
        if old_cols:
            df = df.drop(columns=old_cols)
        for col in taxonomy_df.columns:
            df[col] = taxonomy_df[col]
        print(f"  [INFO] Added: Leaf_reclass → Class_reclass")

        # Detailed classification statistics
        print(f"\n  {'=' * 50}")
        print(f"  CLASSIFICATION STATISTICS")
        print(f"  {'=' * 50}")

        # Count by most specific level achieved
        levels_hierarchy = [
            "Leaf_reclass",
            "Family_reclass",
            "Superfamily_reclass",
            "Infraorder_reclass",
            "Suborder_reclass",
            "Order_reclass",
            "Class_reclass",
        ]

        for level in levels_hierarchy:
            count = df[level].notna().sum()
            if count > 0:
                level_name = level.replace("_reclass", "")
                print(f"    {count:4d} classified at {level_name} level")

        # Find truly unclassified (no level at all)
        all_empty = df[levels_hierarchy].isna().all(axis=1)
        truly_unclassified = all_empty.sum()

        print(f"  {'-' * 50}")
        print(f"    {truly_unclassified:4d} unclassified (no taxonomic level)")
        print(f"  {'=' * 50}\n")

        # Only delete truly unclassified rows
        df_final = df
        if truly_unclassified > 0:
            if config.DELETE_UNCLASSIFIED_ROWS:
                df_final = df[~all_empty]
                print(f"  [AUTO] Deleted {truly_unclassified} truly unclassified rows")
            else:
                print(f"  [AUTO] Kept {truly_unclassified} truly unclassified rows")
        if df_final.empty:
            return False
        output_dir = Path(HOME) / OUTPUT_FOLDER_NAME
        output_dir.mkdir(parents=True, exist_ok=True)
        output_name = output_dir / f"{file_path.stem}_{config.VERSION_SUFFIX}.csv"
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
    input_dir = script_dir / INPUT_FOLDER_NAME
    if not ref_file.exists() or not input_dir.exists():
        print("Error: Missing files")
        return
    excel_files = sorted(
        [
            f
            for f in input_dir.glob("*")
            if f.suffix.lower() in [".xlsx", ".xls"] and not f.name.startswith("~$")
        ]
    )
    try:
        ref_df = pd.read_csv(ref_file)
        true_leaves = set()
        if config.MASTER_LEAF_COL in ref_df.columns:
            true_leaves = set(
                ref_df[config.MASTER_LEAF_COL].dropna().astype(str).str.strip()
            )
            print(f"[INFO] Loaded {len(true_leaves)} true leaves")
        rules_by_level, class_lookup, taxon_lineage_map = build_knowledge_base(ref_df)
    except Exception as e:
        print(f"Error: {e}")
        return
    if not excel_files:
        return
    print(f"Found {len(excel_files)} files...")
    for f in excel_files:
        process_excel_file(
            f, rules_by_level, class_lookup, taxon_lineage_map, true_leaves
        )


if __name__ == "__main__":
    main()
