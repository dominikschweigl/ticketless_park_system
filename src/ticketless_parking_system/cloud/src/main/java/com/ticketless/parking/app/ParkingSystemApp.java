package com.ticketless.parking.app;

import akka.actor.typed.ActorSystem;
import akka.actor.typed.ActorRef;
import akka.actor.typed.Props;
import com.typesafe.config.Config;
import com.typesafe.config.ConfigFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.function.BiConsumer;

import com.ticketless.parking.actors.ParkingLotManagerActor;
import com.ticketless.parking.actors.PaymentActor;
import com.ticketless.parking.http.ParkingHttpServer;
import com.ticketless.parking.actors.BookingActor;
import io.nats.client.Connection;
import io.nats.client.Nats;
import java.nio.charset.StandardCharsets;

/**
 * Main entry point for the Ticketless Parking System application.
 */
public class ParkingSystemApp {
    private static final Logger logger = LoggerFactory.getLogger(ParkingSystemApp.class);

    private final ActorSystem<ParkingLotManagerActor.Command> actorSystem;
    private final ActorRef<ParkingLotManagerActor.Command> parkingLotManager;
    private final ActorRef<PaymentActor.Command> paymentActor;
    private final ActorRef<BookingActor.Command> bookingActor;
    private final Connection parkinglot_mq;
    private final ParkingHttpServer httpServer;

    /**
     * Initializes the Parking System application.
     */
    public ParkingSystemApp() {
        Config config = ConfigFactory.load();
        this.actorSystem = ActorSystem.create(ParkingLotManagerActor.create(), "ParkingSystem", config);
        this.parkingLotManager = actorSystem;
        this.paymentActor = actorSystem.systemActorOf(PaymentActor.create(), "payment-actor", Props.empty());
        // NATS
        String natsUrl = System.getenv().getOrDefault("NATS_URL", "nats://localhost:4222");
        try {
            this.parkinglot_mq = Nats.connect(natsUrl);
        } catch (Exception e) {
            throw new RuntimeException("Failed to connect to NATS at " + natsUrl, e);
        }
        BiConsumer<String, String> publisher = (subject, json) -> this.parkinglot_mq.publish(subject, json.getBytes(StandardCharsets.UTF_8));
        this.bookingActor = actorSystem.systemActorOf(BookingActor.create(publisher), "booking-actor", Props.empty());

        // Initialize HTTP server
        this.httpServer = new ParkingHttpServer(actorSystem, parkingLotManager, paymentActor, bookingActor);

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
    public void registerParkingLot(String parkId, int maxCapacity, double lat, double lng) {
        parkingLotManager.tell(new ParkingLotManagerActor.RegisterLotNoReply(parkId, maxCapacity, lat, lng));
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
        try { if (parkinglot_mq != null) parkinglot_mq.close(); } catch (Exception ignore) {}
        actorSystem.terminate();
    }

    /**
     * Main method - entry point for the application.
     * Supports AWS ECS environment variables for configuration.
     */
    public static void main(String[] args) {
        logger.info("Starting Ticketless Parking System");

        ParkingSystemApp app = new ParkingSystemApp();

        // Keep the application running
        logger.info("Parking System is running. Press Ctrl+C to exit.");
        try {
            System.in.read();
        } catch (IOException e) {
            logger.error("Error reading input", e);
        }
    }
}
