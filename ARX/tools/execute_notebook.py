from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main() -> None:
    notebook_path = Path("ARX_Model_Notebook.ipynb")
    nb = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=1200,
        kernel_name="python3",
        resources={"metadata": {"path": str(notebook_path.parent.resolve())}},
    )
    client.execute()
    nbformat.write(nb, notebook_path)
    print(f"Executed and saved {notebook_path.resolve()}")


if __name__ == "__main__":
    main()
