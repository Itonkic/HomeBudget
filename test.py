import os
from pathlib import Path

def print_tree(start_path: str, prefix: str = ""):
    # Get sorted list of items (directories first)
    items = sorted(Path(start_path).iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    pointers = ["├── "] * (len(items) - 1) + ["└── "]

    for pointer, path in zip(pointers, items):
        print(prefix + pointer + path.name)
        if path.is_dir():
            extension = "│   " if pointer == "├── " else "    "
            print_tree(path, prefix + extension)

if __name__ == "__main__":
    root = Path(__file__).parent
    print(root.name + "/")
    print("│")
    print_tree(root)
