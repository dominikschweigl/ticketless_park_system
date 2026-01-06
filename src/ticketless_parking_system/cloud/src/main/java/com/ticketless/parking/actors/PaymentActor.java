package com.ticketless.parking.actors;

import akka.actor.typed.Behavior;
import akka.actor.typed.ActorRef;
import akka.actor.typed.javadsl.Behaviors;
import akka.actor.typed.javadsl.ActorContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Typed PaymentActor tracks per-license-plate parking sessions and payment status.
 * Stores entry time, calculates price, marks paid, and deletes records on exit.
 */
public class PaymentActor {

    // Pricing config (simple pseudo implementation)
    public static final long MILLIS_PER_HOUR = 3600_000L;
    public static final int PRICE_PER_HOUR_CENTS = 200; // 2.00 per hour

    // Protocol
    public interface Command {}

    public static final class CarEntered implements Command {
        public final String licensePlate;
        public final long entryTimestamp;
        public CarEntered(String licensePlate, long entryTimestamp) {
            this.licensePlate = licensePlate;
            this.entryTimestamp = entryTimestamp;
        }
    }

    public static final class Pay implements Command {
        public final String licensePlate;
        public final ActorRef<PaymentStatus> replyTo;
        public Pay(String licensePlate, ActorRef<PaymentStatus> replyTo) {
            this.licensePlate = licensePlate;
            this.replyTo = replyTo;
        }
    }

    public static final class CheckOnLeave implements Command {
        public final String licensePlate;
        public final ActorRef<PaymentStatus> replyTo;
        public CheckOnLeave(String licensePlate, ActorRef<PaymentStatus> replyTo) {
            this.licensePlate = licensePlate;
            this.replyTo = replyTo;
        }
    }

    public static final class DeleteOnExit implements Command {
        public final String licensePlate;
        public final ActorRef<Ack> replyTo;
        public DeleteOnExit(String licensePlate, ActorRef<Ack> replyTo) {
            this.licensePlate = licensePlate;
            this.replyTo = replyTo;
        }
    }

    // Replies
    public static final class PaymentStatus {
        public final String licensePlate;
        public final boolean paid;
        public final long entryTimestamp;
        public final long currentTimestamp;
        public final int priceCents;
        public PaymentStatus(String licensePlate, boolean paid, long entryTimestamp, long currentTimestamp, int priceCents) {
            this.licensePlate = licensePlate;
            this.paid = paid;
            this.entryTimestamp = entryTimestamp;
            this.currentTimestamp = currentTimestamp;
            this.priceCents = priceCents;
        }
    }

    public static final class Ack { public static final Ack INSTANCE = new Ack(); private Ack() {} }

    // Internal state
    private static class Record {
        final long entryTimestamp;
        boolean paid;
        Record(long entryTimestamp) { this.entryTimestamp = entryTimestamp; this.paid = false; }
    }

    public static Behavior<Command> create() {
        return Behaviors.setup(ctx -> new BehaviorImpl(ctx).behavior());
    }

    private static class BehaviorImpl {
        private final ActorContext<Command> ctx;
        private final Logger log = LoggerFactory.getLogger(PaymentActor.class);
        private final Map<String, Record> sessions = new HashMap<>();

        BehaviorImpl(ActorContext<Command> ctx) { this.ctx = ctx; }

        Behavior<Command> behavior() {
            return Behaviors.receive(Command.class)
                    .onMessage(CarEntered.class, this::onCarEntered)
                    .onMessage(Pay.class, this::onPay)
                    .onMessage(CheckOnLeave.class, this::onCheckOnLeave)
                    .onMessage(DeleteOnExit.class, this::onDeleteOnExit)
                    .build();
        }

        private int calculatePriceCents(long entryTimestamp, long now) {
            long durationMillis = Math.max(0, now - entryTimestamp);
            double hours = (double) durationMillis / MILLIS_PER_HOUR;
            // simple rounding up to next 0.5 hour
            double billableHours = Math.ceil(hours * 2.0) / 2.0; // half-hour increments
            return (int) Math.round(billableHours * PRICE_PER_HOUR_CENTS);
        }

        private Behavior<Command> onCarEntered(CarEntered msg) {
            sessions.put(msg.licensePlate, new Record(msg.entryTimestamp));
            log.info("Payment: car entered {} at {}", msg.licensePlate, msg.entryTimestamp);
            return Behaviors.same();
        }

        private Behavior<Command> onPay(Pay msg) {
            long now = System.currentTimeMillis();
            Record rec = sessions.get(msg.licensePlate);
            if (rec == null) {
                msg.replyTo.tell(new PaymentStatus(msg.licensePlate, false, 0L, now, 0));
                return Behaviors.same();
            }
            int price = calculatePriceCents(rec.entryTimestamp, now);
            rec.paid = true; // mark as paid (pseudo)
            msg.replyTo.tell(new PaymentStatus(msg.licensePlate, true, rec.entryTimestamp, now, price));
            log.info("Payment: car {} marked paid: {} cents", msg.licensePlate, price);
            return Behaviors.same();
        }

        private Behavior<Command> onCheckOnLeave(CheckOnLeave msg) {
            long now = System.currentTimeMillis();
            Record rec = sessions.get(msg.licensePlate);
            if (rec == null) {
                msg.replyTo.tell(new PaymentStatus(msg.licensePlate, false, 0L, now, 0));
            } else {
                int price = calculatePriceCents(rec.entryTimestamp, now);
                msg.replyTo.tell(new PaymentStatus(msg.licensePlate, rec.paid, rec.entryTimestamp, now, price));
            }
            return Behaviors.same();
        }

        private Behavior<Command> onDeleteOnExit(DeleteOnExit msg) {
            sessions.remove(msg.licensePlate);
            log.info("Payment: car {} session removed on exit", msg.licensePlate);
            msg.replyTo.tell(Ack.INSTANCE);
            return Behaviors.same();
        }
    }
}

