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

Or with custom memory settings:

```bash
java -Xmx512m -Xms256m -jar target/parking-system.jar
```

## Docker Deployment

### Build Docker Image

```bash
docker build -t parking-system:latest .
```

### Run Docker Container

```bash
docker run -it --rm \
  -p 8080:8080 \
  -e PARKING_ENVIRONMENT=development \
  -e PARKING_ENABLE_METRICS=false \
  -e HTTP_PORT=8080 \
  parking-system:latest
```

Test the HTTP API:

```bash
# Health check
curl http://localhost:8080/health

# Get all registered parking lots
curl http://localhost:8080/api/parking-lots

# Register parking lot
curl -X POST http://localhost:8080/api/parking-lots \
  -H "Content-Type: application/json" \
  -d '{"parkId":"lot-test","maxCapacity":100}'

# Update occupancy
curl -X POST http://localhost:8080/api/occupancy \
  -H "Content-Type: application/json" \
  -d '{"parkId":"lot-test","currentOccupancy":25}'

# Get status
curl http://localhost:8080/api/parking-lots/lot-test

# Deregister parking lot
curl -X DELETE http://localhost:8080/api/parking-lots/lot-test
```

### AWS ECS Deployment

#### Create ECR Repository

```bash
aws ecr create-repository --repository-name parking-system --region us-east-1
```

#### Push Image to ECR

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

docker tag parking-system:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/parking-system:latest

docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/parking-system:latest
```

#### Create ECS Task Definition

```json
{
  "family": "parking-system",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "parking-system",
      "image": "<AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/parking-system:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "hostPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "PARKING_ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "PARKING_ENABLE_METRICS",
          "value": "true"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/parking-system",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 10
      }
    }
  ]
}
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

### ParkingLotManagerActor

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

### Messages

All messages implement `CarParkMessage` and are immutable/serializable:

- **`RegisterParkMessage`**: Register new parking lot (from edge server)
- **`ParkRegisteredMessage`**: Confirmation with actor reference (to edge server)
- **`GetRegisteredParksMessage`**: Query for registered lots
- **`RegisteredParksListMessage`**: Response with lot list
- **`OccupancyMessage`**: Occupancy update from edge server (replaces arrival/departure messages)
- **`GetStatusMessage`**: Status query
- **`CarParkStatusMessage`**: Status response (occupancy, capacity, isFull flag)

## Configuration

Environment variables (override `application.conf`):

- `PARKING_ENVIRONMENT`: Set to `production`, `development`, or `local`
- `PARKING_ENABLE_METRICS`: Enable metrics collection (true/false)
- `PARKING_HEALTH_CHECK_PORT`: Health check server port (default: 8080)

## Extending the System

### Adding New Messages

Create a new class extending `CarParkMessage`:

```java
public class ReserveSpaceMessage extends CarParkMessage {
    private final String reservationId;

    public ReserveSpaceMessage(String reservationId) {
        this.reservationId = reservationId;
    }

    public String getReservationId() {
        return reservationId;
    }
}
```

### Adding New Behavior to CarParkActor

Add handler in `createReceive()`:

```java
@Override
public Receive createReceive() {
    return receiveBuilder()
        .match(ReserveSpaceMessage.class, this::handleReserveSpace)
        // ... other handlers
        .build();
}

private void handleReserveSpace(ReserveSpaceMessage message) {
    // Implementation
}
```

## Extending the System

### Adding New Messages

Create a new class extending `CarParkMessage`:

```java
public class ReserveSpaceMessage extends CarParkMessage {
    private final String reservationId;

    public ReserveSpaceMessage(String reservationId) {
        this.reservationId = reservationId;
    }

    public String getReservationId() {
        return reservationId;
    }
}
```

### Adding New Behavior to CarParkActor

Add handler in `createReceive()`:

```java
@Override
public Receive createReceive() {
    return receiveBuilder()
        .match(ReserveSpaceMessage.class, this::handleReserveSpace)
        // ... other handlers
        .build();
}

private void handleReserveSpace(ReserveSpaceMessage message) {
    // Implementation
}
```

## Logging

Configured using Logback. Log levels can be adjusted in `logback.xml`:

- `INFO`: Default level - informational messages
- `DEBUG`: Detailed debug information
- `WARN`: Warning messages
- `ERROR`: Error messages

Logs are written to:

- Console (stdout)
- File: `${LOG_PATH}/spring.log` (rotated daily, max 1GB total)

## Testing

Run tests with:

```bash
mvn test
```

## License

Internal project - do not distribute

## Support

For issues and questions, contact the development team.
