import helpers.static_files_fix as static_files_fix
from rich.console import Console
from collector.service import CommitCollectorService
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
    collector_service = CommitCollectorService(
        static_files_fix.get_codebases_of_interest(Constants.codebases_root_directory))

    collector_service.collect_data()

if __name__ == "__main__":
    main()
