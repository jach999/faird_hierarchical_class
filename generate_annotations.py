"""
generate_annotations.py
=======================
Generates a single JSON annotation file for hierarchical DL training.

Maps each observation to its full set of source videos (check-in,
intermediates, check-out) and hierarchical classification labels.

Replaces the manual folder-based approach: all images can live in a
flat folder and the model reads labels from this JSON.

Usage:
    python generate_annotations.py

Reads:
    - Master taxonomy file (from config.py)
    - Reclassified CSVs from /reclass folder
    - Source Excel files from /source_tables (for Video_List sheet)

Produces:
    - annotations/annotations_{VERSION}.json
"""

import pandas as pd
import json
from pathlib import Path
from collections import Counter
import config

# --- CONFIGURATION ---
HOME = Path(__file__).parent
RECLASS_FOLDER = HOME / "reclass"
SOURCE_FOLDER = HOME / "source_tables"
OUTPUT_FOLDER = HOME / "annotations"

# Hierarchy columns in the reclassified CSVs (general → specific)
HIERARCHY_COLS = [
    "Class_reclass",
    "Order_reclass",
    "Suborder_reclass",
    "Infraorder_reclass",
    "Superfamily_reclass",
    "Family_reclass",
    "Leaf_reclass",
]

# Video-related columns in the Monitoring data
VIDEO_CHECK_IN = "Video Name check in"
VIDEO_CHECK_OUT = "Video Name check out"
NO_VIDEOS_COL = "No. Videos"


# =====================================================================
# 1. HIERARCHY (from master taxonomy CSV)
# =====================================================================
def load_master_taxonomy():
    """Load master taxonomy and build the hierarchy tree + class indices."""
    master_path = HOME / config.MASTER_FILE
    ref_df = pd.read_csv(master_path)
    tax_cols = [
        "Class",
        "Order",
        "Suborder",
        "Infraorder",
        "Superfamily",
        "Family",
        "Leaf",
    ]

    tree = {}
    all_paths = []

    for _, row in ref_df.iterrows():
        path = []
        for col in tax_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip():
                path.append(str(val).strip())
        all_paths.append(path)

        node = tree
        for i, taxon in enumerate(path):
            if taxon not in node:
                node[taxon] = {"children": {}, "is_leaf": False}
            if i == len(path) - 1:
                node[taxon]["is_leaf"] = True
            node = node[taxon]["children"]

    # Nodes by depth level
    def get_all_nodes_by_depth(t, depth=1):
        result = {}
        for name, info in t.items():
            result.setdefault(depth, set()).add(name)
            for d, names in get_all_nodes_by_depth(info["children"], depth + 1).items():
                result.setdefault(d, set()).update(names)
        return result

    nodes_by_depth = get_all_nodes_by_depth(tree)
    max_depth = max(nodes_by_depth.keys()) if nodes_by_depth else 0

    class_to_idx = {}
    idx_to_class = {}
    for depth in sorted(nodes_by_depth.keys()):
        level = f"L{depth}"
        sorted_classes = sorted(nodes_by_depth[depth])
        class_to_idx[level] = {cls: i for i, cls in enumerate(sorted_classes)}
        idx_to_class[level] = {i: cls for i, cls in enumerate(sorted_classes)}

    def simplify_tree(t):
        result = {}
        for name, info in t.items():
            children = simplify_tree(info["children"])
            result[name] = {"is_leaf": info["is_leaf"], "children": children or None}
        return result

    hierarchy = {
        "master_file": config.MASTER_FILE,
        "num_levels": max_depth,
        "level_names": [f"L{i}" for i in range(1, max_depth + 1)],
        "classes_per_level": {
            f"L{d}": sorted(list(names)) for d, names in sorted(nodes_by_depth.items())
        },
        "class_to_idx": class_to_idx,
        "idx_to_class": {
            lv: {str(k): v for k, v in mapping.items()}
            for lv, mapping in idx_to_class.items()
        },
        "tree": simplify_tree(tree),
        "paths": [list(p) for p in all_paths],
    }
    return hierarchy


# =====================================================================
# 2. VIDEO LIST (from source Excel files)
# =====================================================================
def load_all_video_lists():
    """
    Load Video_List sheets from all source Excel files.
    Returns a dict: { source_stem: sorted list of video filenames }
    """
    video_lists = {}
    excel_files = sorted(
        f
        for f in SOURCE_FOLDER.glob("*")
        if f.suffix.lower() in [".xlsx", ".xls"] and not f.name.startswith("~$")
    )

    for xls_path in excel_files:
        try:
            vl = pd.read_excel(xls_path, sheet_name="Video_List")
            vl = vl.loc[:, ~vl.columns.str.contains("^Unnamed")]
            vl = vl.sort_values("Date + Hour").reset_index(drop=True)
            vl["Filename"] = vl["Filename"].astype(str).str.strip()
            video_lists[xls_path.stem] = list(vl["Filename"])
            print(f"  [OK] Video_List from {xls_path.name}: {len(vl)} videos")
        except Exception as e:
            print(f"  [WARN] No Video_List in {xls_path.name}: {e}")

    return video_lists


def resolve_intermediate_videos(check_in, check_out, video_list):
    """
    Given check-in and check-out video names, find all videos
    between them (inclusive) using the sorted Video_List.

    Returns list of video names, or [check_in] if resolution fails.
    """
    ci = str(check_in).strip()
    co = str(check_out).strip()

    # Same video → single video event
    if ci == co:
        return [ci]

    try:
        ci_idx = video_list.index(ci)
        co_idx = video_list.index(co)

        if ci_idx <= co_idx:
            return video_list[ci_idx : co_idx + 1]
        else:
            # Edge case: check-out before check-in in list
            return [ci, co]
    except ValueError:
        # Video not found in list
        return [ci, co] if ci != co else [ci]


# =====================================================================
# 3. BUILD ANNOTATIONS
# =====================================================================
def extract_hierarchy_labels(row, num_levels):
    """Extract L1...LN labels from reclassified columns."""
    path_values = []
    for col in HIERARCHY_COLS:
        if col in row.index:
            val = row[col]
            if pd.notna(val) and str(val).strip():
                path_values.append(str(val).strip())

    labels = {}
    for i in range(num_levels):
        level = f"L{i + 1}"
        labels[level] = path_values[i] if i < len(path_values) else None
    return labels


def build_annotations(hierarchy, video_lists):
    """Read reclassified CSVs and build video-based annotation entries."""

    # --- Load reclassified CSVs ---
    pattern = f"*_{config.VERSION_SUFFIX}.csv"
    csv_files = sorted(RECLASS_FOLDER.glob(pattern))
    if not csv_files:
        print(f"  [WARNING] No CSV files matching '{pattern}' in {RECLASS_FOLDER}")
        return []

    # --- First pass: collect all observations and count video usage ---
    all_observations = []

    for csv_file in csv_files:
        print(f"  Reading: {csv_file.name}")
        df = pd.read_csv(csv_file, sep=";", on_bad_lines="skip")

        if VIDEO_CHECK_IN not in df.columns:
            print(f"    [ERROR] Column '{VIDEO_CHECK_IN}' not found. Skipping.")
            continue

        # Match this CSV to its source Excel for Video_List resolution
        source_stem = csv_file.stem.replace(f"_{config.VERSION_SUFFIX}", "")
        video_list = video_lists.get(source_stem, [])
        if not video_list:
            print(
                f"    [WARN] No Video_List for '{source_stem}'."
                f" Intermediate videos won't be resolved."
            )

        for _, row in df.iterrows():
            ci = str(row.get(VIDEO_CHECK_IN, "")).strip()
            co = str(row.get(VIDEO_CHECK_OUT, ci)).strip()

            if ci in ["nan", "", "#N/C"]:
                continue

            all_videos = resolve_intermediate_videos(ci, co, video_list)
            labels = extract_hierarchy_labels(row, hierarchy["num_levels"])

            deepest_level = None
            deepest_class = None
            for lv in reversed(hierarchy["level_names"]):
                if labels.get(lv) is not None:
                    deepest_level = lv
                    deepest_class = labels[lv]
                    break

            if deepest_level is None:
                continue

            all_observations.append(
                {
                    "video_check_in": ci,
                    "video_check_out": co,
                    "videos": all_videos,
                    "labels": labels,
                    "deepest_level": deepest_level,
                    "deepest_class": deepest_class,
                    "source_file": csv_file.stem,
                }
            )

    # --- Second pass: discard multi-specimen videos ---
    # A video with >1 observation means multiple specimens were present
    checkin_counts = Counter(obs["video_check_in"] for obs in all_observations)
    multi_specimen_videos = {v for v, c in checkin_counts.items() if c > 1}

    samples = []
    discarded = 0
    for obs in all_observations:
        if obs["video_check_in"] in multi_specimen_videos:
            discarded += 1
            continue
        samples.append(obs)

    # --- Statistics ---
    print(f"\n{'=' * 50}")
    print(f"ANNOTATION STATISTICS")
    print(f"{'=' * 50}")
    print(f"  Total observations:           {len(all_observations)}")
    print(f"  Multi-specimen (discarded):    {discarded}")
    print(f"  Single-specimen (kept):        {len(samples)}")
    print(f"  Multi-specimen videos:         {len(multi_specimen_videos)}")

    level_counts = Counter(s["deepest_level"] for s in samples)
    for lv in sorted(level_counts.keys()):
        print(f"    Deepest at {lv}: {level_counts[lv]}")

    vid_counts = Counter(len(s["videos"]) for s in samples)
    print(f"  Videos per observation:")
    for n in sorted(vid_counts.keys()):
        print(f"    {n} video(s): {vid_counts[n]} observations")
    print(f"{'=' * 50}\n")

    return samples


# =====================================================================
# 4. MAIN
# =====================================================================
def main():
    print(f"\n{'=' * 60}")
    print(f"GENERATING TRAINING ANNOTATIONS")
    print(f"Master file: {config.MASTER_FILE}")
    print(f"Version: {config.VERSION_SUFFIX}")
    print(f"{'=' * 60}\n")

    # 1. Hierarchy
    print("[1/3] Loading master taxonomy...")
    hierarchy = load_master_taxonomy()
    print(f"  Hierarchy depth: {hierarchy['num_levels']} levels")
    for level, classes in hierarchy["classes_per_level"].items():
        print(f"    {level}: {len(classes)} classes")

    # 2. Video lists
    print(f"\n[2/3] Loading Video_Lists from /source_tables...")
    video_lists = load_all_video_lists()

    # 3. Annotations
    print(f"\n[3/3] Building annotations from /reclass...")
    samples = build_annotations(hierarchy, video_lists)

    # 4. Save single JSON
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    annotations = {
        "version": config.VERSION_SUFFIX,
        "hierarchy": hierarchy,
        "num_samples": len(samples),
        "samples": samples,
    }

    out_path = OUTPUT_FOLDER / f"annotations_{config.VERSION_SUFFIX}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Saved: {out_path}")
    print(f"  {len(samples)} annotated observations ready for training.")


if __name__ == "__main__":
    main()
