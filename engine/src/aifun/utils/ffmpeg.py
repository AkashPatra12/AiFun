import subprocess


def run_ffmpeg(args: list[str]) -> None:
    """Run `ffmpeg -y -loglevel error <args>`, raising with stderr on failure.

    Shared by aifun.editing.* — the args list is just the filter/io flags,
    not the `ffmpeg` binary or the `-y`/`-loglevel` boilerplate.
    """
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr.strip()}")
