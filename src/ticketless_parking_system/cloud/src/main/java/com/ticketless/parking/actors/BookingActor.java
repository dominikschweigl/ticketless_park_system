package com.ticketless.parking.actors;

import akka.actor.typed.Behavior;
import akka.actor.typed.ActorRef;
import akka.actor.typed.javadsl.Behaviors;
import akka.actor.typed.javadsl.ActorContext;
import com.google.gson.Gson;

import java.util.HashMap;
import java.util.Map;
import java.util.function.BiConsumer;

public class BookingActor {
    public interface Command {}

    public static final class Book implements Command {
        public final String parkId;
        public final String licensePlate;
        public final ActorRef<BookingConfirmation> replyTo;
        public Book(String parkId, String licensePlate, ActorRef<BookingConfirmation> replyTo) {
            this.parkId = parkId; this.licensePlate = licensePlate; this.replyTo = replyTo;
        }
    }

    public static final class Cancel implements Command {
        public final String parkId;
        public final String licensePlate;
        public final ActorRef<BookingConfirmation> replyTo;
        public Cancel(String parkId, String licensePlate, ActorRef<BookingConfirmation> replyTo) {
            this.parkId = parkId; this.licensePlate = licensePlate; this.replyTo = replyTo;
        }
    }

    public static final class BookingConfirmation {
        public final String parkId; public final String licensePlate; public final String status;
        public BookingConfirmation(String parkId, String licensePlate, String status) { this.parkId = parkId; this.licensePlate = licensePlate; this.status = status; }
    }

    public static Behavior<Command> create(BiConsumer<String, String> publisher) {
        return Behaviors.setup(ctx -> new BehaviorImpl(ctx, publisher).behavior());
    }

    private static class BehaviorImpl {
        private final ActorContext<Command> ctx;
        private final BiConsumer<String, String> publisher;
        private final Gson gson = new Gson();
        BehaviorImpl(ActorContext<Command> ctx, BiConsumer<String, String> publisher) { this.ctx = ctx; this.publisher = publisher; }

        Behavior<Command> behavior() {
            return Behaviors.receive(Command.class)
                    .onMessage(Book.class, this::onBook)
                    .onMessage(Cancel.class, this::onCancel)
                    .build();
        }

        private Behavior<Command> onBook(Book msg) {
            Map<String, Object> payload = new HashMap<>();
            payload.put("action", "book");
            payload.put("licensePlate", msg.licensePlate);
            String json = gson.toJson(payload);
            String subject = "booking." + msg.parkId;
            publisher.accept(subject, json);
            msg.replyTo.tell(new BookingConfirmation(msg.parkId, msg.licensePlate, "queued"));
            return Behaviors.same();
        }

        private Behavior<Command> onCancel(Cancel msg) {
            Map<String, Object> payload = new HashMap<>();
            payload.put("action", "cancel");
            payload.put("licensePlate", msg.licensePlate);
            String json = gson.toJson(payload);
            String subject = "booking." + msg.parkId;
            publisher.accept(subject, json);
            msg.replyTo.tell(new BookingConfirmation(msg.parkId, msg.licensePlate, "canceled"));
            return Behaviors.same();
        }
    }
}
