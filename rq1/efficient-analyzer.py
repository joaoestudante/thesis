import os
import pandas as pd
import pickle
import plotly.express as px
from our_codebases_check import get_all_clusters_files, contributors_per_microservice
import json
from scipy.cluster import hierarchy
import numpy as np
from mazlami_check import get_total_authors_count
from static_files_fix import get_codebases_of_interest
from efficient_collector import get_couplings


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
        mean_authors_per_cluster += len(set(authors)) / n_clusters
    return mean_authors_per_cluster / len(total_n_authors)


def compute_static_tsr(static_cluster_data, author_data, n_clusters):
    n_monolith_authors = get_total_authors_count(author_data)
    cpm = contributors_per_microservice(static_cluster_data, author_data, int(n_clusters))
    return cpm / n_monolith_authors


def gather_tsr_data(repo_name, all_logical_coupling, fixed_history, entities_logical_coupling, entities_only_history):
    with open(f"all-codebases-data/{repo_name}/{repo_name}-authors.json") as f:
        author_data = json.load(f)

    data = []
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
        sim_matrix = build_similarity_matrix(all_logical_coupling)
        all_files_commit_tsr = compute_tsr(sim_matrix, fixed_history, int(cluster[0]))
        print(f"  - all files commit: {all_files_commit_tsr}")
        data.append([repo_name, int(cluster[0]), all_files_commit_tsr, "all files commit"])

        # TSR FOR COMMIT CLUSTER WITH ENTITY FILES
        filtered_sim_matrix = build_similarity_matrix(entities_logical_coupling)
        entities_only_commit_tsr = compute_tsr(filtered_sim_matrix, entities_only_history, int(cluster[0]))
        print(f"  - entities only commit: {entities_only_commit_tsr}")
        data.append([repo_name, int(cluster[0]), entities_only_commit_tsr, "entities only commit"])

    with open('all-codebases-data/tsrs-data.pkl', 'wb') as f:
        pickle.dump(data, f)

    return data


def main():
    if not os.path.exists("images"):
        os.mkdir("images")

    if os.path.isfile('all-codebases-data/tsrs-data.pkl'):
        with open('all-codebases-data/tsrs-data.pkl', 'rb') as f:
            data = pickle.load(f)
        df = pd.DataFrame(data, columns=['codebase', 'nclusters', 'tsr', 'type'])
        fig = px.scatter(df, x="nclusters", y="tsr", color="type", trendline='ols',
                         title="TSR as a function of the number of clusters in the decomposition")
        results = px.get_trendline_results(fig)
        print(results.query("type == 'static'").px_fit_results.iloc[0].summary())
        print(results.query("type == 'all files commit'").px_fit_results.iloc[0].summary())
        print(results.query("type == 'entities only commit'").px_fit_results.iloc[0].summary())
        fig.show()
        df.to_csv('data/tsr.csv')
    else:
        data = []
        codebases_folder = "../../../Downloads/codebases/"
        valid_codebases = get_codebases_of_interest(codebases_folder)
        ignore_refactors = True

        for repo_name in valid_codebases:
            entities_logical_coupling, all_logical_coupling, \
                entities_only_history, fixed_history, _, _ = get_couplings(repo_name,ignore_refactors)
            data += gather_tsr_data(repo_name, all_logical_coupling, fixed_history, entities_logical_coupling,
                                    entities_only_history)

        df = pd.DataFrame(data, columns=['codebase', 'nclusters', 'tsr', 'type'])
        fig = px.scatter(df, x="nclusters", y="tsr", color="type", trendline='ols')
        fig.show()


if __name__ == "__main__":
    main()
