package com.ticketless.parking.http;

import akka.actor.ActorRef;
import akka.actor.ActorSystem;
import akka.http.javadsl.Http;
import akka.http.javadsl.ServerBinding;
import akka.http.javadsl.model.ContentTypes;
import akka.http.javadsl.model.HttpResponse;
import akka.http.javadsl.model.StatusCodes;
import akka.http.javadsl.server.Route;
import akka.pattern.Patterns;
import com.google.gson.Gson;
import com.ticketless.parking.messages.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.concurrent.CompletionStage;

import static akka.http.javadsl.server.Directives.*;
import static akka.http.javadsl.server.PathMatchers.segment;

/**
 * HTTP Server for the Parking System to enable communication with Python edge servers.
 * Provides REST API endpoints for:
 * - Registering parking lots
 * - Sending occupancy updates
 * - Querying parking lot status
 */
public class ParkingHttpServer {
    private static final Logger logger = LoggerFactory.getLogger(ParkingHttpServer.class);
    private static final Duration ASK_TIMEOUT = Duration.ofSeconds(5);
    private static final long ENTITY_TIMEOUT_MS = 5000;

    private final ActorSystem actorSystem;
    private final ActorRef parkingLotManager;
    private final Gson gson;
    private CompletionStage<ServerBinding> binding;

    public ParkingHttpServer(ActorSystem actorSystem, ActorRef parkingLotManager) {
        this.actorSystem = actorSystem;
        this.parkingLotManager = parkingLotManager;
        this.gson = new Gson();
    }

    /**
     * Start the HTTP server on the specified port.
     */
    public CompletionStage<ServerBinding> start(String host, int port) {
        final Http http = Http.get(actorSystem);

        binding = http.newServerAt(host, port).bind(createRoutes());

        binding.thenAccept(b -> logger.info("HTTP Server started at http://{}:{}/", host, port))
                .exceptionally(ex -> {
                    logger.error("Failed to start HTTP server", ex);
                    return null;
        });

        return binding;
    }

    /**
     * Stop the HTTP server.
     */
    public CompletionStage<Void> stop() {
        if (binding != null) {
            return binding.thenCompose(ServerBinding::unbind).thenAccept(unbound -> {
                logger.info("HTTP Server stopped");
            });
        }
        return null;
    }

    /**
     * Define HTTP routes.
     */
    private Route createRoutes() {
        return concat(
            path("health", this::healthCheck),
            pathPrefix("api", () -> concat(
                path("parking-lots", () ->
                    post(() ->
                        extractRequestEntity(entity ->
                            onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem),
                                strictEntity -> registerParkingLot(strictEntity.getData().utf8String())
                            )
                        )
                    )
                ),
                path("occupancy", () ->
                    post(() ->
                        extractRequestEntity(entity ->
                            onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem),
                                strictEntity -> updateOccupancy(strictEntity.getData().utf8String())
                            )
                        )
                    )
                ),
                pathPrefix("parking-lots", () ->
                    path(segment(), parkId -> get(() -> getParkingLotStatus(parkId)))
                )
            ))
        );
    }

    /**
     * Health check endpoint.
     */
    private Route healthCheck() {
        return complete(HttpResponse.create()
                .withStatus(StatusCodes.OK)
                .withEntity(ContentTypes.APPLICATION_JSON, "{\"status\":\"healthy\"}"));
    }

    /**
     * Register a new parking lot.
     * POST /api/parking-lots
     * Body: {"parkId": "lot-01", "maxCapacity": 50}
     */
    private Route registerParkingLot(String jsonBody) {
        try {
            RegisterParkRequest request = gson.fromJson(jsonBody, RegisterParkRequest.class);

            logger.info("HTTP: Registering parking lot {} (capacity: {})",
                    request.parkId, request.maxCapacity);

            RegisterParkMessage message = new RegisterParkMessage(
                    request.parkId,
                    request.maxCapacity
            );

            CompletionStage<Object> response = Patterns.ask(parkingLotManager, message, ASK_TIMEOUT);

            return onSuccess(response, obj -> {
                if (obj instanceof ParkRegisteredMessage) {
                    ParkRegisteredMessage registered = (ParkRegisteredMessage) obj;
                    String json = gson.toJson(new RegisterParkResponse(
                            registered.getParkId(),
                            registered.getMaxCapacity(),
                            "registered"
                    ));
                    return complete(HttpResponse.create()
                            .withStatus(StatusCodes.CREATED)
                            .withEntity(ContentTypes.APPLICATION_JSON, json));
                } else {
                    return complete(StatusCodes.INTERNAL_SERVER_ERROR, "Unexpected response");
                }
            });
        } catch (Exception e) {
            logger.error("Error parsing register request", e);
            return complete(StatusCodes.BAD_REQUEST, "Invalid JSON");
        }
    }

    /**
     * Update parking lot occupancy.
     * POST /api/occupancy
     * Body: {"parkId": "lot-01", "currentOccupancy": 15}
     */
    private Route updateOccupancy(String jsonBody) {
        try {
            OccupancyUpdateRequest request = gson.fromJson(jsonBody, OccupancyUpdateRequest.class);

            logger.debug("HTTP: Occupancy update for {} - {} cars",
                    request.parkId, request.currentOccupancy);

            ParkingLotOccupancyMessage message = new ParkingLotOccupancyMessage(
                    request.parkId,
                    request.currentOccupancy,
                    System.currentTimeMillis()
            );

            parkingLotManager.tell(message, ActorRef.noSender());

            String json = gson.toJson(new OccupancyUpdateResponse("accepted", request.parkId, request.currentOccupancy));
            return complete(HttpResponse.create()
                    .withStatus(StatusCodes.ACCEPTED)
                    .withEntity(ContentTypes.APPLICATION_JSON, json));
        } catch (Exception e) {
            logger.error("Error parsing occupancy update", e);
            return complete(StatusCodes.BAD_REQUEST, "Invalid JSON");
        }
    }

    /**
     * Get parking lot status.
     * GET /api/parking-lots/{parkId}
     */
    private Route getParkingLotStatus(String parkId) {
        logger.debug("HTTP: Getting status for parking lot {}", parkId);

        GetParkingLotStatusMessage message = new GetParkingLotStatusMessage(parkId);
        CompletionStage<Object> response = Patterns.ask(parkingLotManager, message, ASK_TIMEOUT);

        return onSuccess(response, obj -> {
            if (obj instanceof ParkingLotStatusMessage) {
                ParkingLotStatusMessage status = (ParkingLotStatusMessage) obj;
                String json = gson.toJson(new ParkingLotStatusResponse(
                        status.getParkId(),
                        status.getCurrentOccupancy(),
                        status.getMaxCapacity(),
                        status.getAvailableSpaces()
                ));
                return complete(HttpResponse.create()
                        .withStatus(StatusCodes.OK)
                        .withEntity(ContentTypes.APPLICATION_JSON, json));
            } else {
                return complete(StatusCodes.NOT_FOUND, "Parking lot not found");
            }
        });
    }

    // DTOs for HTTP requests/responses
    public static class RegisterParkRequest {
        public String parkId;
        public int maxCapacity;
    }

    public static class RegisterParkResponse {
        public String parkId;
        public int maxCapacity;
        public String status;

        public RegisterParkResponse(String parkId, int maxCapacity, String status) {
            this.parkId = parkId;
            this.maxCapacity = maxCapacity;
            this.status = status;
        }
    }

    public static class OccupancyUpdateRequest {
        public String parkId;
        public int currentOccupancy;
    }

    public static class OccupancyUpdateResponse {
        public String status;
        public String parkId;
        public int currentOccupancy;

        public OccupancyUpdateResponse(String status, String parkId, int currentOccupancy) {
            this.status = status;
            this.parkId = parkId;
            this.currentOccupancy = currentOccupancy;
        }
    }

    public static class ParkingLotStatusResponse {
        public String parkId;
        public int currentOccupancy;
        public int maxCapacity;
        public int availableSpaces;

        public ParkingLotStatusResponse(String parkId, int currentOccupancy, int maxCapacity, int availableSpaces) {
            this.parkId = parkId;
            this.currentOccupancy = currentOccupancy;
            this.maxCapacity = maxCapacity;
            this.availableSpaces = availableSpaces;
        }
    }
}

