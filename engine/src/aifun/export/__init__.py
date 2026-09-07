import shutil
from pathlib import Path


def export_clip(rendered_path: str, output_dir: str, filename: str) -> str:
    """Copy the rendered clip into output_dir under its final filename."""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    final_path = output_dir_path / filename
    shutil.copyfile(rendered_path, final_path)
    return str(final_path)
