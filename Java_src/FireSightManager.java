import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;

// ============================================================================
// DATA STRUCTURE 1: PriorityQueue (Max-Heap) for Emergency Dispatch
// ============================================================================
class FireIncident {
    String zoneName;
    double riskScore;

    public FireIncident(String zoneName, double riskScore) {
        this.zoneName = zoneName;
        this.riskScore = riskScore;
    }
}

class PriorityDispatchSystem {
    private PriorityQueue<FireIncident> dispatchQueue;

    public PriorityDispatchSystem() {
        // Max-Heap: Orders incidents so the highest risk score is retrieved first O(log N)
        dispatchQueue = new PriorityQueue<>(Comparator.comparingDouble((FireIncident f) -> f.riskScore).reversed());
    }

    public void addIncident(String zone, double risk) {
        dispatchQueue.add(new FireIncident(zone, risk));
    }

    public FireIncident getHighestPriorityIncident() {
        return dispatchQueue.poll();
    }
}

// ============================================================================
// DATA STRUCTURE 2: Spatial Index / QuadTree Node for Geospatial Partitioning
// ============================================================================
class QuadTreeNode {
    double minLat, maxLat, minLon, maxLon;
    boolean isDivided = false;
    QuadTreeNode northWest, northEast, southWest, southEast;

    public QuadTreeNode(double minLat, double maxLat, double minLon, double maxLon) {
        this.minLat = minLat;
        this.maxLat = maxLat;
        this.minLon = minLon;
        this.maxLon = maxLon;
    }

    public void subdivide() {
        double midLat = (minLat + maxLat) / 2.0;
        double midLon = (minLon + maxLon) / 2.0;

        northWest = new QuadTreeNode(midLat, maxLat, minLon, midLon);
        northEast = new QuadTreeNode(midLat, maxLat, midLon, maxLon);
        southWest = new QuadTreeNode(minLat, midLat, minLon, midLon);
        southEast = new QuadTreeNode(minLat, midLat, midLon, maxLon);
        isDivided = true;
    }
}

// ============================================================================
// DATA STRUCTURE 3: Graph (Adjacency List) for Evacuation Routing
// ============================================================================
class SectorGraph {
    private Map<String, List<Edge>> adjacencyList = new HashMap<>();

    static class Edge {
        String targetSector;
        double travelRiskWeight;

        public Edge(String targetSector, double travelRiskWeight) {
            this.targetSector = targetSector;
            this.travelRiskWeight = travelRiskWeight;
        }
    }

    public void addSector(String sectorId) {
        adjacencyList.putIfAbsent(sectorId, new ArrayList<>());
    }

    public void addRoad(String source, String destination, double weight) {
        adjacencyList.putIfAbsent(source, new ArrayList<>());
        adjacencyList.putIfAbsent(destination, new ArrayList<>());
        adjacencyList.get(source).add(new Edge(destination, weight));
        adjacencyList.get(destination).add(new Edge(source, weight));
    }
}

// ============================================================================
// MAIN MANAGER CLASS
// ============================================================================
public class FireSightManager {

    public static void main(String[] args) {
        System.out.println("==================================================");
        System.out.println("🔥 FireSight AI - Java Bridge & Data Structure System");
        System.out.println("==================================================");

        // Initialize and demonstrate Java Data Structures
        PriorityDispatchSystem dispatchSystem = new PriorityDispatchSystem();
        dispatchSystem.addIncident("Pune Sector 1", 45.5);
        dispatchSystem.addIncident("Pune Sector 4", 88.2); // Highest Risk

        FireIncident topIncident = dispatchSystem.getHighestPriorityIncident();
        System.out.println("[JAVA DS] Max-Heap Priority Dispatch Initialized.");
        if (topIncident != null) {
            System.out.println("[JAVA DS] Top Priority Dispatch Target: " + topIncident.zoneName + " (Risk: " + topIncident.riskScore + ")");
        }

        try {
            // Execution command to trigger the Python analysis orchestrator
            ProcessBuilder pb = new ProcessBuilder("python", "-m", "src.main", "--mode", "auto");
            pb.redirectErrorStream(true);

            Process process = pb.start();

            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            String line;
            System.out.println("\n[JAVA BRIDGE] Triggering Python Backend Service...\n");

            while ((line = reader.readLine()) != null) {
                System.out.println(line);
            }

            int exitCode = process.waitFor();
            System.out.println("\n==================================================");
            System.out.println("[JAVA BRIDGE] Process finished with exit code: " + exitCode);
            System.out.println("==================================================");

        } catch (Exception e) {
            System.err.println("[JAVA BRIDGE ERROR] Failed to execute Python process: " + e.getMessage());
            e.printStackTrace();
        }
    }
}