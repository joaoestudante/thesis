import datetime
import glob
import json
import os
import time
import csv

import pandas as pd
import requests

from rich.console import Console
from distutils.dir_util import copy_tree
from rich import print
import shutil

from metrics import tsr
from mono2micro import interface
from mono2micro.interface import convert_analyser_result, parse_analyser_result
from collector import service as collector
from helpers import static_files_fix
from helpers.constants import Constants
import collector.functionalitysplit as fsplit


def single_cut(commit_weight, author_weight, clusters, codebase_name):
    r = requests.post(f'http://localhost:8080/mono2micro/codebase/{codebase_name}/{commit_weight}/{author_weight}/{clusters}/analyserCut')
    return r.status_code


def codebase_entities(codebase_name):
    with open(f"{Constants.codebases_data_output_directory}/{codebase_name}/{codebase_name}_IDToEntity.json", "r") as f:
        return len(json.load(f).keys())


def merge_analyser_csvs(codebases):
    dfs = []
    for codebase_data in codebases:
        codebase = codebase_data[0]
        print("Merging " + codebase)
        codebase_df = pd.read_csv(f"{Constants.codebases_data_output_directory}/{codebase}/analyserResult.csv")
        codebase_df['codebase_name'] = codebase
        dfs.append(codebase_df)
    all_together = pd.concat(dfs)
    all_together.to_csv(f"{Constants.project_root}/resources/codebases_collection/analyserCompilationCorrectMetrics.csv", index=False)


def convert_single_analyser_json(mono2micro_codebase_name, codebase_name):
    with open(f"{Constants.mono2micro_codebases_root}/{mono2micro_codebase_name}/analyser/analyserResult.json", "r") as f:
        analyser_result = parse_analyser_result(json.load(f))
    max_complexity = analyser_result['complexity'].max()
    if max_complexity != 0:
        analyser_result['pondered_complexity'] = analyser_result['complexity'] / max_complexity
        analyser_result = analyser_result.loc[analyser_result['complexity'] != max_complexity]
    else:
        analyser_result['pondered_complexity'] = 0
    analyser_result.to_csv(
        f"{Constants.codebases_data_output_directory}/{codebase_name}-analyser.csv",
        index=False)



def main():
    """The sequence of methods below performs everything that is required to arrive at some values. These values are
    to be used in R or Plotly Express to perform comparisons between strategies.
    Assumptions:
    - the mono2micro system is running;
    """
    console = Console()

    codebases = []
    blacklist = ["blended-workflow", "fenixedu-academic", "edition"]
    with open(f"{Constants.resources_directory}/codebases.csv", "r") as c:
        reader = csv.reader(c)
        next(reader)
        codebases = [row for row in reader]
    codebases = [c for c in codebases if c[0] not in blacklist]
    #
    # console.rule("Running commit collection")
    # force_recollection = True
    # collector.collect_data(codebases, force_recollection)
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

    # console.rule("Converting static files to functionality split")
    # fsplit.collect(codebases_of_interest)
    #
    # console.rule("Creating codebases in Mono2Micro")
    # # # codebases_of_interest = ["fenixedu-academic"]
    # interface.create_codebases(codebases, "")
    # console.rule("Running static analyser")
    # # print("Total: " + str(len(codebases_of_interest[8:])))
    # t0 = time.time()
    # interface.run_analyser(codebases, "")
    # t1 = time.time()
    # print(f"Total time: {datetime.timedelta(t1-t0)}")
    # # #
    # #
    # console.rule("Merging csvs")
    # merge_analyser_csvs(codebases)

    console.rule("Getting tsr")
    tsr_data = tsr.get_data(codebases)

    # TODO: fazer um método para processar um analyser em especifico...

    # convert_single_analyser_json("cloudunit", "cloudunit")


if __name__ == "__main__":
    main()
