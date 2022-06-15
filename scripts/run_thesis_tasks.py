import datetime
import json
import os
import time

import pandas as pd
import requests

from rich.console import Console
from distutils.dir_util import copy_tree
from rich import print
import shutil

from metrics import tsr
from mono2micro import interface
from mono2micro.interface import save_best_decompositions_from_static_analyser
from collector import service as collector
from helpers import static_files_fix
from helpers.constants import Constants


def single_cut(commit_weight, author_weight, clusters, codebase_name):
    r = requests.post(f'http://localhost:8080/mono2micro/codebase/{codebase_name}/{commit_weight}/{author_weight}/{clusters}/analyserCut')
    return r.status_code


def codebase_entities(codebase_name):
    with open(f"{Constants.codebases_data_output_directory}/{codebase_name}/{codebase_name}_IDToEntity.json", "r") as f:
        return len(json.load(f).keys())


def merge_analyser_csvs(codebases):
    dfs = []
    for codebase in codebases:
        print("Merging " + codebase)
        codebase_df = pd.read_csv(f"{Constants.codebases_data_output_directory}/{codebase}/all_static_decompositions_all_metrics.csv")
        codebase_df['codebase_name'] = codebase
        dfs.append(codebase_df)
    all_together = pd.concat(dfs)
    all_together.to_csv(f"{Constants.project_root}/resources/codebases_collection/max-complexities-analyser-result.csv", index=False)


def main():
    """The sequence of methods below performs everything that is required to arrive at some values. These values are
    to be used in R or Plotly Express to perform comparisons between strategies.
    Assumptions:
    - the mono2micro system is running;
    """
    console = Console()

    # console.rule("Converting static files")
    # static_files_fix.correct_static_files()
    console.rule("Grabbing codebases of interest...")
    codebases_of_interest = static_files_fix.get_codebases_of_interest(Constants.codebases_root_directory)
    codebases_of_interest.remove("fenixedu-academic")

    # console.rule("Running commit collection")
    # collector.collect_data(["fenixedu-academic"])
    # save_best_decompositions_from_static_analyser("fenixedu-academic")
    # codebases_of_interest = ["quizzes-tutor"]
    # # # If the codebases are already created... replace the files
    # console.rule("Copying files")
    # for i, codebase in enumerate(codebases_of_interest):
    #     print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases_of_interest)}]")
    #     shutil.copyfile(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_commit_all.json",
    #                     f"{Constants.mono2micro_codebases_root}/{codebase}_all/commitChanges.json")
    #     shutil.copyfile(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_author_all.json",
    #                     f"{Constants.mono2micro_codebases_root}/{codebase}_all/filesAuthors.json")
    #     shutil.copyfile(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_commit_entities.json",
    #                     f"{Constants.mono2micro_codebases_root}/{codebase}_entities/commitChanges.json")
    #     shutil.copyfile(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_author_entities.json",
    #                     f"{Constants.mono2micro_codebases_root}/{codebase}_entities/filesAuthors.json")

    # console.rule("Creating codebases in Mono2Micro")
    # codebases_of_interest = ["fenixedu-academic"]
    # interface.create_codebases(codebases_of_interest)
    # console.rule("Running static analyser")
    # print("Total: " + str(len(codebases_of_interest)))
    # t0 = time.time()
    # interface.run_analyser(codebases_of_interest)
    # t1 = time.time()
    # print(f"Total time: {datetime.timedelta(t1-t0)}")
    #

    # # console.rule("Merging csvs")
    # for codebase in codebases_of_interest:
    #     print("Saving decompositions from " + codebase)
    #     save_best_decompositions_from_static_analyser(codebase)
    # merge_analyser_csvs(codebases_of_interest)

    console.rule("Getting tsr")
    tsr_data = tsr.get_data(codebases_of_interest)



if __name__ == "__main__":
    main()
