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
LEAF_COLUMN = "Classification class refined"
# Define the prefix to detect parent columns dynamically
PARENT_PREFIX = "Parent folder"


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


def load_master_leaves(master_path: Path) -> set:
    """
    Loads the Master Classification file to identify TRUE LEAVES.
    This prevents intermediate nodes (like 'Diptera') from being colored yellow
    just because they appear in the refined column due to fallback logic.
    """
    if not master_path.exists():
        print(
            f"[ERROR] Master file not found at {master_path}. Coloring might be inaccurate."
        )
        return set()

    try:
        df = pd.read_csv(master_path)
        # We assume the column containing the leaf names is 'Classification Class'
        # Adjust if your master file uses a different header
        target_col = config.MASTER_LEAF_COL

        if target_col not in df.columns:
            print(f"[ERROR] Column '{target_col}' not found in Master file.")
            return set()

        # Extract unique values, strip whitespace, ignore nan
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
    # Only load CSV files that match the current version suffix
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
            # Note: We use sep=';' because the previous script saves with semicolons
            temp_df = pd.read_csv(f, sep=";", on_bad_lines="skip")
            df_list.append(temp_df)
            print(f"  - Loaded: {f.name} ({len(temp_df)} rows)")
        except Exception as e:
            print(f"  [ERROR] Failed to load {f.name}: {e}")

    if not df_list:
        return pd.DataFrame()

    combined_df = pd.concat(df_list, ignore_index=True)
    return combined_df


def generate_graph(df: pd.DataFrame, output_path: Path, true_leaves: set):
    """
    Generates the Graphviz tree from the DataFrame.
    """
    print(f"\n[INFO] Generating graph structure...")

    # 1. Identify Parent Columns dynamically
    parent_cols = [c for c in df.columns if PARENT_PREFIX.lower() in c.lower()]

    # Sort them descending (Parent 6 -> Parent 1)
    try:
        parent_cols.sort(
            key=lambda x: int("".join(filter(str.isdigit, x))), reverse=True
        )
    except:
        print("[ERROR] Could not sort parent columns numerically. Check column names.")
        return

    print(f"  Detected hierarchy columns (General -> Specific): {parent_cols}")

    if LEAF_COLUMN not in df.columns:
        print(f"[ERROR] Leaf column '{LEAF_COLUMN}' not found in data.")
        return

    # 2. Build Paths and Count Occurrences
    node_counts = Counter()
    edges = set()

    # We maintain a set of ALL nodes encountered to iterate later
    all_encountered_nodes = set()

    for _, row in df.iterrows():
        # Construct the path for this row
        path_nodes = []

        # Add Parents
        for col in parent_cols:
            val = row[col]
            if is_valid_node(val):
                clean_val = str(val).strip()
                path_nodes.append(clean_val)
                all_encountered_nodes.add(clean_val)

        # Add Leaf (Refined Class)
        leaf_val = row[LEAF_COLUMN]
        if is_valid_node(leaf_val):
            clean_leaf = str(leaf_val).strip()
            path_nodes.append(clean_leaf)
            all_encountered_nodes.add(clean_leaf)

        # Update Counts and Edges
        if path_nodes:
            # We count specifically the ENDPOINT of this row
            endpoint = path_nodes[-1]
            node_counts[endpoint] += (
                1  # Count appearances as an endpoint (classification)
            )

            # Create edges: Node i -> Node i+1
            for i in range(len(path_nodes) - 1):
                parent = path_nodes[i]
                child = path_nodes[i + 1]
                edges.add((parent, child))

                # OPTIONAL: If you want n=X to represent flow through parents too:
                # node_counts[parent] += 1

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

        # Detect 1:1 relationships (parent has exactly 1 child AND child is a leaf)
        # BUT: Don't collapse if multiple parents converge to the same child
        for parent, children in parent_children.items():
            if len(children) == 1:
                child = children[0]
                # Check if this child is a leaf (true leaf from master file)
                if child in true_leaves:
                    # Check if this child has multiple parents (convergence)
                    num_parents = len(child_parents.get(child, []))

                    if num_parents > 1:
                        # Multiple parents converge to this leaf - DON'T collapse
                        print(
                            f"  - Skipping: {parent} → {child} (converges with {num_parents - 1} other parent(s))"
                        )
                        continue

                    # This is a true 1:1 alias relationship - safe to collapse
                    # Create combined label
                    if config.LABEL_FORMAT == "taxonomic_common":
                        combined_label = f"{parent} ({child})"
                    else:  # common_taxonomic
                        combined_label = f"{child} ({parent})"

                    collapsed_nodes[parent] = combined_label
                    collapsed_nodes[child] = combined_label

                    print(f"  - Collapsing: {parent} → {child} => {combined_label}")

        # Rebuild edges, skipping collapsed nodes
        new_edges = set()
        for parent, child in edges:
            # Check if either node is being collapsed
            if parent in collapsed_nodes and child in collapsed_nodes:
                # Both are part of the same collapsed pair - skip this edge
                continue
            elif parent in collapsed_nodes:
                # Parent is collapsed - use combined node
                new_edges.add((collapsed_nodes[parent], child))
            elif child in collapsed_nodes:
                # Child is collapsed - connect parent to combined node
                new_edges.add((parent, collapsed_nodes[child]))
            else:
                # Neither collapsed - keep original edge
                new_edges.add((parent, child))

        collapsed_edges = new_edges

        # Update all_encountered_nodes
        # Remove individual nodes that were collapsed and add combined nodes
        collapsed_set = set(collapsed_nodes.keys())
        all_encountered_nodes = (all_encountered_nodes - collapsed_set) | set(
            collapsed_nodes.values()
        )

        print(f"  Collapsed {len(collapsed_nodes) // 2} node pairs")

    # 3. Initialize Graph
    dot = graphviz.Digraph(comment="Taxonomy Tree")
    dot.attr(rankdir="LR")  # Left to Right orientation
    # Default style
    dot.attr(
        "node", shape="folder", style="filled", fontname="Arial", fillcolor="white"
    )

    # 4. Add Nodes with Coloring Logic
    for node in all_encountered_nodes:
        # Check if this is a collapsed combined node
        is_collapsed = (
            node in collapsed_nodes.values() if config.COLLAPSE_LEAF_ALIAS else False
        )

        # For collapsed nodes, sum counts from both original nodes
        if is_collapsed and config.COLLAPSE_LEAF_ALIAS:
            # Find the original nodes that were collapsed into this one
            original_nodes = [k for k, v in collapsed_nodes.items() if v == node]
            count = sum(node_counts.get(orig, 0) for orig in original_nodes)
        else:
            count = node_counts.get(node, 0)

        # --- COLOR LOGIC ---
        # Collapsed nodes or true leaves get yellow color
        if is_collapsed or node in true_leaves:
            fill_color = "#FFFF99"  # Light Yellow
            shape = "note"  # Use 'note' shape for files/leaves
        else:
            fill_color = "white"  # White
            shape = "folder"  # Use 'folder' shape for categories

        # Label
        label_text = clean_label(node)
        # Optional: Add count if > 0
        if count > 0:
            label_text += f"\n(n={count})"

        dot.node(node, label=label_text, fillcolor=fill_color, shape=shape)

    # 5. Add Edges
    for parent, child in collapsed_edges:  # Use collapsed_edges instead of edges
        dot.edge(parent, child, color="#555555")

    # 6. Save
    output_file = output_path / OUTPUT_FILENAME
    print(f"[INFO] Rendering to {output_file}.png...")

    try:
        dot.render(filename=str(output_file), format="png", cleanup=True)
        print(f"[SUCCESS] Graph saved successfully at: {output_file}.png")
    except Exception as e:
        print(f"[ERROR] Graphviz render failed: {e}")
        print(
            "Ensure Graphviz is installed on your system (not just the python library)."
        )


def main():
    script_dir = Path(HOME)
    input_path = script_dir / INPUT_FOLDER
    output_path = script_dir / OUTPUT_FOLDER
    master_path = script_dir / MASTER_FILE

    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"--- TAXONOMY TREE GENERATOR ---")
    print(f"Input Folder:  {input_path}")
    print(f"Output Folder: {output_path}")
    print(f"Master File:   {master_path}")

    # 1. Load Master Leaves (Authority)
    true_leaves = load_master_leaves(master_path)
    if not true_leaves:
        print(
            "[WARNING] Proceeding without leaf validation (Coloring will be default)."
        )

    # 2. Load Data
    df = load_and_combine_data(input_path)

    if df.empty:
        print("[ERROR] No data found to process. Exiting.")
        return

    # 3. Generate Graph
    generate_graph(df, output_path, true_leaves)


if __name__ == "__main__":
    main()
