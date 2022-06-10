import datetime
import json
import os
import time

import pandas as pd
import requests
import statsmodels.api as sm

import helpers.static_files_fix as static_files_fix
from rich.console import Console
import collector.service as collector
from helpers.constants import Constants
from mono2micro import interface
from distutils.dir_util import copy_tree
from rich import print
import shutil

from mono2micro.interface import save_best_decompositions_from_static_analyser


def single_cut(commit_weight, author_weight, clusters, codebase_name):
    r = requests.post(f'http://localhost:8080/mono2micro/codebase/{codebase_name}/{commit_weight}/{author_weight}/{clusters}/analyserCut')
    return r.status_code


def combinations():
    interval = 10
    combinations = []
    for a in range(interval, -1, -1):
        remainder = interval - a
        if remainder == 0:
            print(f"access={a}, write=0, read=0, sequence=0, commit=0, author=0")
            combinations.append((a, 0, 0, 0, 0))
            #sendRequest(a, 0, 0, 0, False, totalNumberOfEntities, codebase, entities, linkageType)
        else:
            for w in range(remainder, -1, -1):
                remainder2 = remainder - w
                if remainder2 == 0:
                    print(f"access={a}, write={w}, read=0, sequence=0, commit=0, author=0")
                    combinations.append((a, w, 0, 0, 0, 0))
                else:
                    for r in range(remainder2, -1, -1):
                        remainder3 = remainder2 - r
                        if remainder3 == 0:
                            print(f"access={a}, write={w}, read={r}, sequence=0, commit=0, author=0")
                            combinations.append((a, w, r, 0, 0))
                        else:
                            for s in range(remainder3, -1, -1):
                                remainder4 = remainder3 - s
                                if remainder4 == 0:
                                    print(f"access={a}, write={w}, read={r}, sequence={s}, commit=0, author=0")
                                    combinations.append((a, w, r, s, 0, 0))
                                else:
                                    for c in range(remainder4, -1, -1):
                                        remainder5 = remainder4 - c
                                        if remainder5 == 0:
                                            print(f"access={a}, write={w}, read={r}, sequence={s}, commit={c}, author=0")
                                            combinations.append((a, w, r, s, c, 0))
                                        else:
                                            print(f"access={a}, write={w}, read={r}, sequence={s}, commit={c}, author={remainder5}")
                                            combinations.append((a, w, r, s, c, remainder5))

    print(f"Total combinations: {len(combinations)}")


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
    all_together.to_csv(f"{Constants.project_root}/resources/codebases_collection/giga-analyser-result.csv", index=False)

def run_ols():
    df = {
    }
    all_results = pd.read_csv(f"{Constants.project_root}/resources/codebases_collection/giga-analyser-result.csv")
    # only_static = all_results.loc[(all_results["commit"] == 0) & (all_results["static"] == 0),]
    df['A'] = list(all_results["access"])
    df['W'] = list(all_results["write"])
    df['R'] = list(all_results["read"])
    df['S'] = list(all_results["sequence"])
    df['C'] = list(all_results["commit"])
    df['AU'] = list(all_results["authors"])
    df['n'] = list(all_results["clusters"])
    df['cohesion'] = list(all_results["cohesion"])
    df['coupling'] = list(all_results["coupling"])
    df['complexity'] = list(all_results["pondered_complexity"])
    # for entry in all_results.values:
    #     df['A'].append(entry[0])
    #     df['W'].append(entry[1])
    #     df['R'].append(entry[2])
    #     df['S'].append(entry[3])
    #     df['C'].append(entry[4])
    #     df['AU'].append(entry[5])
    #     df['n'].append(entry[6])
    #     df['cohesion'].append(entry[7])
    #     df['coupling'].append(entry[8])
    #     df['complexity'].append(entry[10])
    df = pd.DataFrame(df)

    X = df.loc[:, ['n', 'A', 'W', 'R', 'S', 'C', 'AU']]
    y = df.loc[:, 'complexity']
    X = sm.add_constant(X)
    model = sm.OLS(y, X)
    results = model.fit()
    print(results.summary())
    print()



def main():
    """The sequence of methods below performs everything that is required to arrive at some values. These values are
    to be used in R or Plotly Express to perform comparisons between strategies.
    Assumptions:
    - the mono2micro system is running;
    """
    console = Console()

    # console.rule("Converting static files")
    # static_files_fix.correct_static_files()

    # codebases_of_interest = static_files_fix.get_codebases_of_interest(Constants.codebases_root_directory)

    # console.rule("Running commit collection")
    collector.collect_data(["fenixedu-academic"])
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
    # interface.create_codebases(codebases_of_interest)

    # console.rule("Running static analyser")
    # print("Total: " + str(len(codebases_to_consider)))
    # t0 = time.time()
    # interface.run_analyser(["fenixedu-academic"])
    # t1 = time.time()
    # print(f"Total time: {datetime.timedelta(t1-t0)}")
    #
    # console.rule("Merging csvs")
    # # for codebase in codebases_of_interest:
    # #     print("Saving decompositions from " + codebase)
    # #     save_best_decompositions_from_static_analyser(codebase)
    # merge_analyser_csvs(codebases_of_interest)
    # run_ols()



if __name__ == "__main__":
    main()
