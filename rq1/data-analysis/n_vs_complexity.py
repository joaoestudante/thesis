"""
This script generates a plot meant to evaluate trendlines of the min, median, and max values of the complexity of
decompositions, as a function of the number of clusters, for the commit-based decompositions.
"""

import pandas as pd
import os
import plotly.express as px
import statsmodels.api as sm


def get_max_complexity(repo_name):
    first_complexity = \
    pd.read_csv(f"../codebases-data/{repo_name}/{repo_name}-best-static-decompositions.csv")["complexity"][0]
    pondered_complexity = \
    pd.read_csv(f"../codebases-data/{repo_name}/{repo_name}-best-static-decompositions.csv")["pComplexity"][0]
    return first_complexity/pondered_complexity


def find_min(sorted_list):
    return sorted_list[0]


def find_max(sorted_list):
    return sorted_list[len(sorted_list) - 1]


def find_median(sorted_list):
    indices = []

    list_size = len(sorted_list)
    median = 0

    if list_size % 2 == 0:
        indices.append(int(list_size / 2) - 1)  # -1 because index starts from 0
        indices.append(int(list_size / 2))

        median = (sorted_list[indices[0]] + sorted_list[indices[1]]) / 2
        pass
    else:
        indices.append(int(list_size / 2))

        median = sorted_list[indices[0]]
        pass

    return median, indices
    pass


def getMinMedianAndMax(elementsList):
    samples = sorted(elementsList)
    median, median_indices = find_median(samples)
    minV = find_min(samples)
    maxV = find_max(samples)
    return [minV, median, maxV]


def main():
    final_df = {
        "n": [],
        "pComplexity": [],
        "hover": []
    }
    x_n = []
    y_pComplexity = []
    colors_all = []

    commit_data = pd.read_csv("../data/commit-static-comparison.csv")
    repos = pd.read_csv("../joao-codebases.csv")
    for repo_name in repos["codebase"]:
        if f"{repo_name}-best-static-decompositions.csv" in os.listdir(f"../codebases-data/{repo_name}"):
            print("\n" + repo_name)
            max_complexity = get_max_complexity(repo_name)
            this_codebase_commit_data = commit_data[(commit_data["codebase"] == repo_name) & (commit_data["type"] == "commit")]
            dict1 = {}
            for entry in this_codebase_commit_data.values:
                if entry[2] not in dict1:
                    dict1[entry[2]] = []
                dict1[entry[2]].append(entry[8]/max_complexity)

                final_df["n"].append(entry[2])
                final_df["pComplexity"].append(entry[8]/max_complexity)
                final_df["hover"].append(repo_name)

            x_data = list(dict1.keys())
            y_data = []
            for i in x_data:
                y = dict1[i]
                y_data.append(y)

            for xd, yd in zip(x_data, y_data):
                var = getMinMedianAndMax(yd)
                print(f"Min: {var[0]}, Median: {var[1]}, Max: {var[2]}")

                x_n.append(xd)
                y_pComplexity.append(var[0])
                colors_all += ['min']

                x_n.append(xd)
                y_pComplexity.append(var[1])
                colors_all += ['med']

                x_n.append(xd)
                y_pComplexity.append(var[2])
                colors_all += ['max']

    fig1 = px.scatter(
        x=x_n,
        y=y_pComplexity,
        color=colors_all,
        labels={'x': 'N', 'y': 'PComplexity'},
        range_y=[0, 1],
        title="N x PComplexity (min, med and max regressions)",
        trendline="ols"
    )
    fig1.show()

main()