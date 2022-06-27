"""
A mixed collection strategy, where the commit data changes the static analysis data.

The algorithm is like so:
- Retrieve, parse, fix the history and store it in a dataframe.
- Compute the similarity of all entities
- For each functionality:
    * Create a similarity matrix with the entities in that functionality
    * Cluster those entities in the best way possible (according to scipy's fcluster method)
    * Create a new functionality for each of the generated clusters
"""
from functools import lru_cache

from collector.commitsplit import parse_functionalities
from collector.repository import Repository
from collector.service import get_logical_couplings
from helpers.constants import Constants
import json
from scipy.cluster import hierarchy
import numpy as np
from rich import print


class StaticFunctionality:
    def __init__(self, accesses, name):
        self.accesses = accesses
        self.name = name

    def __str__(self):
        return f"{self.name} - {len(self.accesses)} accesses"

    def __repr__(self):
        return self.__str__()

    def add_access(self, access):
        self.accesses.append(access)

    @lru_cache
    def entities_ids(self):
        entities_ids = set()
        for access in self.accesses:
            entities_ids.add(access[1])
        return entities_ids

    def split(self, couplings):
        new_functionalities = []
        entities_in_functionaliy = set()
        for a in self.accesses:
            entities_in_functionaliy.add(a[1])
        if len(entities_in_functionaliy) == 1:
            return [self]

        similarities = []
        for entity1 in entities_in_functionaliy:
            entity1_similarity = []
            for entity2 in entities_in_functionaliy:
                if entity1 == entity2:
                    entity1_similarity.append(1)
                else:
                    entity1_similarity.append(
                        len(couplings.loc[(couplings["first_file"] == entity1) & (couplings["second_file"] == entity2)])
                    )
            similarities.append(entity1_similarity)
        matrix = np.array(similarities)
        hierarc = hierarchy.linkage(y=matrix)
        n_clusters = 2
        clustering = hierarchy.fcluster(hierarc, n_clusters, criterion='maxclust')

        # Test if only one cluster exists - situation where it's all 1s
        if np.sum(clustering) == len(clustering):
            return [self]

        for i in range(n_clusters):
            new_functionalities.append(StaticFunctionality([], f"{self.name}-{i}"))

        for access in self.accesses:
            entity_cluster = clustering[list(entities_in_functionaliy).index(access[1])]
            new_functionalities[entity_cluster-1].add_access(access)

        return new_functionalities

    def json_format(self):
        return {"t": [{"id": 0, "a": self.accesses}]}


def convert_names_ids(element, repo):
    return [int(repo.get_file_id(element[0])), int(repo.get_file_id(element[1]))]


def parse_full_functionalities(static_analysis_file_path):
    functionalities = []
    with open(static_analysis_file_path, "r") as f:
        data = json.load(f)
    for controller in data:
        accesses = data[controller]["t"][0]["a"]
        functionalities.append(StaticFunctionality(accesses, controller))
    return functionalities


def collect(codebases):
    for codebase in codebases:
        print(f":white_circle: {codebase}")
        print("  :white_circle: Initializing history")
        codebase_repo = Repository(codebase)

        cutoff_value = 100
        print("  :white_circle: Processing history")
        history = codebase_repo.cleanup_history(cutoff_value)

        print("  :white_circle: Parsing functionalities")
        functionalities = parse_full_functionalities(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}.json")

        print("  :white_circle: Getting coupling data")
        couplings = get_logical_couplings(history)

        print("  :white_circle: Converting to ids")
        couplings_ids = couplings.apply(convert_names_ids, args=[codebase_repo], axis=1, result_type='expand')
        couplings_ids.set_axis(["first_file", "second_file"], axis=1, inplace=True)

        print("  :white_circle: Splitting functionalities")
        final_data_collection = {}
        for functionality in functionalities:
            for new_functionality in functionality.split(couplings_ids):
                final_data_collection[new_functionality.name] = new_functionality.json_format()

        with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}-split.json", "w") as f:
            json.dump(final_data_collection, f)


# collect(["spring-framework-petclinic"])