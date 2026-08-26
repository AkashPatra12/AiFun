import typer

app = typer.Typer(help="AiFun - Auto Reel/Shorts Generator")


@app.command()
def process(input_path: str, output_dir: str = "data/output"):
    """Turn a long-form video into one or more short-form clips."""
    from aifun.pipeline import run_pipeline

    run_pipeline(input_path, output_dir)


if __name__ == "__main__":
    app()
