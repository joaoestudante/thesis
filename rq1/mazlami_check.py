"""
This script is meant to check the data from Mazlami's paper. We want to confirm their results with their codebases and
with ours.
"""
import json
import pandas as pd
import numpy as np
from scipy.cluster import hierarchy
import plotly.express as px


def generate_similarity_matrix(commit_data):
    matrix = []
    for file1 in commit_data.keys():
        row = []
        for file2 in commit_data.keys():
            if file1 == file2:
                row.append(1)
                continue

            metric = 0
            for file1_file in commit_data[file1]:
                if file1_file == file2:
                    metric += 1
            row.append(metric)
        matrix.append(row)
    return np.array(matrix)


def generate_decomposition(matrix, n_clusters, method):
    hierarch = hierarchy.linkage(matrix, method)
    fcluster_clusters = hierarchy.fcluster(hierarch, n_clusters, criterion='maxclust')
    clusters = {}
    for i in range(len(fcluster_clusters)):
        if str(fcluster_clusters[i]) in clusters.keys():
            clusters[str(fcluster_clusters[i])] += [i]
        else:
            clusters[str(fcluster_clusters[i])] = [i]
    return clusters


def get_total_authors_count(authors_data):
    total = 0
    authors = list(authors_data.values())
    authors_set = set()
    for author_list in authors:
        for author in author_list:
            authors_set.add(author)
    return len(authors_set)


def compute_average_contributors_per_microservice(decomposition, commit_data, authors_data):
    authors_per_cluster_sum = 0
    authors_per_cluster = []
    files = list(commit_data.keys())
    for cluster in decomposition.keys():
        contributors_in_this_cluster = []
        for file_id in decomposition[cluster]:
            try:
                contributors_in_this_cluster += authors_data[files[int(file_id)]]
            except KeyError:
                print(f"{files[int(file_id)]} not found in authors data.")
        authors_per_cluster_sum += len(set(contributors_in_this_cluster))
        authors_per_cluster.append(contributors_in_this_cluster)

    return authors_per_cluster_sum / 4


def main():
    repos = pd.read_csv("joao-codebases.csv")
    data = extract_data(repos)

    df = pd.DataFrame(data)
    df.columns = ["repoName", "tsr", "linkageType"]
    fig = px.box(df, x="linkageType", y="tsr", points="all")
    fig.show()


def extract_data(repos):
    tsr_values = []
    linkage_type = []
    data = []
    repo_count = 0
    # linkage_types = ['single', 'complete', 'average', 'weighted', 'centroid', 'median', 'ward']
    for repo_name in repos["codebase"]:
        print("")
        print(repo_name)
        with open(f"codebases-data/{repo_name}/{repo_name}-commit-v3.json", "r") as d:
            commit_data = json.load(d)

        print("Building matrix")
        matrix = generate_similarity_matrix(commit_data)

        # for linkage in linkage_types:
        # print(f"Decomposition with linkage type: '{linkage}'")
        decomposition = generate_decomposition(matrix, 4, 'average')

        with open(f"codebases-data/{repo_name}/{repo_name}-author-v3.json", "r") as d:
            authors_data = json.load(d)

        print("Counting metrics")
        n_monolith_authors = get_total_authors_count(authors_data)
        cpm = compute_average_contributors_per_microservice(decomposition, commit_data, authors_data)
        tsr = cpm / n_monolith_authors
        tsr_values.append(tsr)
        # linkage_type.append(linkage)
        data.append([repo_name, tsr, 'commit-analysis-mazlami', "mazlami"])
        print(f"tsr={tsr}")
    repo_count += 1
    return data


if __name__ == "__main__":
    main()
