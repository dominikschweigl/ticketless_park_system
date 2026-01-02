package com.ticketless.parking.app;

import akka.actor.ActorRef;
import akka.actor.ActorSystem;
import com.typesafe.config.Config;
import com.typesafe.config.ConfigFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

import com.ticketless.parking.actors.ParkingLotManagerActor;
import com.ticketless.parking.messages.*;

/**
 * Main entry point for the Ticketless Parking System application.
 * 
 * This application demonstrates a distributed Akka actor-based parking management system.
 * 
 * Architecture:
 * - ParkingLotManagerActor: Supervises all parking lots and handles registration
 * - ParkingLotActor (per parking lot): Manages individual parking lot state
 * - Edge servers register parking lots and send periodic occupancy updates
 * 
 * State Model:
 * - Edge servers are the SOURCE OF TRUTH via sensor measurements
 * - Edge servers periodically send OccupancyMessage with current car count
 * - Cloud system mirrors the state received from edge servers
 * - No need for individual car arrival/departure messages
 * 
 * Benefits of occupancy-based approach:
 * 1. Simple and robust - single source of truth per parking lot
 * 2. Handles sensor errors gracefully
 * 3. No message ordering issues
 * 4. Easy to audit and debug
 * 5. Naturally handles edge server failover (latest occupancy is always accurate)
 * 
 * Can be run on AWS ECS with proper Docker configuration.
 */
public class ParkingSystemApp {
    private static final Logger logger = LoggerFactory.getLogger(ParkingSystemApp.class);

    private final ActorSystem actorSystem;
    private final ActorRef parkingLotManager;

    /**
     * Initializes the Parking System application.
     */
    public ParkingSystemApp() {
        Config config = ConfigFactory.load();
        this.actorSystem = ActorSystem.create("ParkingSystem", config);
        this.parkingLotManager = actorSystem.actorOf(
                ParkingLotManagerActor.props(),
                "parking-lot-manager"
        );
        logger.info("ParkingSystemApp initialized with ActorSystem: {}", actorSystem.name());
    }

    /**
     * Registers a new parking lot with the system.
     * This should be called by edge servers when they come online.
     *
     * @param parkId      Unique identifier for the parking lot
     * @param maxCapacity Maximum capacity of the parking lot
     * @param edgeServerId Identifier of the edge server registering this lot
     */
    public void registerParkingLot(String parkId, int maxCapacity, String edgeServerId) {
        parkingLotManager.tell(
                new RegisterParkMessage(parkId, maxCapacity, edgeServerId),
                ActorRef.noSender()
        );
    }

    /**
     * Gets list of all registered parking lots.
     * Edge servers use this to discover available lots.
     */
    public void getRegisteredLots() {
        parkingLotManager.tell(
                GetRegisteredParksMessage.INSTANCE,
                ActorRef.noSender()
        );
    }

    /**
     * Sends occupancy update for a parking lot.
     * This is called by edge servers periodically with the current number of cars.
     * This REPLACES the old CarArrivedMessage/CarDepartedMessage approach.
     *
     * @param parkId       Parking lot identifier
     * @param occupancy    Current number of cars in the lot (from sensors)
     * @param edgeServerId Identifier of the edge server sending this update
     */
    public void updateOccupancy(String parkId, int occupancy, String edgeServerId) {
        parkingLotManager.tell(
                new ParkingLotOccupancyMessage(parkId, occupancy, System.currentTimeMillis(), edgeServerId),
                ActorRef.noSender()
        );
    }

    /**
     * Shuts down the actor system gracefully.
     */
    public void shutdown() {
        logger.info("Shutting down ParkingSystemApp");
        actorSystem.terminate();
    }

    /**
     * Main method - entry point for the application.
     * Supports AWS ECS environment variables for configuration.
     */
    public static void main(String[] args) {
        logger.info("Starting Ticketless Parking System");

        ParkingSystemApp app = new ParkingSystemApp();

        // Example: Edge servers register their parking lots
        logger.info("Edge servers registering parking lots...");
        app.registerParkingLot("lot-01", 50, "edge-server-01");
        app.registerParkingLot("lot-02", 100, "edge-server-02");
        app.registerParkingLot("lot-03", 25, "edge-server-01");

        // Give the system a moment to process registrations
        try {
            Thread.sleep(500);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // Example: Edge servers send periodic occupancy updates
        logger.info("Simulating occupancy updates from edge servers...");
        
        // Edge server 1 sending occupancy updates for lot-01
        app.updateOccupancy("lot-01", 15, "edge-server-01");
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        app.updateOccupancy("lot-01", 18, "edge-server-01");
        
        // Edge server 2 sending occupancy updates for lot-02
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        app.updateOccupancy("lot-02", 45, "edge-server-02");
        
        // Edge server 1 sending occupancy updates for lot-03
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        app.updateOccupancy("lot-03", 8, "edge-server-01");

        // Keep the application running
        logger.info("Parking System is running. Press Ctrl+C to exit.");
        try {
            System.in.read();
        } catch (IOException e) {
            logger.error("Error reading input", e);
        }

        app.shutdown();
    }
}
