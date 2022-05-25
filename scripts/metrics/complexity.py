import json
from collections import defaultdict

from funcy import print_durations

from helpers.constants import Constants


def get_controllers_to_clusters(clusters, controllers):
    result = defaultdict(set)
    for cluster in clusters:
        for controller in controllers:
            for entity_id in controller.entities:
                if entity_id in cluster.entities:
                    result[controller].add(cluster)
    return result


class Decomposition:
    def __init__(self):
        self.entity_id_to_cluster_id = {}
        self.clusters = []
        self.controllers = {}
        self.pandas_controllers = None

    def add_cluster(self, cluster):
        self.clusters.append(cluster)

    def add_entity(self, entity_id, cluster_id):
        self.entity_id_to_cluster_id[entity_id] = cluster_id

    def get_all_transactions_set(self, data_collection):
        all_local_transactions_sets = {}
        for controller in self.controllers.keys():
            local_transaction_set = self.get_local_transactions_set(controller, data_collection)
            all_local_transactions_sets[controller] = local_transaction_set
        return all_local_transactions_sets

    def get_controller_complexity(self, controller_local_transactions, controller, controllers_clusters_map):
        i = 0
        controllers_touching_entity_with_mode_cache = {}
        complexity = 0
        for local_transaction in controller_local_transactions:
            i += 1
            controllers_touching_same_entities = set()
            for a in local_transaction.cluster_accesses:
                controllers_that_touch_this_entity_and_mode = controllers_touching_entity_with_mode_cache.get(a, None)
                if controllers_that_touch_this_entity_and_mode is None:
                    controllers_that_touch_this_entity_and_mode = self.cost_of_access(controller, a,
                                                                                      controllers_clusters_map)
                    controllers_touching_entity_with_mode_cache[a] = controllers_that_touch_this_entity_and_mode
                for c in controllers_that_touch_this_entity_and_mode:
                    controllers_touching_same_entities.add(c)
            complexity += len(controllers_touching_same_entities)
        return complexity

    @print_durations
    def compute_complexity(self, data_collection):
        complexity = 0
        all_local_transactions_sets = self.get_all_transactions_set(data_collection)
        controllers_clusters_map = get_controllers_to_clusters(self.clusters, self.controllers.values())

        for controller in self.controllers.keys():
            if len(controllers_clusters_map[self.controllers[controller]]) == 1:
                continue
            complexity += self.get_controller_complexity(all_local_transactions_sets[controller], controller, controllers_clusters_map)

            # for transaction in all_local_transactions_sets[controller]:
            #     # Find next local transactions, add cluster dependencies

        complexity /= len(controllers_clusters_map)
        return complexity

    def get_local_transactions_set(self, controller, data_collection):
        accesses = data_collection[controller]["t"][0]["a"]
        first_accessed_cluster_id = None
        local_transaction_sequence = []
        entity_id_to_mode = {}
        current_local_transaction = None
        for a in accesses:
            entity_id = a[1]
            mode = a[0]
            current_cluster_id = self.entity_id_to_cluster_id[entity_id]
            if current_cluster_id is None:
                print(f"{current_cluster_id} is not assigned to a cluster")
            if first_accessed_cluster_id is None:
                first_accessed_cluster_id = current_cluster_id

            if current_local_transaction is None:
                current_local_transaction = LocalTransaction(current_cluster_id, a, entity_id)
                entity_id_to_mode[entity_id] = mode
            else:
                if current_cluster_id == current_local_transaction.cluster_id:
                    has_cost = False
                    saved_mode = entity_id_to_mode.get(entity_id, None)
                    if saved_mode is None or (saved_mode == "R" and mode == "W"):
                        has_cost = True
                    if has_cost:
                        current_local_transaction.add_cluster_access(a)
                        entity_id_to_mode[entity_id] = mode
                else:
                    local_transaction_sequence.append(current_local_transaction)
                    current_local_transaction = LocalTransaction(current_cluster_id, a, entity_id)
                    entity_id_to_mode = {entity_id: mode}
        if current_local_transaction is not None and len(current_local_transaction.cluster_accesses) > 0:
            local_transaction_sequence.append(current_local_transaction)

        return local_transaction_sequence

    def cost_of_access(self, controller_name, a, controllers_clusters_map):
        controllers_touching_this_entity_with_mode = []
        for controller in self.controllers.values():
            if controller.name != controller_name and controller in controllers_clusters_map:
                saved_mode = controller.entities.get(a[1], None)
                if saved_mode is not None and saved_mode != a[0] and len(controllers_clusters_map[controller]) > 1:
                    controllers_touching_this_entity_with_mode.append(controller.name)
        return controllers_touching_this_entity_with_mode

    def create_pandas_controllers(self):
        pass


class LocalTransaction:
    def __init__(self, cluster_id, new_cluster_access, first_accessed_entity_id):
        self.cluster_id = cluster_id
        self.cluster_accesses = set()
        self.cluster_accesses.add(tuple(new_cluster_access))
        self.first_accessed_entity_ids = {first_accessed_entity_id}

    def add_cluster_access(self, a):
        self.cluster_accesses.add(tuple(a))


class Cluster:
    def __init__(self, entities, cluster_id):
        self.entities = entities
        self.id = cluster_id

    def __repr__(self):
        return self.id


class Controller:
    def __init__(self, name):
        self.name = name
        self.entities = {}

    def add_entity(self, entity_id, mode):
        saved_mode = self.entities.get(entity_id, None)
        if saved_mode is not None:
            if saved_mode != mode and saved_mode != "RW":
                self.entities[entity_id] = "RW"
        else:
            self.entities[entity_id] = mode

    def __repr__(self):
        return self.name


@print_durations()
def get_controllers_with_costly_accesses(codebase_name, entity_id_to_cluster_id, data_collection):
    controllers = {}
    for controller_name, trace in data_collection.items():
        accesses = trace["t"][0]["a"]
        entity_id_to_mode = {}
        previous_cluster = '-2'
        controller = Controller(controller_name)
        for i, access in enumerate(accesses):
            entity_id = access[1]
            mode = access[0]
            cluster = entity_id_to_cluster_id.get(entity_id, None)
            if cluster is None:
                print(f"Entity {entity_id} was not assigned to a cluster, abort.")
                exit(0)
            if i == 0:
                entity_id_to_mode[entity_id] = mode
                controller.add_entity(entity_id, mode)
            else:
                if cluster == previous_cluster:
                    has_cost = False
                    saved_mode = entity_id_to_mode.get(entity_id, None)
                    if saved_mode is None or (saved_mode == "R" and mode == "W"):
                        has_cost = True
                    if has_cost:
                        entity_id_to_mode[entity_id] = mode
                        controller.add_entity(entity_id, mode)
                else:
                    controller.add_entity(entity_id, mode)
                    entity_id_to_mode = {entity_id: mode}
            previous_cluster = cluster
        if len(controller.entities) > 0:
            controllers[controller.name] = controller
    return controllers

@print_durations
def build_decomposition():
    with open(f"{Constants.mono2micro_codebases_root}/fenixedu-academic_all/analyser/cuts/"
              f"20,10,0,10,60,0,5.json", "r") as f:
        clusters = json.load(f)["clusters"]
    with open(f"{Constants.mono2micro_codebases_root}/fenixedu-academic_all/datafile.json", "r") as f:
        data_collection = json.load(f)

    decomposition = Decomposition()
    for cluster_id, entities in clusters.items():
        decomposition.add_cluster(Cluster(entities, cluster_id))
        for entity_id in entities:
            decomposition.add_entity(entity_id, cluster_id)

    decomposition.controllers = get_controllers_with_costly_accesses(
        "fenixedu-academic_all", decomposition.entity_id_to_cluster_id, data_collection)

    decomposition.create_pandas_controllers()

    complexity = decomposition.compute_complexity(data_collection)
    print(f"Final Complexity: {complexity}")


build_decomposition()
