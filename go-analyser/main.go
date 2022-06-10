package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"sync"
	"time"
)

type Decomposition struct {
	entityIdToClusterId map[int]int
	clusters            []Cluster
	controllers         []Controller
}

type Controller struct {
	name     string
	entities map[int]string
}

func (c *Controller) addEntity(id int, mode string) {
	savedMode, ok := c.entities[id]
	if !ok {
		if savedMode != mode && savedMode != "RW" {
			c.entities[id] = "RW"
		}
	} else {
		c.entities[id] = mode
	}
}

type Cluster struct {
	id       int
	entities []int
}

func (c Cluster) String() string {
	return fmt.Sprintf("Cluster(id: %d, entities: %d)", c.id, c.entities)
}

type Access struct {
	id   int
	mode string
}

type ControllerData struct {
	T []struct {
		ID int             `json:"id"`
		A  [][]interface{} `json:"a"`
	} `json:"t"`
}

func loadClusters(filename string) map[int][]int {
	content, err := ioutil.ReadFile(filename)
	if err != nil {
		fmt.Println(err)
	}
	var payload map[string]map[int][]int
	err = json.Unmarshal(content, &payload)
	if err != nil {
		log.Fatal("Error during Unmarshal(): ", err)
	}
	return payload["clusters"]
}

func loadDataCollection(filename string) map[string]ControllerData {
	content, err := ioutil.ReadFile(filename)
	if err != nil {
		fmt.Println(err)
	}
	var payload map[string]ControllerData
	err = json.Unmarshal(content, &payload)
	if err != nil {
		log.Fatal("Error during Unmarshal(): ", err)
	}
	return payload
}

func initializeDecomposition(clusters map[int][]int) *Decomposition {
	decomposition := new(Decomposition)
	decomposition.entityIdToClusterId = make(map[int]int)

	for id, entities := range clusters {
		decomposition.clusters = append(decomposition.clusters, Cluster{id: id, entities: entities})
		for entityId := range entities {
			decomposition.entityIdToClusterId[entityId] = id
		}
	}
	return decomposition
}

func getControllersWithCostlyAccessesConcurrent(entityIdToClusterId map[int]int) map[string]Controller {
	dataCollection := loadDataCollection("/home/joaolourenco/Thesis/development/mono2micro-mine/codebases/fenixedu-academic_all/datafile.json")
	controllers := make(map[string]Controller)

	var wg sync.WaitGroup

	for controllerName, data := range dataCollection {
		wg.Add(1)
		go func(controllerName string, data ControllerData, entityIdToClusterId map[int]int) {
			defer wg.Done()
			controllerObject := Controller{name: controllerName, entities: make(map[int]string)}
			previousCluster := -2
			entityIdToMode := make(map[int]string)
			for i, access := range data.T[0].A {
				id := int(access[1].(float64))
				mode := access[0].(string)
				cluster, ok := entityIdToClusterId[id]
				if !ok {
					// panic(fmt.Sprintf("Entity with id %d s not assigned to a cluster!", id))
					// if it does not exist returns 0, but entities may be in cluster 0...
				}
				if i == 0 {
					entityIdToMode[id] = mode
					controllerObject.addEntity(id, mode)
				} else {
					if cluster == previousCluster {
						hasCost := false
						savedMode, ok := entityIdToMode[id]
						if !ok || (savedMode == "R" && mode == "W") {
							hasCost = true
						}
						if hasCost {
							entityIdToMode[id] = mode
							controllerObject.addEntity(id, mode)
						}
					} else {
						controllerObject.addEntity(id, mode)
						entityIdToMode = make(map[int]string)
						entityIdToMode[id] = mode
					}
				}
				previousCluster = cluster
			}

			//fmt.Printf("%s is done.\n", controllerName)
		}(controllerName, data, entityIdToClusterId)
		//if len(controllerObject.entities) > 0 {
		//	controllers[controllerName] = controllerObject
		//}
		//fmt.Printf("Sent call to %s\n", controllerName)
	}
	wg.Wait()
	return controllers
}

func getControllersWithCostlyAccessesSerial(entityIdToClusterId map[int]int) map[string]Controller {
	dataCollection := loadDataCollection("/home/joaolourenco/Thesis/development/mono2micro-mine/codebases/fenixedu-academic_all/datafile.json")
	controllers := make(map[string]Controller)

	for controllerName, data := range dataCollection {
		controllerObject := Controller{name: controllerName, entities: make(map[int]string)}
		previousCluster := -2
		entityIdToMode := make(map[int]string)
		for i, access := range data.T[0].A {
			id := int(access[1].(float64))
			mode := access[0].(string)
			cluster, ok := entityIdToClusterId[id]
			if !ok {
				// panic(fmt.Sprintf("Entity with id %d s not assigned to a cluster!", id))
				// if it does not exist returns 0, but entities may be in cluster 0...
			}
			if i == 0 {
				entityIdToMode[id] = mode
				controllerObject.addEntity(id, mode)
			} else {
				if cluster == previousCluster {
					hasCost := false
					savedMode, ok := entityIdToMode[id]
					if !ok || (savedMode == "R" && mode == "W") {
						hasCost = true
					}
					if hasCost {
						entityIdToMode[id] = mode
						controllerObject.addEntity(id, mode)
					}
				} else {
					controllerObject.addEntity(id, mode)
					entityIdToMode = make(map[int]string)
					entityIdToMode[id] = mode
				}
			}
			previousCluster = cluster
		}
		if len(controllerObject.entities) > 0 {
			controllers[controllerName] = controllerObject
		}
		//fmt.Printf("%s is done.\n", controllerName)
	}

	//fmt.Printf("Sent call to %s\n", controllerName)
	return controllers
}

func main() {
	clusters := loadClusters("/home/joaolourenco/Thesis/development/mono2micro-mine/codebases/fenixedu-academic_all/analyser/cuts/20,10,0,10,60,0,5.json")
	decomposition := initializeDecomposition(clusters)

	start := time.Now()
	getControllersWithCostlyAccessesSerial(decomposition.entityIdToClusterId)
	elapsed := time.Since(start)
	log.Printf("Controllers with costly accesses took %s", elapsed)
}
