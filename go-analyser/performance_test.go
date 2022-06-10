package main

import "testing"

func BenchmarkConcurrentControllersCostlyAccesses(b *testing.B) {
	clusters := loadClusters("/home/joaolourenco/Thesis/development/mono2micro-mine/codebases/fenixedu-academic_all/analyser/cuts/20,10,0,10,60,0,5.json")
	decomposition := initializeDecomposition(clusters)
	for i := 0; i < b.N; i++ {
		getControllersWithCostlyAccessesSerial(decomposition.entityIdToClusterId)
	}
}

func BenchmarkSerialControllersCostlyAccesses(b *testing.B) {
	clusters := loadClusters("/home/joaolourenco/Thesis/development/mono2micro-mine/codebases/fenixedu-academic_all/analyser/cuts/20,10,0,10,60,0,5.json")
	decomposition := initializeDecomposition(clusters)
	for i := 0; i < b.N; i++ {
		getControllersWithCostlyAccessesConcurrent(decomposition.entityIdToClusterId)
	}
}
