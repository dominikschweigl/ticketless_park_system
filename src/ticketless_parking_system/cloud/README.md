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

### Key Design Principles

1. **Source of Truth**: Edge servers (with sensors) are the SOURCE OF TRUTH. They measure actual occupancy and send it to cloud.

2. **Occupancy-Based Approach**: Instead of tracking individual car arrivals/departures, the system uses periodic occupancy snapshots.

3. **One Actor Per Parking Lot**: Each parking lot gets its own `ParkingLotActor` for isolation and independent scaling.

4. **Simple State Model**: Cloud mirrors occupancy received from edge servers; no complex event correlation needed.

5. **Eventual Consistency**: If an update is lost, the next occupancy message within 5-10 seconds corrects the state.

6. **Actor Model**: Uses Akka's actor model for concurrent handling of multiple parking lots and fault tolerance.

### Message Flow

#### Registration Flow
```
Edge Server
    │
    ├─ RegisterParkMessage(lot-id, capacity, edge-server-id)
    │
    ▼
ParkingLotManagerActor
    │
    ├─ Creates ParkingLotActor("lot-id", capacity)
    │
    └─▶ ParkRegisteredMessage(lot-id, capacity, actor-ref)
       
    Back to Edge Server
```

#### Occupancy Update Flow
```
Edge Server (via sensors measuring actual cars)
    │
    ├─ OccupancyMessage("lot-01", 18, timestamp, "edge-server-01")
    │
    ▼
ParkingLotManagerActor
    │
    ├─ Routes to ParkingLotActor("lot-01")
    │
    ▼
ParkingLotActor("lot-01")
    │
    ├─ Updates occupancy: 18/50
    └─ Logs: "Occupancy update for lot-01: 18/50 cars"
```
    ├─ Logs arrival
    │
    └─ (Every 5 seconds)
       ▼
       CarParkStateUpdateMessage sent
       (current: 23/50, timestamp)
```

### Actor Model: Losse vs Strongly Typed

- **Actor Model**: Akka actors are built on the actor model - they process messages sequentially in a mailbox
- **Non-blocking**: All message processing is non-blocking; heavy operations should be offloaded
- **Supervision**: Actors can supervise child actors and define failure recovery strategies
- **Remote Transparency**: Same code works locally, in a cluster, or distributed across machines

## Project Structure

```
.
├── src/
│   └── main/
│       ├── java/
│       │   └── com/ticketless/parking/
│       │       ├── actors/         # Akka actors
│       │       ├── messages/       # Actor messages
│       │       └── app/            # Application entry point
│       └── resources/
│           ├── application.conf    # Akka configuration
│           └── logback.xml         # Logging configuration
├── pom.xml                         # Maven dependencies
├── Dockerfile                      # Docker image definition
└── README.md                       # This file
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
  -e PARKING_ENVIRONMENT=development \
  -e PARKING_ENABLE_METRICS=false \
  parking-system:latest
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
        "command": ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 10
      }
    }
  ]
}
```

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

## Edge Server Integration

### Typical Edge Server Workflow

The edge server is responsible for measuring actual occupancy via sensors and periodically reporting it:

```java
// 1. Edge server starts and registers its parking lots
ParkingSystemClient client = new ParkingSystemClient("cloud-system-url");
client.registerParkingLot("lot-01", 50, "edge-server-01");
client.registerParkingLot("lot-02", 100, "edge-server-01");

// 2. Periodically query sensors and send occupancy updates
while (running) {
    // Read from parking lot sensors (your sensor integration here)
    int currentOccupancy = sensorSystem.readParkingLotOccupancy("lot-01");
    
    // Send occupancy snapshot to cloud (this is the SOURCE OF TRUTH)
    client.updateOccupancy("lot-01", currentOccupancy, "edge-server-01");
    
    // Sleep for a reasonable interval (e.g., 5-10 seconds)
    Thread.sleep(5000);
    
    // Optionally poll cloud for status
    CarParkStatus status = client.getParkStatus("lot-01");
    System.out.println("Cloud sees: " + status.getCurrentOccupancy() + "/" + status.getMaxCapacity());
}
```

### Advantages of Occupancy-Based Approach

1. **Simple**: Edge server just reads a sensor and sends a number
2. **Robust**: Works even if many messages are lost (next update corrects state)
3. **Single Source of Truth**: Edge server sensors are authoritative
4. **No Event Ordering Issues**: Occupancy is absolute, not relative
5. **Handles Sensor Errors**: If sensor reads wrong, only that update is affected
6. **No Clock Sync Required**: Edge server timestamps not strictly needed
7. **Easy Debugging**: You can see exactly what sensors reported

### Example: Edge Server Integration Code

Edge servers don't need the complex CarArrivedMessage/CarDepartedMessage logic anymore. Instead:

```java
// OLD APPROACH (replaced):
// client.sendCarArrived("lot-01_car-001");
// client.sendCarDeparted("lot-01_car-001");

// NEW APPROACH (much simpler):
int occupancy = sensorSystem.countParkedCars("lot-01");
client.updateOccupancy("lot-01", occupancy, "edge-server-01");
```

### Fault Tolerance

**What happens if a message is lost?**
- The next occupancy update (5-10 seconds later) contains the correct state
- Cloud automatically converges to correct occupancy
- No manual reconciliation needed
- Edge server can safely send updates at its own frequency

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
