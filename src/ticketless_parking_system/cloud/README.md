# Ticketless Parking System - Cloud Edition

A distributed parking management system built with Akka, designed to run on AWS ECS.

## Architecture

### System Design

This is a distributed parking management system with the following architecture:

```
┌─────────────────────────────────────────────────────────────┐
│             Cloud Parking System (AWS ECS)                   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ParkingLotManagerActor (Supervisor)                  │   │
│  │  - Registers new parking lots from edge servers       │   │
│  │  - Maintains registry of all active lots              │   │
│  │  - Routes occupancy updates to ParkingLotActors       │   │
│  └──────────────────────────────────────────────────────┘   │
│         │             │             │                        │
│         ▼             ▼             ▼                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │ParkingLotAct │ │ParkingLotAct │ │ParkingLotAct │         │
│  │ (lot-01)     │ │ (lot-02)     │ │ (lot-03)     │         │
│  │ Occupancy:   │ │ Occupancy:   │ │ Occupancy:   │         │
│  │ 18/50 cars   │ │ 45/100 cars  │ │ 8/25 cars    │         │
│  │ (from edge)  │ │ (from edge)  │ │ (from edge)  │         │
│  └──────────────┘ └──────────────┘ └──────────────┘         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ▲              ▲              ▲
         │              │              │
    ┌────┴──────┐  ┌────┴──────┐  ┌────┴──────┐
    │Edge Server│  │Edge Server│  │Edge Server│
    │   #1      │  │   #2      │  │   #3      │
    │           │  │           │  │           │
    │Register   │  │Register   │  │Register   │
    │lot-01     │  │lot-02     │  │lot-03     │
    │           │  │           │  │           │
    │Sensors    │  │Sensors    │  │Sensors    │
    │measure    │  │measure    │  │measure    │
    │occupancy  │  │occupancy  │  │occupancy  │
    │           │  │           │  │           │
    │Send       │  │Send       │  │Send       │
    │periodic   │  │periodic   │  │periodic   │
    │Occupancy  │  │Occupancy  │  │Occupancy  │
    │Messages   │  │Messages   │  │Messages   │
    └───────────┘  └───────────┘  └───────────┘
```

## Building

### Prerequisites

- Java 11+
- Maven 3.8.0+

### Build the Application

```bash
mvn clean package
```

This creates a fat JAR at `target/parking-system.jar` that includes all dependencies.

## Running Locally

```bash
java -jar target/parking-system.jar
```

## API Endpunkte

| Method | Endpoint                              | Beschreibung                                        |
| ------ | ------------------------------------- | --------------------------------------------------- |
| GET    | `/health`                             | Health Check                                        |
| GET    | `/api/parking-lots`                   | Alle registrierten Parkplätze abrufen               |
| POST   | `/api/parking-lots`                   | Parking Lot registrieren                            |
| GET    | `/api/parking-lots/{id}`              | Status eines spezifischen Parkplatzes abfragen      |
| DELETE | `/api/parking-lots/{id}`              | Parking Lot deregistrieren                          |
| POST   | `/api/occupancy`                      | Occupancy Update senden                             |
| POST   | `/api/bookings`                       | Parkplatz buchen                                    |
| DELETE | `/api/bookings`                       | Buchung stornieren                                  |
| POST   | `/api/payment/enter`                  | Fahrzeugeinfahrt registrieren (Startzeit speichern) |
| POST   | `/api/payment/pay`                    | Parkgebühr bezahlen                                 |
| GET    | `/api/payment/check?licensePlate=XYZ` | Zahlungsstatus beim Verlassen prüfen                |
| DELETE | `/api/payment/exit?licensePlate=XYZ`  | Zahlungsdatensatz nach Ausfahrt löschen             |

## Core Components

### Actors

#### ParkingLotManagerActor

Supervises all `ParkingLotActor` instances and handles:

- **RegisterParkMessage**: Register new parking lot from edge servers
- **GetRegisteredParksMessage**: Get list of all registered parking lots
- **OccupancyMessage**: Route occupancy update to appropriate lot
- **GetStatusMessage**: Query parking lot status

Maintains:

- Map of parkId → ParkingLotActor reference
- Map of parkId → maxCapacity

### ParkingLotActor

Manages a single parking lot. Tracks:

- Current occupancy (number of cars measured by edge server sensors)
- Maximum capacity
- Last update timestamp and source edge server ID

**Handled Messages:**

- `OccupancyMessage`: Receives occupancy from edge server sensors
- `GetStatusMessage`: Returns current status immediately

**State Model:**

- Simple mirror of what edge server measures via sensors
- No counting arrivals/departures
- No need for periodic broadcasts (edge server controls update frequency)
- Validates that occupancy ≤ maxCapacity

### PaymentActor

Manages payment processing for parking tickets:

- Tracks entry/exit events with timestamps
- Calculates parking fees based on duration
- Stores payment records

### BookingActor

Handles parking space reservations:

- Manages parking lot availability
- Publishes booking events to message queue
- Integrates with external booking systems

### RoutingActor

Routes users to appropriate parking lots:

- Finds nearby parking lots based on GPS coordinates
- Selects optimal lot based on occupancy and availability

## Messages

All messages are immutable/serializable and extend `ParkingLotMessage`:

### Parking Lot Registration

- **`RegisterParkMessage`**: Register new parking lot from edge server
- **`ParkRegisteredMessage`**: Confirmation of successful registration
- **`DeregisterParkMessage`**: Deregister a parking lot
- **`ParkDeregisteredMessage`**: Confirmation of successful deregistration

### Parking Lot Status and Occupancy

- **`GetParkingLotStatusMessage`**: Query status of a specific parking lot
- **`ParkingLotStatusMessage`**: Response containing parking lot status (occupancy, capacity, fullness)
- **`ParkingLotOccupancyMessage`**: Update occupancy from edge server sensors
- **`GetRegisteredParksMessage`**: Query list of all registered parking lots
- **`RegisteredParksListMessage`**: Response containing list of registered lots

### Nearby Parking Lot Discovery

- **`NearbyParkingLotsRequestMessage`**: Request parking lots near a GPS location
- **`NearbyParkingLotsResponseMessage`**: Response with nearby parking lots sorted by distance/availability

## Logging

Configured using Logback. Log levels can be adjusted in `src/main/resources/logback.xml`:

- `INFO`: Default level - informational messages
- `DEBUG`: Detailed debug information
- `WARN`: Warning messages
- `ERROR`: Error messages

Logs are written to:

- Console (stdout)
- File: `${LOG_PATH}/spring.log` (rotated daily, max 1GB total)
