package com.ticketless.parking.messages;

/**
 * Request message for finding nearby parking lots.
 */
public class NearbyParkingLotsRequestMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final double userLat;
    private final double userLng;
    private final int limit;
    private final boolean onlyAvailable;

    public NearbyParkingLotsRequestMessage(double userLat, double userLng, int limit, boolean onlyAvailable) {
        this.userLat = userLat;
        this.userLng = userLng;
        this.limit = limit;
        this.onlyAvailable = onlyAvailable;
    }

    public double getUserLat() {
        return userLat;
    }

    public double getUserLng() {
        return userLng;
    }

    public int getLimit() {
        return limit;
    }

    public boolean isOnlyAvailable() {
        return onlyAvailable;
    }
}
