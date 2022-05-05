import json
import os
import time

import pandas as pd
from pydriller.git import Git
import subprocess
from io import StringIO

from scipy.cluster import hierarchy
import numpy as np
import itertools
from collections import Counter

from mazlami_check import get_total_authors_count
from our_codebases_check import get_all_clusters_files, contributors_per_microservice
import plotly.express as px


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def findsubsets(S,m):
    return set(itertools.combinations(S, m))


def get_history(repo_name) -> pd.DataFrame:
    command = f"./commit_log_script.sh ../codebases/{repo_name}/ | grep .java"
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print("Error retrieving history.")
        print(e)
    else:
        return pd.read_csv(StringIO(output), sep=";", names=['commit_hash', 'change_type', 'previous_filename', 'filename', 'timestamp', 'author'])


def fix_renames(history: pd.DataFrame):
    rename_info = history.loc[history['change_type'] == "RENAMED"]
    #
    # occurrences_to_be_replaced = history.merge(rename_info, left_on='filename', right_on='previous_filename')
    # occurrences_to_be_replaced['filename_x'] = occurrences_to_be_replaced['filename_y']
    # occurrences_to_be_replaced['previous_filename_x'] = occurrences_to_be_replaced['previous_filename_y']
    # occurrences_to_be_replaced = occurrences_to_be_replaced.drop(['commit_hash_x', 'commit_hash_y', 'change_type_x', 'change_type_y', 'previous_filename_y', 'filename_y', 'timestamp_y', 'timestamp_x'], axis=1)
    # occurrences_to_be_replaced.columns = ['previous_filename', 'filename']
    # occurrences_to_be_replaced.drop_duplicates(inplace=True)
    #
    # renamed_history = history.merge(occurrences_to_be_replaced, left_on='filename', right_on='previous_filename', how='outer', indicator=True)
    # renamed_history.loc[renamed_history['filename_x'] == renamed_history['previous_filename_y'], 'filename_x'] = renamed_history['filename_y']
    # renamed_history = renamed_history.drop(['previous_filename_y', 'filename_y', '_merge'], axis=1)
    # renamed_history.columns = ['commit_hash', 'change_type', 'previous_filename', 'filename', 'timestamp']
    # # renamed_history.fillna('?', inplace=True)

    for before, after in zip(rename_info['previous_filename'], rename_info['filename']):
        history.loc[history['filename'] == before, 'filename'] = after
    return history


def fix_deletes(history: pd.DataFrame):
    delete_info = history.loc[history['change_type'] == "DELETED"]['filename']
    history = history.loc[~history['filename'].isin(delete_info)]
    history = history.loc[~history['previous_filename'].isin(delete_info)]
    return history


def compute_logical_coupling(fixed_history):
    earliest_timestamp = fixed_history['timestamp'].min()
    last_timestamp = fixed_history['timestamp'].max()
    couplings = []
    for ts in range(earliest_timestamp, last_timestamp, 3600):
        bottom_range = ts
        top_range = bottom_range + 3600
        commits_of_interest = fixed_history.loc[(fixed_history['timestamp'] < top_range) & (fixed_history['timestamp'] >= bottom_range)]
        filenames = set(commits_of_interest['filename'])
        couplings += findsubsets(filenames, 2)

    return pd.DataFrame(couplings, columns=['first_file', 'second_file'])


def build_similarity_matrix(logical_coupling):
    # https://stackoverflow.com/questions/48393259/count-unique-pairs-and-store-counts-in-a-matrix
    unique_filenames = list(logical_coupling['first_file'].unique())
    v = pd.crosstab(logical_coupling['first_file'], logical_coupling['second_file'])
    res = v.reindex(index=unique_filenames, columns=unique_filenames, fill_value=0)
    np.fill_diagonal(res.values, 1)
    return res


def generate_decomposition(matrix, n_clusters, method, history):
    hierarch = hierarchy.linkage(matrix, method)
    fcluster_clusters = hierarchy.fcluster(hierarch, n_clusters, criterion='maxclust')
    clusters = {}
    clusters_authors = {}
    files = matrix.columns
    for i in range(len(fcluster_clusters)):
        if str(fcluster_clusters[i]) in clusters.keys():
            clusters[str(fcluster_clusters[i])] += [files[i]]
            clusters_authors[str(fcluster_clusters[i])] += list(history[history['filename'] == files[i]]['author'])
        else:
            clusters[str(fcluster_clusters[i])] = [files[i]]
            clusters_authors[str(fcluster_clusters[i])] = list(history[history['filename'] == files[i]]['author'])
    return clusters, clusters_authors


def compute_tsr(sim_matrix, history, n_clusters):
    decomposition, decomposition_authors = generate_decomposition(sim_matrix, n_clusters, 'average', history)
    total_n_authors = history['author'].unique()
    mean_authors_per_cluster = 0
    for authors in decomposition_authors.values():
        mean_authors_per_cluster += len(set(authors))/n_clusters
    return mean_authors_per_cluster/len(total_n_authors)


def compute_static_tsr(static_cluster_data, author_data, n_clusters):
    n_monolith_authors = get_total_authors_count(author_data)
    cpm = contributors_per_microservice(static_cluster_data, author_data, int(n_clusters))
    return cpm / n_monolith_authors


def extract_entity_files(repo_name, fixed_history):
    results = []
    for file in os.listdir(f"codebases-data/{repo_name}"):
        if "IDToEntity" in file:
            with open(f"codebases-data/{repo_name}/{file}") as f:
                files_plain = list(json.load(f).values())
                for filename in files_plain:
                    filename_long = list(fixed_history.loc[fixed_history['filename'].str.contains(filename+".java")]['filename'].head(1))
                    if len(filename_long) > 0:
                        results.append(filename_long[0])
    return results


def main():
    repo_data = pd.read_csv("joao-codebases.csv")
    ignore_refactors = True
    tsr_values = []
    data = []

    i = 0
    for repo_name in repo_data['codebase']:
        print(f"===================== {bcolors.UNDERLINE} {repo_name} {bcolors.ENDC} ===================== ")
        print("* Preparing history...")
        t0 = time.time()
        history = get_history(repo_name)
        renamed_history = fix_renames(history)
        fixed_history = fix_deletes(renamed_history)

        print("* Computing logical coupling...")
        if ignore_refactors:  # Ignore commits with more than 100 files
            grouped_history = fixed_history.groupby('commit_hash').filter(lambda x: len(x) < 100)
            logical_coupling = compute_logical_coupling(grouped_history)
        else:
            logical_coupling = compute_logical_coupling(fixed_history)

        with open(f"codebases-data/{repo_name}/{repo_name}-authors.json") as f:
            author_data = json.load(f)

        all_static_decompositions = get_all_clusters_files(repo_name)
        for cluster in all_static_decompositions:
            with open(cluster[1]) as f:
                static_cluster_data = json.load(f)

            print(f"* tsrs for {cluster[0]} clusters: ")
            # TSR FOR STATIC CLUSTER - cluster is already made
            static_tsr = compute_static_tsr(static_cluster_data, author_data, cluster[0])
            print(f"  - static: {static_tsr}")
            data.append([repo_name, int(cluster[0]), static_tsr, "static"])

            # TSR FOR COMMIT CLUSTER WITH ALL FILES
            sim_matrix = build_similarity_matrix(logical_coupling)
            all_files_commit_tsr = compute_tsr(sim_matrix, fixed_history, int(cluster[0]))
            print(f"  - all files commit: {all_files_commit_tsr}")
            data.append([repo_name, int(cluster[0]), all_files_commit_tsr, "all files commit"])


            # TSR FOR COMMIT CLUSTER WITH ENTITY FILES
            entity_files = extract_entity_files(repo_name, fixed_history)
            filtered_coupling = logical_coupling.loc[(logical_coupling['first_file'].isin(entity_files)) & (logical_coupling['second_file'].isin(entity_files))]
            filtered_sim_matrix = build_similarity_matrix(filtered_coupling)
            entities_only_commit_tsr = compute_tsr(filtered_sim_matrix, fixed_history, int(cluster[0]))
            print(f"  - entities only commit: {entities_only_commit_tsr}")
            data.append([repo_name, int(cluster[0]), entities_only_commit_tsr, "entities only commit"])
        print(f"Done - total time was {time.time() - t0}")

    df = pd.DataFrame(data, columns=['codebase', 'nclusters', 'tsr', 'type'])
    fig = px.box(df, x="nclusters", y="tsr", color="type")
    fig.show()


if __name__ == '__main__':
    main()
