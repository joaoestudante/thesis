import json
import os
import difflib

from mazlami_check import get_total_authors_count, extract_data
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def contributors_per_microservice(clusters_four_data, author_data, n_clusters):
    authors_per_cluster_sum = 0
    authors_per_cluster = []
    for cluster in clusters_four_data['clusters'].keys():
        contributors_in_this_cluster = []
        for file_id in clusters_four_data['clusters'][cluster]:
            try:
                contributors_in_this_cluster += author_data[str(file_id)]
            except KeyError:
                print(f"{file_id} not found in authors data.")
        authors_per_cluster_sum += len(set(contributors_in_this_cluster))
        authors_per_cluster.append(contributors_in_this_cluster)

    return authors_per_cluster_sum / n_clusters


def get_all_clusters_files(repo_name):
    matches = difflib.get_close_matches(repo_name, os.listdir("../mono2micro-mine/codebases"), cutoff=0.4)
    paths = []
    base_dir = f"../mono2micro-mine/codebases/{repo_name}_all"
    for folder_file in os.listdir(base_dir):
        if "," in folder_file:  # it's a static decomposition
            clusters = folder_file.split(",")[-1]
            for folder_file2 in os.listdir(f"{base_dir}/{folder_file}"):
                if folder_file2 == f"N{clusters}":
                    paths.append((clusters, f"{base_dir}/{folder_file}/{folder_file2}/clusters.json"))
    return paths


def get_all_commit_clusters(repo_name):
    matches = difflib.get_close_matches(repo_name, os.listdir("../mono2micro-mine/codebases"), cutoff=0.4)
    base_dir = ""
    paths = []
    for match in matches:
        if "entities" in match:
            base_dir = f"../mono2micro-mine/codebases/{match}"
    for folder_file in os.listdir(base_dir):
        if "commit" == folder_file:
            for decomposition in os.listdir(f"{base_dir}/{folder_file}"):
                if "N" in decomposition:
                    clusters = decomposition.replace("N", "")
                    paths.append((clusters, f"{base_dir}/{folder_file}/{decomposition}/clusters.json"))
    return paths


def get_labels():
    labels = ["mazlami-codebases"]
    for i in range(3, 11):
        labels.append(f'commit-analysis-N{i}')
        labels.append(f'static-analysis-N{i}')
    print(labels)
    return labels

def main():
    #  We need the authors' data - comes from codebases-data/authors.json
    repos = pd.read_csv("joao-codebases.csv")
    mazlami_repos = pd.read_csv('mazlami-codebases.csv')
    tsr_values = []
    data = []

    for repo_name in repos["codebase"]:
        print("===================== " + repo_name + " =====================")
        with open(f"codebases-data/{repo_name}/{repo_name}-authors.json") as f:
            author_data = json.load(f)

        all_static_decompositions = get_all_clusters_files(repo_name)
        for cluster in all_static_decompositions:
            with open(cluster[1]) as f:
                cluster_data = json.load(f)

            n_monolith_authors = get_total_authors_count(author_data)
            cpm = contributors_per_microservice(cluster_data, author_data, int(cluster[0]))
            tsr = cpm / n_monolith_authors
            tsr_values.append(tsr)
            data.append([repo_name, tsr, f"static-analysis-N{cluster[0]}", "static"])
            # print(f"tsr={tsr}")

        all_commit_decompositions = get_all_commit_clusters(repo_name)
        for cluster in all_commit_decompositions:
            with open(cluster[1]) as f:
                cluster_data = json.load(f)

            n_monolith_authors = get_total_authors_count(author_data)
            cpm = contributors_per_microservice(cluster_data, author_data, int(cluster[0]))
            tsr = cpm / n_monolith_authors
            tsr_values.append(tsr)
            data.append([repo_name, tsr, f"commit-analysis-N{cluster[0]}", "commit"])

    # print(data)
    data += extract_data(mazlami_repos)
    df = pd.DataFrame(data)
    df.columns = ["repoName", "tsr", "strategy", "type"]
    # print(df)
    fig = px.box(df, x="strategy", y="tsr", color="type", points="all", category_orders={
        "strategy": get_labels(),
        "type": ["static", "commit", "mazlami"]
    })
    fig.show()




if __name__ == "__main__":
    main()
