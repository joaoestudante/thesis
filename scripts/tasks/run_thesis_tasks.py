import helpers.static_files_fix as static_files_fix
from rich.console import Console
import collector.service as collector
from helpers.constants import Constants


def main():
    """The sequence of methods below performs everything that is required to arrive at some values. These values are
    to be used in R or Plotly Express to perform comparisons between strategies.
    Assumptions:
    - the mono2micro system is running;
    """
    console = Console()

    # console.rule("Converting static files")
    # static_files_fix.correct_static_files()

    console.rule("Running commit collection")
    collector.collect_data(static_files_fix.get_codebases_of_interest(Constants.codebases_root_directory))

    console.rule("Creating codebases in Mono2Micro")

if __name__ == "__main__":
    main()
