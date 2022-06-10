import json
import time
from datetime import datetime

import pandas as pd
from rich import print
import requests
from distutils.dir_util import copy_tree

from helpers.constants import Constants


class Mono2MicroRequests:
    def __init__(self):
        self.base_url = "http://localhost:8080/mono2micro"
        self.analyser_url = self.base_url + "/codebase/{}/analyser"
        self.create_cut_url = self.base_url + "/codebase/{}/dendrogram/{}/cut"
        self.create_codebase_url = self.base_url + "/codebase/create"
        self.commit_analyser_url = self.base_url + "/codebase/{}/commitAnalyser"
        self.create_dendrogram_url = self.base_url + "/codebase/{}/dendrogram/create"

    def do_create_codebase(self, codebase_name, codebase_suffix):
        data = {
            'codebaseName': codebase_name + "_" + codebase_suffix
        }
        codebases_path = Constants.codebases_data_output_directory
        files = {
            'datafile': open(f"{codebases_path}/{codebase_name}/{codebase_name}.json"),
            'translationFile': open(f"{codebases_path}/{codebase_name}/{codebase_name}_IDToEntity.json"),
            'commitFile': open(f"{codebases_path}/{codebase_name}/{codebase_name}_commit_{codebase_suffix}.json"),
            'authorFile': open(f"{codebases_path}/{codebase_name}/{codebase_name}_author_{codebase_suffix}.json")
        }
        r = requests.post(self.create_codebase_url, files=files, data=data)
        return r.status_code

    def do_analyse(self, codebase):
        data = {
            "expert": {},
            "profile": "Generic",
            "requestLimit": 0,
            "traceType": 0,
            "tracesMaxLimit": 0,
        }
        r = requests.post(self.analyser_url.format(codebase + "_all"), json=data)
        return r.status_code

    def do_commit_analyse(self, codebase, suffix):
        r = requests.post(self.commit_analyser_url.format(codebase + suffix))
        return r.status_code

    def do_create_dendrogram(self, codebase, base, access, write, read, sequence, commit, author, n_clusters):
        if base == "STATIC":
            dendrogram_name = f"{access},{write},{read},{sequence},{n_clusters}"
        else:
            dendrogram_name = "commit"

        data = {
            "codebaseName": codebase,
            "name": dendrogram_name,
            "base": base,
            "linkageType": "average",
            "accessMetricWeight": access,
            "writeMetricWeight": write,
            "readMetricWeight": read,
            "sequenceMetricWeight": sequence,
            "commitMetricWeight": commit,
            "authorMetricWeiht": author,
            "profile": "Generic",
            "tracesMaxLimit": 0,
            "traceType": "ALL"
        }
        r = requests.post(url=self.create_dendrogram_url.format(codebase), json=data)
        return r.status_code

    def do_create_cut(self, codebase, base, access, write, read, sequence, n_clusters):
        if base == "STATIC":
            dendrogram_name = f"{access},{write},{read},{sequence},{n_clusters}"
        else:
            dendrogram_name = "commit"
        data = {
            "codebaseName": codebase,
            "dendrogramName": dendrogram_name,
            "expert": False,
            "cutValue": n_clusters,
            "cutType": "N"
        }
        r = requests.post(url=self.create_cut_url.format(codebase, dendrogram_name), json=data)
        return r.status_code


def create_codebases(codebases):
    mono2micro = Mono2MicroRequests()

    for i, codebase in enumerate(codebases):
        print("")
        print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases)}]")

        print(":white_circle: Creating codebase for all files... ", end="")
        all_files_result = mono2micro.do_create_codebase(codebase, "all")
        if all_files_result == 201:
            print("[green]Success.[/green]")
        else:
            print(f"[red]Error (code = {all_files_result}). Aborting. [/red]")
            break

        print(":white_circle: Creating codebase for entities only... ", end="")
        entities_result = mono2micro.do_create_codebase(codebase, "entities")
        if entities_result == 201:
            print("[green]Success.[/green]")
        else:
            print(f"[red]Error (code = {all_files_result}). Aborting. [/red]")
            break


def parse_analyser_result(file):
    result = []
    for cut in file:
        access_weight = file[cut]["accessWeight"]
        write_weight = file[cut]["writeWeight"]
        read_weight = file[cut]["readWeight"]
        sequence_weight = file[cut]["sequenceWeight"]
        commit_weight = file[cut]["commitWeight"]
        authors_weight = file[cut]["authorsWeight"]
        n_clusters = int(file[cut]["numberClusters"])
        cohesion = file[cut]["cohesion"]
        coupling = file[cut]["coupling"]
        complexity = file[cut]["complexity"]
        result.append([access_weight, write_weight, read_weight, sequence_weight, commit_weight, authors_weight,
                       n_clusters, cohesion, coupling, complexity])

    return pd.DataFrame(result, columns=['access', 'write', 'read', 'sequence', 'commit', 'authors',
                                         'clusters', 'cohesion', 'coupling', 'complexity'])


def get_best_cuts(analyser_result):
    best_cuts = []
    decomposition_by_n_clusters = analyser_result.groupby('clusters')
    for cluster, cluster_amount in decomposition_by_n_clusters:
        if int(str(cluster)) > 10:
            break
        minimum_complexity = cluster_amount.loc[
            cluster_amount['complexity'] == cluster_amount['complexity'].min()].head(1)
        best_cuts.append((float(minimum_complexity['access']),
                          float(minimum_complexity['write']),
                          float(minimum_complexity['read']),
                          float(minimum_complexity['sequence']),
                          int(minimum_complexity['clusters'])))
    return best_cuts


def create_decompositions(codebases):
    mono2micro = Mono2MicroRequests()

    def create(cuts, suffix):
        print(f":white_circle: Creating dendrogram for commit, suffix:{suffix}")
        mono2micro.do_create_dendrogram(codebase + suffix, "COMMIT", 25, 25, 25, 25, 100, 0, -1)
        for cut in cuts:
            # mono2micro.do_create_dendrogram(codebase, "STATIC", cut[0], cut[1], cut[2], cut[3], 50, 50, cut[4])
            print(f":white_circle: Performing cut with {cut[4]} clusters. ", end="")
            result = mono2micro.do_create_cut(codebase + suffix, "COMMIT", cut[0], cut[1], cut[2], cut[3], cut[4])
            if result == 201:
                print("[green]Success.[/green]")
            else:
                print(f"[red]Error. (code {result})")

    for i, codebase in enumerate(codebases):
        print("")
        print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases)}]")

        try:
            with open(f"{Constants.mono2micro_codebases_root}/{codebase}_all/analyser/analyserResult.json", "r") as f:
                analyser_result = parse_analyser_result(json.load(f))
        except FileNotFoundError:
            print(
                f"[red]Analyser file not found at {Constants.mono2micro_codebases_root}/{codebase}_all/analyser/analyserResult.json.[/red]")
            break

        max_complexity = analyser_result['complexity'].max()
        analyser_result['pondered_complexity'] = analyser_result['complexity'] / max_complexity
        best_cuts = get_best_cuts(analyser_result)

        create(best_cuts, "all")
        create(best_cuts, "entities")


def run_analyser(codebases):
    mono2micro = Mono2MicroRequests()

    for i, codebase in enumerate(codebases):
        print("")
        print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases)}]")

        # Run the analyser for the first type (all files)
        print(f":white_circle: ({datetime.now().strftime('%H:%M:%S')}) Running... ", end="")
        result = mono2micro.do_analyse(codebase)
        if result == 200:
            print(f"[green]Success.[/green] Finished at {datetime.now().strftime('%H:%M:%S')}")
        else:
            print(f"[red]Error (code = {result}). Aborting. [/red]")
            break

        # Copy the result into the other type (entities) - analyser is based on static analysis, so there are no
        # differences between both types.
        # copy_tree(f"{Constants.mono2micro_codebases_root}/{codebase}_all/analyser",
        #           f"{Constants.mono2micro_codebases_root}/{codebase}_entities/analyser")

        print(f":white_circle: Converting result to .csv")
        save_best_decompositions_from_static_analyser(codebase)


def save_best_decompositions_from_static_analyser(codebase):
    with open(f"{Constants.mono2micro_codebases_root}/{codebase}_all/analyser/analyserResult5Cutoff.json", "r") as f:
        analyser_result = parse_analyser_result(json.load(f))
    max_complexity = analyser_result['complexity'].max()
    if max_complexity != 0:
        analyser_result['pondered_complexity'] = analyser_result['complexity'] / max_complexity
        analyser_result = analyser_result.loc[analyser_result['complexity'] != max_complexity]
    else:
        analyser_result['pondered_complexity'] = 0
    # decomposition_by_n_clusters = analyser_result.groupby('clusters')
    # best_decompositions = []
    # for cluster, cluster_amount in decomposition_by_n_clusters:
    #     if int(str(cluster)) > 10:
    #         break
    #     minimum_complexity = cluster_amount.loc[
    #         cluster_amount['complexity'] == cluster_amount['complexity'].min()].head(1)
    #     best_decompositions.append((float(minimum_complexity['access']),
    #                                 float(minimum_complexity['write']),
    #                                 float(minimum_complexity['read']),
    #                                 float(minimum_complexity['sequence']),
    #                                 float(minimum_complexity['commit']),
    #                                 float(minimum_complexity['author']),
    #                                 int(minimum_complexity['clusters']),
    #                                 float(minimum_complexity['cohesion']),
    #                                 float(minimum_complexity['coupling']),
    #                                 float(minimum_complexity['complexity']),
    #                                 float(minimum_complexity['pondered_complexity'])))
    #
    # best = pd.DataFrame(best_decompositions, columns=['access', 'write', 'read', 'sequence',
    #                                                   'clusters', 'cohesion', 'coupling', 'complexity',
    #                                                   'pondered_complexity'])
    # best.to_csv(f"{Constants.codebases_data_output_directory}/{codebase}/best_static_decompositions.csv", index=False)
    analyser_result.to_csv(f"{Constants.codebases_data_output_directory}/{codebase}/all_static_decompositions_all_metrics5.csv",
                           index=False)


def run_commit_analyser(codebases):
    mono2micro = Mono2MicroRequests()

    for i, codebase in enumerate(codebases):
        print("")
        print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases)}]")

        # print(f":white_circle: ({datetime.now().strftime('%H:%M:%S')}) Running for all files... ", end="")
        # result = mono2micro.do_commit_analyse(codebase, "_all")
        # if result == 200:
        #     print(f"[green]Success.[/green] Finished at {datetime.now().strftime('%H:%M:%S')}")
        # else:
        #     print(f"[red]Error (code = {result}). Aborting. [/red]")

        print(f":white_circle: ({datetime.now().strftime('%H:%M:%S')}) Running for entities only... ", end="")
        result = mono2micro.do_commit_analyse(codebase, "_entities")
        if result == 200:
            print(f"[green]Success.[/green] Finished at {datetime.now().strftime('%H:%M:%S')}")
        else:
            print(f"[red]Error (code = {result}). Aborting. [/red]")

        # save_best_decompositions_from_commit_analyser(codebase, "_all")
        save_best_decompositions_from_commit_analyser(codebase, "_entities")


def save_best_decompositions_from_commit_analyser(codebase, suffix):
    with open(f"{Constants.mono2micro_codebases_root}/{codebase}{suffix}/analyser/commitAnalyserResult.json", "r") as f:
        analyser_result = parse_analyser_result(json.load(f))

    decomposition_by_n_clusters = analyser_result.groupby('clusters')
    best_decompositions = []
    for cluster, cluster_amount in decomposition_by_n_clusters:
        minimum_complexity = cluster_amount.loc[
            cluster_amount['complexity'] == cluster_amount['complexity'].min()].head(1)
        best_decompositions.append((float(minimum_complexity['commit']),
                                    float(minimum_complexity['authors']),
                                    int(minimum_complexity['clusters']),
                                    float(minimum_complexity['cohesion']),
                                    float(minimum_complexity['coupling']),
                                    float(minimum_complexity['complexity'])))

    best = pd.DataFrame(best_decompositions, columns=['commit', 'authors', 'clusters',
                                                      'cohesion', 'coupling', 'complexity'])
    best.to_csv(f"{Constants.codebases_data_output_directory}/{codebase}/best_commit{suffix}_decompositions.csv",
                index=False)
    commit_data_analyser_result = analyser_result.drop(['access', 'write', 'read', 'sequence'], axis=1)
    commit_data_analyser_result.to_csv(
        f"{Constants.codebases_data_output_directory}/{codebase}/all_commit{suffix}_decompositions.csv", index=False)
