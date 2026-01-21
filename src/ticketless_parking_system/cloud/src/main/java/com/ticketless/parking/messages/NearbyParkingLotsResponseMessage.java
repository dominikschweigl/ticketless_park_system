package com.ticketless.parking.messages;

import java.util.List;

/**
 * Response message containing nearby parking lots sorted by distance.
 */
public class NearbyParkingLotsResponseMessage extends ParkingLotMessage {
    private static final long serialVersionUID = 1L;

    private final List<NearbyLot> results;

    public NearbyParkingLotsResponseMessage(List<NearbyLot> results) {
        this.results = results;
    }

    public List<NearbyLot> getResults() {
        return results;
    }

    /**
     * Represents a parking lot with distance information.
     */
    public static class NearbyLot {
        private final String parkId;
        private final double lat;
        private final double lng;
        private final int maxCapacity;
        private final int currentOccupancy;
        private final int availableSpaces;
        private final double distanceMeters;

        public NearbyLot(String parkId, double lat, double lng, int maxCapacity,
                        int currentOccupancy, int availableSpaces, double distanceMeters) {
            this.parkId = parkId;
            this.lat = lat;
            this.lng = lng;
            this.maxCapacity = maxCapacity;
            this.currentOccupancy = currentOccupancy;
            this.availableSpaces = availableSpaces;
            this.distanceMeters = distanceMeters;
        }

        public String getParkId() {
            return parkId;
        }

        public double getLat() {
            return lat;
        }

        public double getLng() {
            return lng;
        }

        public int getMaxCapacity() {
            return maxCapacity;
        }

        public int getCurrentOccupancy() {
            return currentOccupancy;
        }

        public int getAvailableSpaces() {
            return availableSpaces;
        }

        public double getDistanceMeters() {
            return distanceMeters;
        }
    }
}
