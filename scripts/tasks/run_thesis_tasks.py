import os

import helpers.static_files_fix as static_files_fix
from rich.console import Console
import collector.service as collector
from helpers.constants import Constants
from mono2micro import interface
from distutils.dir_util import copy_tree
from rich import print
import shutil


def main():
    """The sequence of methods below performs everything that is required to arrive at some values. These values are
    to be used in R or Plotly Express to perform comparisons between strategies.
    Assumptions:
    - the mono2micro system is running;
    """
    console = Console()

    # console.rule("Converting static files")
    # static_files_fix.correct_static_files()

    codebases_of_interest = static_files_fix.get_codebases_of_interest(Constants.codebases_root_directory)

    # console.rule("Running commit collection")
    # collector.collect_data(codebases_of_interest)

    # console.rule("Creating codebases in Mono2Micro")
    # interface.create_codebases(codebases_of_interest)

    console.rule("Running static analyser")
    interface.run_analyser(codebases_of_interest[1:])

    console.rule("Running commit analyser")
    interface.run_commit_analyser(codebases_of_interest[1:])


    # console.rule("Creating decompositions")
    # interface.create_decompositions(codebases_of_interest[:1])
    #
    # console.rule("Creating cuts")
    # interface.create_decompositions()

if __name__ == "__main__":
    main()
