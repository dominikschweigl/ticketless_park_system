package com.ticketless.parking.app;

import akka.actor.typed.ActorSystem;
import akka.actor.typed.ActorRef;
import akka.actor.typed.javadsl.AskPattern;
import akka.actor.typed.Props;
import scala.concurrent.duration.FiniteDuration;
import java.time.Duration;
import com.typesafe.config.Config;
import com.typesafe.config.ConfigFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

import com.ticketless.parking.actors.ParkingLotManagerActor;
import com.ticketless.parking.actors.PaymentActor;
import com.ticketless.parking.http.ParkingHttpServer;
import com.ticketless.parking.messages.*;

/**
 * Main entry point for the Ticketless Parking System application.
 */
public class ParkingSystemApp {
    private static final Logger logger = LoggerFactory.getLogger(ParkingSystemApp.class);

    private final ActorSystem<ParkingLotManagerActor.Command> actorSystem;
    private final ActorRef<ParkingLotManagerActor.Command> parkingLotManager;
    private final ActorRef<PaymentActor.Command> paymentActor;
    private final ParkingHttpServer httpServer;

    /**
     * Initializes the Parking System application.
     */
    public ParkingSystemApp() {
        Config config = ConfigFactory.load();
        this.actorSystem = ActorSystem.create(ParkingLotManagerActor.create(), "ParkingSystem", config);
        this.parkingLotManager = actorSystem;
        this.paymentActor = actorSystem.systemActorOf(PaymentActor.create(), "payment-actor", Props.empty());

        // Initialize HTTP server for Python edge server communication
        this.httpServer = new ParkingHttpServer(actorSystem, parkingLotManager, paymentActor);

        // Get HTTP server configuration from environment or use defaults
        String httpHost = System.getenv().getOrDefault("HTTP_HOST", "0.0.0.0");
        int httpPort = Integer.parseInt(System.getenv().getOrDefault("HTTP_PORT", "8080"));

        // Start HTTP server
        httpServer.start(httpHost, httpPort);

        logger.info("ParkingSystemApp initialized with ActorSystem: {}", actorSystem.path().name());
    }

    /**
     * Registers a new parking lot with the system.
     * This should be called by edge servers when they come online.
     *
     * @param parkId      Unique identifier for the parking lot
     * @param maxCapacity Maximum capacity of the parking lot
     */
    public void registerParkingLot(String parkId, int maxCapacity) {
        parkingLotManager.tell(new ParkingLotManagerActor.RegisterLotNoReply(parkId, maxCapacity));
    }

    /**
     * Gets list of all registered parking lots.
     * Edge servers use this to discover available lots.
     */
    public void getRegisteredLots() {
        // No-op here; HTTP path handles asks
    }

    /**
     * Sends occupancy update for a parking lot.
     * This is called by edge servers periodically with the current number of cars.
     * This REPLACES the old CarArrivedMessage/CarDepartedMessage approach.
     *
     * @param parkId    Parking lot identifier
     * @param occupancy Current number of cars in the lot (from sensors)
     */
    public void updateOccupancy(String parkId, int occupancy) {
        parkingLotManager.tell(new ParkingLotManagerActor.UpdateOccupancy(parkId, occupancy, System.currentTimeMillis()));
    }

    /**
     * Shuts down the actor system gracefully.
     */
    public void shutdown() {
        logger.info("Shutting down ParkingSystemApp");
        httpServer.stop();
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
        app.registerParkingLot("lot-01", 50);
        app.registerParkingLot("lot-02", 100);
        app.registerParkingLot("lot-03", 25);

        // Give the system a moment to process registrations
        try {
            Thread.sleep(500);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // Example: Edge servers send periodic occupancy updates
        logger.info("Simulating occupancy updates from edge servers...");
        
        // Edge server 1 sending occupancy updates for lot-01
        app.updateOccupancy("lot-01", 15);
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        app.updateOccupancy("lot-01", 18);

        // Edge server 2 sending occupancy updates for lot-02
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        app.updateOccupancy("lot-02", 45);

        // Edge server 1 sending occupancy updates for lot-03
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        app.updateOccupancy("lot-03", 8);

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
