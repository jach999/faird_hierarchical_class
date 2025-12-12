import pandas as pd
import graphviz
from pathlib import Path
import os
from collections import Counter
import config

# --- CONFIGURATION ---
HOME = os.path.dirname(__file__)
INPUT_FOLDER = "reclass"  # Read from versioned files
OUTPUT_FOLDER = "scheme"  # Save versioned file
OUTPUT_FILENAME = f"taxonomy_tree_{config.VERSION_SUFFIX}"  # Versioned output file
MASTER_FILE = config.MASTER_FILE  # The authority on what is a true leaf

# Define the Leaf Column name in the input files
LEAF_COLUMN = "Leaf_reclass"

# Master file hierarchy columns (without _reclass suffix)
MASTER_HIERARCHY = ["Class", "Order", "Suborder", "Infraorder", "Superfamily", "Family"]


def is_valid_node(val) -> bool:
    """
    Checks if a node value is valid for the graph.
    Ignores: #N/C, 0, nan, empty strings.
    """
    if pd.isna(val):
        return False
    s = str(val).strip()
    if not s:
        return False
    if s.upper() == "#N/C":
        return False
    if s == "0":
        return False
    return True


def clean_label(value):
    """
    Truncates long labels for better visualization.
    """
    s = str(value).strip()
    if len(s) > 25:
        return s[:22] + "..."
    return s


def build_master_paths_map(master_path: Path) -> dict:
    """
    Builds a comprehensive map of ALL taxonomic nodes to their complete paths.
    This ensures we use the master file's hierarchy, not the potentially incomplete
    reclassified data.

    Returns:
        dict: {taxon_name: [path_from_root_to_taxon]}

    Example:
        "muscoid_fly": ["Insecta", "Diptera", "Brachycera", "Muscomorpha", "Muscoidea", "muscoid_fly"]
        "Muscoidea": ["Insecta", "Diptera", "Brachycera", "Muscomorpha", "Muscoidea"]
        "Muscomorpha": ["Insecta", "Diptera", "Brachycera", "Muscomorpha"]
    """
    if not master_path.exists():
        print(f"[ERROR] Master file not found at {master_path}")
        return {}

    try:
        master_df = pd.read_csv(master_path)
        paths_map = {}

        print(f"[INFO] Building master taxonomy paths map from {master_path.name}...")

        for _, row in master_df.iterrows():
            # Build the full path for this taxonomy line
            full_path = []

            # Add each level from general to specific
            for level in MASTER_HIERARCHY:
                if level in master_df.columns:
                    val = row[level]
                    if is_valid_node(val):
                        full_path.append(str(val).strip())

            # Add leaf if present
            if config.MASTER_LEAF_COL in master_df.columns:
                leaf = row[config.MASTER_LEAF_COL]
                if is_valid_node(leaf):
                    full_path.append(str(leaf).strip())

            # Now store the path for each taxon in this lineage
            # Example: if path is [A, B, C, D], store:
            # A: [A]
            # B: [A, B]
            # C: [A, B, C]
            # D: [A, B, C, D]
            for i in range(len(full_path)):
                taxon = full_path[i]
                taxon_path = full_path[: i + 1]

                # Only store if not already present (avoid overwrites)
                # For convergent taxonomies (same common name, different parents),
                # we keep the first occurrence
                if taxon not in paths_map:
                    paths_map[taxon] = taxon_path

        print(f"  Built paths for {len(paths_map)} unique taxonomic nodes")
        return paths_map

    except Exception as e:
        print(f"[ERROR] Failed to build master paths map: {e}")
        return {}


def load_master_leaves(master_path: Path) -> set:
    """
    Loads the Master Classification file to identify TRUE LEAVES.
    """
    if not master_path.exists():
        print(f"[ERROR] Master file not found at {master_path}")
        return set()

    try:
        df = pd.read_csv(master_path)
        target_col = config.MASTER_LEAF_COL

        if target_col not in df.columns:
            print(f"[ERROR] Column '{target_col}' not found in Master file.")
            return set()

        leaves = set(df[target_col].dropna().astype(str).str.strip())
        print(f"[INFO] Loaded {len(leaves)} true leaf categories from Master file.")
        return leaves

    except Exception as e:
        print(f"[ERROR] Failed to load Master file: {e}")
        return set()


def load_and_combine_data(input_path: Path) -> pd.DataFrame:
    """
    Iterates through all CSV files in the input folder and combines them
    into a single DataFrame.
    """
    all_files = sorted(
        [
            f
            for f in input_path.glob("*.csv")
            if f.stem.endswith(f"_{config.VERSION_SUFFIX}")
        ]
    )

    if not all_files:
        print(f"[WARNING] No CSV files found in '{input_path.name}' folder.")
        return pd.DataFrame()

    print(
        f"[INFO] Found {len(all_files)} CSV files in /{input_path.name}. Combining data..."
    )

    df_list = []
    for f in all_files:
        try:
            temp_df = pd.read_csv(f, sep=";", on_bad_lines="skip")
            df_list.append(temp_df)
            print(f"  - Loaded: {f.name} ({len(temp_df)} rows)")
        except Exception as e:
            print(f"  [ERROR] Failed to load {f.name}: {e}")

    if not df_list:
        return pd.DataFrame()

    combined_df = pd.concat(df_list, ignore_index=True)
    return combined_df


def generate_graph(
    df: pd.DataFrame,
    output_path: Path,
    true_leaves: set,
    master_paths_map: dict,
    mode: str = "endpoint",
    suffix: str = "",
):
    """
    Generates the Graphviz tree from the DataFrame using master file paths.

    CRITICAL FIX: Uses master_paths_map to construct complete hierarchical paths,
    ensuring no levels are skipped even if they're NaN in the reclassified data.

    Args:
        master_paths_map: dict mapping taxon names to their complete paths from master file
        mode: "endpoint" (counts only final classifications) or "cumulative" (counts all flow-through)
        suffix: suffix to add to output filename (e.g., "_cml")
    """
    print(f"\n[INFO] Generating graph structure ({mode} mode)...")

    # Define hierarchy columns (General -> Specific)
    hierarchy_cols = [
        "Class_reclass",
        "Order_reclass",
        "Suborder_reclass",
        "Infraorder_reclass",
        "Superfamily_reclass",
        "Family_reclass",
    ]

    # Verify columns exist
    missing_cols = [col for col in hierarchy_cols if col not in df.columns]
    if missing_cols:
        print(f"[ERROR] Missing hierarchy columns: {missing_cols}")
        return

    if LEAF_COLUMN not in df.columns:
        print(f"[ERROR] Leaf column '{LEAF_COLUMN}' not found in data.")
        return

    print(f"  Using master file to reconstruct complete hierarchical paths")

    # 2. Build Paths and Count Occurrences
    node_counts = Counter()
    node_cumulative_counts = Counter()
    edges = set()
    all_encountered_nodes = set()

    # Track warnings
    missing_taxa_warnings = set()

    for _, row in df.iterrows():
        # CRITICAL FIX: Find the most specific classification for this row
        # Check from most specific (Leaf) to most general (Class)
        most_specific_taxon = None

        # First check Leaf
        if is_valid_node(row[LEAF_COLUMN]):
            most_specific_taxon = str(row[LEAF_COLUMN]).strip()
        else:
            # Check hierarchy levels from most to least specific
            for col in reversed(hierarchy_cols):
                if is_valid_node(row[col]):
                    most_specific_taxon = str(row[col]).strip()
                    break

        if not most_specific_taxon:
            continue  # Skip rows with no classification

        # NEW: Look up the complete path from master file
        if most_specific_taxon in master_paths_map:
            path_nodes = master_paths_map[most_specific_taxon].copy()
        else:
            # Taxon not found in master - this shouldn't happen with correct reclassification
            # But handle gracefully
            if most_specific_taxon not in missing_taxa_warnings:
                print(
                    f"  [WARNING] Taxon '{most_specific_taxon}' not found in master file"
                )
                missing_taxa_warnings.add(most_specific_taxon)
            # Fallback: use whatever values we have (old behavior)
            path_nodes = []
            for col in hierarchy_cols:
                val = row[col]
                if is_valid_node(val):
                    path_nodes.append(str(val).strip())
            if is_valid_node(row[LEAF_COLUMN]):
                path_nodes.append(str(row[LEAF_COLUMN]).strip())

        # Add all nodes in path to encountered set
        for node in path_nodes:
            all_encountered_nodes.add(node)

        # Update Counts and Edges
        if path_nodes:
            # ENDPOINT COUNT: Only count the final node
            endpoint = path_nodes[-1]
            node_counts[endpoint] += 1

            # CUMULATIVE COUNT: Count all nodes in path (flow-through)
            for node in path_nodes:
                node_cumulative_counts[node] += 1

            # Create edges: Node i -> Node i+1
            for i in range(len(path_nodes) - 1):
                parent = path_nodes[i]
                child = path_nodes[i + 1]
                edges.add((parent, child))

    # 2.5. Collapse 1:1 parent-leaf relationships if enabled
    collapsed_nodes = {}  # Maps: parent -> combined_node_name
    collapsed_edges = set(edges)  # Start with original edges

    if config.COLLAPSE_LEAF_ALIAS:
        print(f"[INFO] Detecting and collapsing 1:1 parent-leaf relationships...")

        # Count children for each parent
        parent_children = {}
        for parent, child in edges:
            if parent not in parent_children:
                parent_children[parent] = []
            parent_children[parent].append(child)

        # Count parents for each child (detect convergence)
        child_parents = {}
        for parent, child in edges:
            if child not in child_parents:
                child_parents[child] = []
            child_parents[child].append(parent)

        # Detect 1:1 relationships
        for parent, children in parent_children.items():
            if len(children) == 1:
                child = children[0]
                if child in true_leaves:
                    num_parents = len(child_parents.get(child, []))

                    if num_parents > 1:
                        print(
                            f"  - Skipping: {parent} → {child} (converges with {num_parents - 1} other parent(s))"
                        )
                        continue

                    # Create combined label
                    if config.LABEL_FORMAT == "taxonomic_common":
                        combined_label = f"{parent} ({child})"
                    else:
                        combined_label = f"{child} ({parent})"

                    collapsed_nodes[parent] = combined_label
                    collapsed_nodes[child] = combined_label

                    print(f"  - Collapsing: {parent} → {child} => {combined_label}")

        # Rebuild edges
        new_edges = set()
        for parent, child in edges:
            if parent in collapsed_nodes and child in collapsed_nodes:
                continue
            elif parent in collapsed_nodes:
                new_edges.add((collapsed_nodes[parent], child))
            elif child in collapsed_nodes:
                new_edges.add((parent, collapsed_nodes[child]))
            else:
                new_edges.add((parent, child))

        collapsed_edges = new_edges

        # Update all_encountered_nodes
        collapsed_set = set(collapsed_nodes.keys())
        all_encountered_nodes = (all_encountered_nodes - collapsed_set) | set(
            collapsed_nodes.values()
        )

        print(f"  Collapsed {len(collapsed_nodes) // 2} node pairs")

    # 3. Initialize Graph
    dot = graphviz.Digraph(comment="Taxonomy Tree")
    dot.attr(rankdir="LR")
    dot.attr(
        "node", shape="folder", style="filled", fontname="Arial", fillcolor="white"
    )

    # 4. Add Nodes
    for node in sorted(all_encountered_nodes):
        is_collapsed = (
            node in collapsed_nodes.values() if config.COLLAPSE_LEAF_ALIAS else False
        )

        if is_collapsed and config.COLLAPSE_LEAF_ALIAS:
            original_nodes = [k for k, v in collapsed_nodes.items() if v == node]
            if mode == "cumulative":
                count = sum(
                    node_cumulative_counts.get(orig, 0) for orig in original_nodes
                )
            else:
                count = sum(node_counts.get(orig, 0) for orig in original_nodes)
        else:
            if mode == "cumulative":
                count = node_cumulative_counts.get(node, 0)
            else:
                count = node_counts.get(node, 0)

        # COLOR LOGIC
        if is_collapsed or node in true_leaves:
            fill_color = "#FFFF99"
            shape = "note"
        else:
            fill_color = "white"
            shape = "folder"

        label_text = clean_label(node)
        if count > 0:
            label_text += f"\n(n={count})"

        dot.node(node, label=label_text, fillcolor=fill_color, shape=shape)

    # 5. Add Edges
    for parent, child in sorted(collapsed_edges):
        dot.edge(parent, child, color="#555555")

    # 6. Save
    output_file = output_path / f"{OUTPUT_FILENAME}{suffix}"
    print(f"[INFO] Rendering to {output_file}.png...")

    try:
        dot.render(filename=str(output_file), format="png", cleanup=True)
        print(f"[SUCCESS] Graph saved successfully at: {output_file}.png")
    except Exception as e:
        print(f"[ERROR] Graphviz render failed: {e}")


def main():
    script_dir = Path(HOME)
    input_path = script_dir / INPUT_FOLDER
    output_path = script_dir / OUTPUT_FOLDER
    master_path = script_dir / MASTER_FILE

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"--- TAXONOMY TREE GENERATOR ---")
    print(f"Input Folder:  {input_path}")
    print(f"Output Folder: {output_path}")
    print(f"Master File:   {master_path}")

    # 1. Build master paths map (CRITICAL!)
    master_paths_map = build_master_paths_map(master_path)
    if not master_paths_map:
        print("[ERROR] Failed to build master paths map. Cannot continue.")
        return

    # 2. Load Master Leaves (for coloring)
    true_leaves = load_master_leaves(master_path)

    # 3. Load Data
    df = load_and_combine_data(input_path)

    if df.empty:
        print("[ERROR] No data found to process. Exiting.")
        return

    # 4. Generate Graphs (both versions)
    print("\n" + "=" * 60)
    print("GENERATING ENDPOINT VERSION (counts only final classifications)")
    print("=" * 60)
    generate_graph(
        df, output_path, true_leaves, master_paths_map, mode="endpoint", suffix=""
    )

    print("\n" + "=" * 60)
    print("GENERATING CUMULATIVE VERSION (counts all flow-through)")
    print("=" * 60)
    generate_graph(
        df, output_path, true_leaves, master_paths_map, mode="cumulative", suffix="_cml"
    )


if __name__ == "__main__":
    main()
