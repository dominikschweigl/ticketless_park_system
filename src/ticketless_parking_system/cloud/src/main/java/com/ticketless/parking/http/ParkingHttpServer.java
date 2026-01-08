package com.ticketless.parking.http;

import akka.actor.typed.ActorRef;
import akka.actor.typed.ActorSystem;
import akka.actor.typed.Scheduler;
import akka.actor.typed.javadsl.AskPattern;
import akka.http.javadsl.Http;
import akka.http.javadsl.ServerBinding;
import akka.http.javadsl.model.ContentTypes;
import akka.http.javadsl.model.HttpResponse;
import akka.http.javadsl.model.StatusCodes;
import akka.http.javadsl.server.Route;
import com.google.gson.Gson;
import com.ticketless.parking.actors.ParkingLotManagerActor;
import com.ticketless.parking.actors.PaymentActor;
import com.ticketless.parking.actors.BookingActor;
import com.ticketless.parking.messages.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.concurrent.CompletionStage;

import static akka.http.javadsl.server.Directives.*;
import static akka.http.javadsl.server.PathMatchers.segment;

/**
 * HTTP Server for the Parking System to enable communication with Python edge servers.
 */
public class ParkingHttpServer {
    private static final Logger logger = LoggerFactory.getLogger(ParkingHttpServer.class);
    private static final Duration ASK_TIMEOUT = Duration.ofSeconds(5);
    private static final long ENTITY_TIMEOUT_MS = 5000;

    private final ActorSystem<?> actorSystem;
    private final Scheduler scheduler;
    private final ActorRef<ParkingLotManagerActor.Command> parkingLotManager;
    private final ActorRef<PaymentActor.Command> paymentActor;
    private final ActorRef<BookingActor.Command> bookingActor;
    private final Gson gson;
    private CompletionStage<ServerBinding> binding;

    public ParkingHttpServer(ActorSystem<?> actorSystem,
                             ActorRef<ParkingLotManagerActor.Command> parkingLotManager,
                             ActorRef<PaymentActor.Command> paymentActor,
                             ActorRef<BookingActor.Command> bookingActor) {
        this.actorSystem = actorSystem;
        this.scheduler = actorSystem.scheduler();
        this.parkingLotManager = parkingLotManager;
        this.paymentActor = paymentActor;
        this.bookingActor = bookingActor;
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
                path("occupancy", () ->
                    post(() ->
                        extractRequestEntity(entity ->
                            onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem),
                                strictEntity -> updateOccupancy(strictEntity.getData().utf8String())
                            )
                        )
                    )
                ),
                pathPrefix("parking-lots", () -> concat(
                    pathEnd(() -> concat(
                        get(this::getRegisteredParkingLots),
                        post(() ->
                            extractRequestEntity(entity ->
                                onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem),
                                    strictEntity -> registerParkingLot(strictEntity.getData().utf8String())
                                )
                            )
                        )
                    )),
                    path(segment(), parkId -> concat(
                        get(() -> getParkingLotStatus(parkId)),
                        delete(() -> deregisterParkingLot(parkId))
                    ))
                )),
                pathPrefix("bookings", () -> concat(
                    // Create booking
                    post(() -> extractRequestEntity(entity -> onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem), strict ->
                        createBooking(strict.getData().utf8String())
                    ))
                    ),
                    // Cancel booking
                    delete(() -> extractRequestEntity(entity -> onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem), strict ->
                        cancelBooking(strict.getData().utf8String())
                    )))
                )),
                pathPrefix("payment", () -> concat(
                    // Car enters: record entry timestamp
                    path("enter", () -> post(() ->
                        extractRequestEntity(entity -> onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem), strict ->
                            carEnter(strict.getData().utf8String())
                        ))
                    )),
                    // Pay: mark as paid, compute price
                    path("pay", () -> post(() ->
                        extractRequestEntity(entity -> onSuccess(() -> entity.toStrict(ENTITY_TIMEOUT_MS, actorSystem), strict ->
                            pay(strict.getData().utf8String())
                        ))
                    )),
                    // Check on leave: verify payment and give price
                    path("check", () -> get(() ->
                        parameter("licensePlate", lp -> checkOnLeave(lp))
                    )),
                    // Delete record after exit
                    path("exit", () -> delete(() ->
                        parameter("licensePlate", lp -> deleteOnExit(lp))
                    ))
                ))
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
     * Get all registered parking lots.
     * GET /api/parking-lots
     */
    private Route getRegisteredParkingLots() {
        logger.debug("HTTP: Getting all registered parking lots");

        CompletionStage<RegisteredParksListMessage> response = AskPattern.ask(
                parkingLotManager,
                (ActorRef<RegisteredParksListMessage> replyTo) -> new ParkingLotManagerActor.GetRegistered(replyTo),
                ASK_TIMEOUT,
                scheduler
        );

        return onSuccess(response, parksListMessage -> {
            String json = gson.toJson(new RegisteredParksResponse(parksListMessage.getParks()));
            return complete(HttpResponse.create()
                    .withStatus(StatusCodes.OK)
                    .withEntity(ContentTypes.APPLICATION_JSON, json));
        });
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

            CompletionStage<ParkRegisteredMessage> response = AskPattern.ask(
                    parkingLotManager,
                    (ActorRef<ParkRegisteredMessage> replyTo) -> new ParkingLotManagerActor.RegisterLot(request.parkId, request.maxCapacity, request.lat, request.lng, replyTo),
                    ASK_TIMEOUT,
                    scheduler
            );

            return onSuccess(response, registered -> {
                String json = gson.toJson(new RegisterParkResponse(
                        registered.getParkId(),
                        registered.getMaxCapacity(),
                        "registered"
                ));
                return complete(HttpResponse.create()
                        .withStatus(StatusCodes.CREATED)
                        .withEntity(ContentTypes.APPLICATION_JSON, json));
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

            parkingLotManager.tell(new ParkingLotManagerActor.UpdateOccupancy(
                    request.parkId,
                    request.currentOccupancy,
                    System.currentTimeMillis()
            ));

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

        CompletionStage<ParkingLotStatusMessage> response = AskPattern.ask(
                parkingLotManager,
                (ActorRef<ParkingLotStatusMessage> replyTo) -> new ParkingLotManagerActor.GetStatus(parkId, replyTo),
                ASK_TIMEOUT,
                scheduler
        );

        return onSuccess(response, status -> {
            String json = gson.toJson(new ParkingLotStatusResponse(
                    status.getParkId(),
                    status.getCurrentOccupancy(),
                    status.getMaxCapacity(),
                    status.getAvailableSpaces(),
                    status.getLat(),
                    status.getLng()
            ));
            return complete(HttpResponse.create()
                    .withStatus(StatusCodes.OK)
                    .withEntity(ContentTypes.APPLICATION_JSON, json));
        });
    }

    /**
     * Deregister a parking lot.
     * DELETE /api/parking-lots/{parkId}
     */
    private Route deregisterParkingLot(String parkId) {
        logger.info("HTTP: Deregistering parking lot {}", parkId);

        CompletionStage<ParkDeregisteredMessage> response = AskPattern.ask(
                parkingLotManager,
                (ActorRef<ParkDeregisteredMessage> replyTo) -> new ParkingLotManagerActor.DeregisterLot(parkId, replyTo),
                ASK_TIMEOUT,
                scheduler
        );

        return onSuccess(response, deregistered -> {
            String json = gson.toJson(new DeregisterParkResponse(
                    deregistered.getParkId(),
                    "deregistered"
            ));
            return complete(HttpResponse.create()
                    .withStatus(StatusCodes.OK)
                    .withEntity(ContentTypes.APPLICATION_JSON, json));
        });
    }

    /**
     * Car enters the parking: record entry timestamp.
     * POST /api/payment/enter
     * Body: {"licensePlate": "ABC123", "entryTimestamp": 1633072800000}
     */
    private Route carEnter(String jsonBody) {
        try {
            CarEnterRequest req = gson.fromJson(jsonBody, CarEnterRequest.class);
            long ts = req.entryTimestamp != null ? req.entryTimestamp : System.currentTimeMillis();
            paymentActor.tell(new PaymentActor.CarEntered(req.licensePlate, ts));
            return complete(StatusCodes.ACCEPTED, "recorded");
        } catch (Exception e) {
            logger.error("Error parsing car enter", e);
            return complete(StatusCodes.BAD_REQUEST, "Invalid JSON");
        }
    }

    /**
     * Pay for the parking: mark as paid and compute price.
     * POST /api/payment/pay
     * Body: {"licensePlate": "ABC123"}
     */
    private Route pay(String jsonBody) {
        try {
            PayRequest req = gson.fromJson(jsonBody, PayRequest.class);
            var fut = AskPattern.ask(paymentActor,
                    (ActorRef<PaymentActor.PaymentStatus> reply) -> new PaymentActor.Pay(req.licensePlate, reply),
                    ASK_TIMEOUT,
                    scheduler);
            return onSuccess(fut, status -> {
                String json = gson.toJson(status);
                return complete(StatusCodes.OK, json);
            });
        } catch (Exception e) {
            logger.error("Error parsing pay", e);
            return complete(StatusCodes.BAD_REQUEST, "Invalid JSON");
        }
    }

    /**
     * Check payment status on leave: verify payment and provide price.
     * GET /api/payment/check?licensePlate=ABC123
     */
    private Route checkOnLeave(String licensePlate) {
        var fut = AskPattern.ask(paymentActor,
                (ActorRef<PaymentActor.PaymentStatus> reply) -> new PaymentActor.CheckOnLeave(licensePlate, reply),
                ASK_TIMEOUT,
                scheduler);
        return onSuccess(fut, status -> complete(StatusCodes.OK, gson.toJson(status)));
    }

    /**
     * Delete payment record after exit.
     * DELETE /api/payment/exit?licensePlate=ABC123
     */
    private Route deleteOnExit(String licensePlate) {
        var fut = AskPattern.ask(paymentActor,
                (ActorRef<PaymentActor.Ack> reply) -> new PaymentActor.DeleteOnExit(licensePlate, reply),
                ASK_TIMEOUT,
                scheduler);
        return onSuccess(fut, ack -> complete(StatusCodes.OK, "deleted"));
    }

    /**
     * Create a booking.
     * POST /api/bookings
     * Body: {"parkId": "lot-01", "licensePlate": "ABC123"}
     */
    private Route createBooking(String jsonBody) {
        try {
            BookingRequest req = gson.fromJson(jsonBody, BookingRequest.class);
            var fut = AskPattern.ask(bookingActor,
                    (ActorRef<BookingActor.BookingConfirmation> reply) -> new BookingActor.Book(req.parkId, req.licensePlate, reply),
                    ASK_TIMEOUT,
                    scheduler);
            return onSuccess(fut, conf -> complete(StatusCodes.ACCEPTED, gson.toJson(new BookingResponse(conf.parkId, conf.licensePlate, conf.status))));
        } catch (Exception e) {
            logger.error("Error parsing booking request", e);
            return complete(StatusCodes.BAD_REQUEST, "Invalid JSON");
        }
    }

    /**
     * Cancel a booking.
     * DELETE /api/bookings
     * Body: {"parkId": "lot-01", "licensePlate": "ABC123"}
     */
    private Route cancelBooking(String jsonBody) {
        try {
            CancelBookingRequest req = gson.fromJson(jsonBody, CancelBookingRequest.class);
            var fut = AskPattern.ask(bookingActor,
                    (ActorRef<BookingActor.BookingConfirmation> reply) -> new BookingActor.Cancel(req.parkId, req.licensePlate, reply),
                    ASK_TIMEOUT,
                    scheduler);
            return onSuccess(fut, conf -> complete(StatusCodes.OK, gson.toJson(new BookingResponse(conf.parkId, conf.licensePlate, conf.status))));
        } catch (Exception e) {
            logger.error("Error parsing cancel booking request", e);
            return complete(StatusCodes.BAD_REQUEST, "Invalid JSON");
        }
    }

    // DTOs for HTTP requests/responses
    public static class RegisterParkRequest { public String parkId; public int maxCapacity; public double lat; public double lng;}
    public static class RegisterParkResponse { public String parkId; public int maxCapacity; public String status; public RegisterParkResponse(String parkId, int maxCapacity, String status) { this.parkId = parkId; this.maxCapacity = maxCapacity; this.status = status; } }
    public static class OccupancyUpdateRequest { public String parkId; public int currentOccupancy; }
    public static class OccupancyUpdateResponse { public String status; public String parkId; public int currentOccupancy; public OccupancyUpdateResponse(String status, String parkId, int currentOccupancy) { this.status = status; this.parkId = parkId; this.currentOccupancy = currentOccupancy; } }
    public static class ParkingLotStatusResponse {public String parkId;public int currentOccupancy;public int maxCapacity;public int availableSpaces;public double lat;public double lng;public ParkingLotStatusResponse(String parkId,int currentOccupancy,int maxCapacity,int availableSpaces,double lat,double lng) {this.parkId = parkId;this.currentOccupancy = currentOccupancy;this.maxCapacity = maxCapacity;this.availableSpaces = availableSpaces;this.lat = lat;this.lng = lng;}}
    public static class RegisteredParksResponse { public java.util.Map<String, Integer> parks; public RegisteredParksResponse(java.util.Map<String, Integer> parks) { this.parks = parks; } }
    public static class DeregisterParkResponse { public String parkId; public String status; public DeregisterParkResponse(String parkId, String status) { this.parkId = parkId; this.status = status; } }
    // Payment DTOs
    public static class CarEnterRequest { public String licensePlate; public Long entryTimestamp; }
    public static class PayRequest { public String licensePlate; }
    // Booking DTO
    public static class BookingRequest { public String parkId; public String licensePlate; }
    public static class BookingResponse { public String parkId; public String licensePlate; public String status; public BookingResponse(String parkId, String licensePlate, String status) { this.parkId = parkId; this.licensePlate = licensePlate; this.status = status; } }
    public static class CancelBookingRequest { public String parkId; public String licensePlate; }
}
