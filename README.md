# ticketless_park_system

## Overview

A distributed parking system that uses license plate detection to enable ticketless parking. Vehicles are detected at entry and exit points, and customers can pay using their license plate number through a web application or payment station.

## System Architecture

The system consists of four main layers:

### 1. IoT Layer (Edge Devices)

- **Camera Simulators**: Generate camera feeds at entry/exit points
- **Barrier Controllers**: Manage physical barriers at entry/exit gates
- **Dashboard**: Real-time monitoring web interface with WebSocket support

### 2. Edge Layer

- **Edge Server**: License plate detection and local processing
- **Local Database**: SQLite database for parking session tracking
- **ML Models**: YOLOv11 for license plate detection + EasyOCR for text recognition
- **Cloud Synchronization**: Bidirectional communication with cloud backend

### 3. Cloud Layer (Akka-based)

- **Parking Lot Manager**: Supervises all parking lots, handles registration
- **Payment Actor**: Tracks parking sessions, calculates pricing, manages payments
- **Booking Actor**: Handles advance parking reservations
- **Routing Actor**: Geographic queries for nearby parking lots
- **NATS Integration**: Message queue for edge-cloud communication

### 4. Frontend Layer

- **Web Application**: React-based UI for payments and reservations
- **Real-time Updates**: Live parking capacity information
- **Geolocation**: Find nearby parking lots based on user location

## Communication Flow

```
┌─────────────┐     NATS      ┌──────────────┐    HTTP/NATS   ┌─────────────┐
│   Camera    │──────────────▶│ Edge Server  │───────────────▶│   Cloud     │
│  Simulator  │               │ (Detection)  │                │   (Akka)    │
└─────────────┘               └──────┬───────┘                └──────┬──────┘
                                     │                                │
                                     │ NATS                           │ HTTP
                                     ▼                                ▼
                              ┌─────────────┐                  ┌──────────┐
                              │  Barrier    │                  │  Webapp  │
                              │ Controller  │                  │ (React)  │
                              └─────────────┘                  └──────────┘
```

## How to Run

### Edge stack (Docker Compose, local)

- Prereqs: Docker + Docker Compose, image assets in `./data` (Cars\*.png, Empty.png).
- Start services (NATS, camera, barriers, dashboard, edge):
  ```bash
  docker-compose up --build
  ```
- Available locally after startup:
  - NATS monitoring UI: http://localhost:8222
  - Dashboard (live feeds + barrier state): http://localhost:8000
  - Edge server: internal on `parking-net` (no public port); talks to cloud via `CLOUD_URL`/`CLOUD_NATS_URL` envs.
- Stop/cleanup:
  ```bash
  docker-compose down        # stop
  docker-compose down -v     # stop and remove volumes
  ```

### Cloud stack (Terraform, AWS)

- Prereqs: AWS credentials, `terraform`, built artifacts (`cloud/target/parking-system.jar`, `webapp/dist`).
- Deploy:
  ```bash
  terraform init
  terraform apply
  ```
- After `apply`, note outputs and wire the edge stack to them:
  - `akka_app_public_ip` → set `CLOUD_URL=http://<ip>:8080`
  - `nats_public_ip` → set `CLOUD_NATS_URL=nats://<ip>:4222`
  - `webapp_public_ip` → customer UI at http://<ip>
- Available remotely after deploy:
  - Cloud API (Akka): http://<akka_app_public_ip>:8080 (health: `/health`, parking: `/api/parking-lots`)
  - Cloud NATS: nats://<nats_public_ip>:4222
  - Webapp: http://<webapp_public_ip>
- Destroy when done:
  ```bash
  terraform destroy
  ```

## Camera Stream Simulation

### Overview

The camera simulation module (`camera.py`) is responsible for generating realistic camera streams at entry and exit points of the parking facility. It continuously publishes frames to a NATS message queue, simulating real-world camera feeds that would be processed by the edge server for license plate detection.

### How It Works

The camera simulator operates with two independent camera streams:

#### Entry Camera

- Continuously cycles through car images from the license plate detection dataset
- Displays each car image for a fixed duration (`DISPLAY_TIME = 5.0` seconds)
- Alternates between showing a car and an empty street scene
- Publishes frames to the `camera.entry` NATS subject at regular intervals

#### Exit Camera

- Monitors the entry stream and maintains consistency with it
- Only shows cars leaving that have previously entered through the entry camera
- Uses a probabilistic model to determine when cars exit
- Tracks the duration each car stays in the parking lot with randomly sampled times
- Publishes frames to the `camera.exit` NATS subject

### Data Requirements

The camera simulator requires car images and an empty street reference image in the `./data` directory:

- **Cars\*.png**: Multiple car images from the license plate detection dataset (e.g., `Cars1.png`, `Cars2.png`, ...)
- **Empty.png**: A reference image of an empty street scene for both entry and exit feeds

```bash
./data/
  ├── Cars1.png
  ├── Cars2.png
  ├── Cars3.png
  └── Empty.png
```

This data folder is also mounted in the camera container to `/app/data` when running the application with docker.

### Configuration

Key parameters in `camera.py`:

- `DISPLAY_TIME`: Duration (seconds) each car is shown at a camera feed (default: 5.0 seconds)
- `FRAME_DELAY`: Delay between successive frame publications (default: 1.0 second)
- `NATS_URL`: Connection URL for the NATS message queue (default: from environment variable)

### Usage

```bash
# Set up environment
export NATS_URL=nats://localhost:4222

# Run the camera simulator directly
python src/ticketless_parking_system/IoT/camera/camera.py
```

## Barrier Controller

### Overview

The barrier controller simulates physical parking barriers at entry and exit points. It provides both a visual GUI representation and responds to NATS messages to open barriers when vehicles are authorized to enter or exit.

### How It Works

#### Barrier States

- **Closed (Red)**: Default state, blocking vehicle passage
- **Open (Green)**: Allows vehicle passage, triggered by edge server

#### Communication Protocol

- Subscribes to `{BARRIER_ID}.trigger` NATS subject
- Receives barrier trigger that leads to state transition (open to closed, closed to open)
- Sends acknowledgment response back
- Uses request-reply pattern for reliable communication

#### Sensor Simulation

A real world implementation would include Sensors for object detection as:

- **detect_vehicle**: Light sensor positioned before the barrier
- **vehicle_passed**: Sensor behind the barrier to confirm passage

These sensors enable automatic barrier closing after vehicle passage and are mocked in this code.

### Configuration

Key parameters in `barrier.py`:

- `NATS_URL`: Connection URL for the NATS message queue (default: from environment variable)
- `BARRIER_ID`: Unique identifier for the barrier (e.g., "entry_0", "exit_0")
- Barrier automatically closes after vehicle passes through

### Usage

```bash
# Set up environment
export NATS_URL=nats://localhost:4222
export BARRIER_ID=entry_0

# Run the barrier controller
python src/ticketless_parking_system/IoT/barrier/barrier.py
```

## Dashboard (Real-Time Monitoring)

### Overview

A FastAPI-based web dashboard that provides real-time monitoring of the parking system. It displays live camera feeds and barrier states by subscribing and listening to nats communication between IOT-components.

### How It Works

#### WebSocket Server

- Serves on port 8000
- listens on any camera/barrier_id.* topic
- creates a card for every actively communicating camera+barrier composition
- displays camera input and a figurative picture for the barrier state

#### NATS Subscriptions

The dashboard subscribes to multiple NATS subjects:

- `barrier.*.state`: Barrier state changes (open/closed)
- `camera.entry`: Entry camera feed (base64 encoded images)
- `camera.exit`: Exit camera feed (base64 encoded images)

### Configuration

Key parameters in `dashboard.py`:

- `NATS_URL`: Connection URL for the NATS message queue (default: from environment variable)
- Port: 8000 (hardcoded in FastAPI startup)

### Usage

```bash
# Set up environment
export NATS_URL=nats://localhost:4222

# Run the dashboard
python src/ticketless_parking_system/IoT/dashboard/dashboard.py
```

### Access

- Open browser to `http://localhost:8000`

## Edge Server

### Overview

The edge server is the core processing component that handles license plate detection, parking session management, and coordination between IoT devices and the cloud backend.

### How It Works

#### License Plate Detection Pipeline

1. **Frame Reception**: Receives camera frames via NATS from entry/exit cameras
2. **Vehicle Detection**: Uses YOLOv11 model to detect license plates in frames
3. **OCR Processing**: Extracts text from detected plates using EasyOCR
4. **Validation**: Filters results based on confidence thresholds

#### Parking Session Management

**Entry Flow**:

- Detects license plate at entry camera
- Checks if vehicle already inside (via local SQLite database)
- Registers entry with cloud backend
- Opens entry barrier via NATS request-reply
- Records session in local database

**Exit Flow**:

- Detects license plate at exit camera
- Verifies payment status with cloud backend
- If paid: Opens exit barrier and marks session complete
- If unpaid: Barrier remains closed
- Cleans up session data after successful exit

#### Local Database (SQLite)

Tracks parking sessions with fields:

- License plate
- Car park ID
- Entry/exit timestamps
- Session status (active, completed)
- Created/updated timestamps

This provides resilience against temporary edge server
failuers.

#### Cloud Synchronization

**HTTP Communication**:

- Registers parking lot on startup
- Sends periodic occupancy updates
- Checks payment status
- Notifies entry/exit events

**NATS Communication**:

- Receives booking notifications from cloud
- Sends barrier control messages to IoT devices
- Publishes occupancy updates to dashboard

### Configuration

Environment variables in `server.py`:

- `EDGE_NATS_URL`: Local NATS server (for IoT devices)
- `CLOUD_NATS_URL`: Cloud NATS server (for cloud backend communication)
- `CLOUD_URL`: Cloud backend HTTP endpoint
- `DETECTION_MODEL_PATH`: Path to YOLOv11 model file
- `DB_PATH`: SQLite database path
- `CAR_PARK_ID`: Unique parking lot identifier
- `CAR_PARK_CAPACITY`: Maximum parking capacity
- `CAR_PARK_LAT` / `CAR_PARK_LNG`: Geographic coordinates

### Usage

```bash
# Set up environment
export EDGE_NATS_URL=nats://localhost:4222
export CLOUD_URL=http://localhost:8080
export CLOUD_NATS_URL=nats://localhost:4222
export DETECTION_MODEL_PATH=./yolov11s-license-plate.pt
export DB_PATH=./parking.db
export CAR_PARK_ID=lot-01
export CAR_PARK_CAPACITY=67

# Run the edge server
python src/ticketless_parking_system/edge/server.py
```

### Components

#### ParkingDatabase (`edge_db.py`)

- SQLite wrapper for session tracking
- CRUD operations for parking sessions
- Thread-safe for async operations

#### CloudParkingClient (`cloud_parking_client.py`)

- HTTP client for cloud backend API
- Handles registration, occupancy, payment operations

#### ParkingLotTracker (`parkinglot_tracker.py`)

- Maintains local occupancy state
- Sends periodic updates to cloud
- Handles booking notifications
- Manages registration/deregistration
- Uses CloudParkingClient

### ML Models

- **YOLOv11**: Real-time license plate detection
- **EasyOCR**: Optical character recognition for plate text
- Models run locally on edge server for low latency

## Cloud Backend (Akka)

### Overview

The cloud backend is built with Akka (Java) and provides a centralized actor-based system for managing multiple parking lots, handling payments, and coordinating bookings across the entire parking network.
For detailed Actor implementation see the respective
Akka Cloud Backend README at `src/ticketless_parking_system/cloud`.

### NATS Integration

The cloud backend integrates with NATS for:

- Publishing booking events to edge servers
- Receiving status updates (if configured)
- Enabling pub/sub patterns across distributed edge nodes

### Configuration

Environment variables:

- `NATS_URL`: NATS server connection string
- `HTTP_HOST`: HTTP server bind address (default: 0.0.0.0)
- `HTTP_PORT`: HTTP server port (default: 8080)
- `PARKING_ENVIRONMENT`: Environment name (development/production)
- `PARKING_ENABLE_METRICS`: Enable metrics collection

### Building & Running

See "AWS Deployment with Terraform" section for build instructions.

For local development:

```bash
cd src/ticketless_parking_system/cloud
mvn clean package
java -jar target/parking-system.jar
```

## Web Application

### Overview

A modern React-based web application that provides the customer-facing interface for the ticketless parking system. Built with Vite, Tailwind CSS, and Lucide icons.
For details see webapp README at `src/ticketless_parking_system/webapp`

### Configuration

The webapp uses environment-based configuration:

- API base URL configured via `window.APP_CONFIG.API_BASE_URL`
- Configured during Terraform deployment via `config.js` injection

### Building

```bash
cd src/ticketless_parking_system/webapp

# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build
```

### Deployment

The webapp is deployed to AWS EC2 via Terraform:

1. Vite builds static files to `dist/` directory
2. Terraform provisions EC2 instance with nginx
3. Static files uploaded and served
4. API base URL injected via `config.js`

Access after deployment: `http://<webapp_public_ip>`

## Docker Setup

### Overview

This project uses Docker and Docker Compose to orchestrate multiple services: the NATS message broker, the camera simulator, barrier controllers, dashboard, and the edge server. This containerized approach ensures consistency across environments and simplifies deployment.

### Services

#### NATS Message Broker

- **Image**: nats:2.10
- **Role**: Central message queue for inter-service communication
- **Ports**:
  - `4222`: Client connection port
  - `8222`: Monitoring UI port
- **Network**: parking-net (bridge network)

#### Camera Simulator

- **Role**: Simulates camera streams at parking entry/exit points
- **Dockerfile**: Located at `src/ticketless_parking_system/IoT/camera/dockerfile`
- **Environment**:
  - `NATS_URL=nats://nats:4222`
  - `CAMERA_ID=0`
- **Dependencies**: Requires NATS service to be running
- **Data Volume**: Mounts `./data` directory for car and empty street images
- **Network**: parking-net (bridge network)

#### Barrier Controllers

**Entry Barrier**:

- **Role**: Controls entry gate barrier
- **Dockerfile**: Located at `src/ticketless_parking_system/IoT/barrier/dockerfile`
- **Environment**:
  - `NATS_URL=nats://nats:4222`
  - `BARRIER_ID=entry_0`
- **Dependencies**: Requires NATS service
- **Network**: parking-net (bridge network)

**Exit Barrier**:

- **Role**: Controls exit gate barrier
- **Environment**:
  - `NATS_URL=nats://nats:4222`
  - `BARRIER_ID=exit_0`
- **Configuration**: Same as entry barrier but with different ID

#### Dashboard

- **Role**: Real-time monitoring web interface
- **Dockerfile**: Located at `src/ticketless_parking_system/IoT/dashboard/dockerfile`
- **Environment**:
  - `NATS_URL=nats://nats:4222`
- **Ports**: `8000:8000` (WebSocket and HTTP server)
- **Dependencies**: Requires NATS service
- **Network**: parking-net (bridge network)
- **Access**: `http://localhost:8000`

#### Edge Server

- **Role**: Processes video streams and detects license plates
- **Dockerfile**: Located at `src/ticketless_parking_system/edge/dockerfile`
- **Environment**:
  - `EDGE_NATS_URL=nats://nats:4222` (local IoT communication)
  - `CLOUD_URL=http://<akka-cloud-ip>:8080` (cloud backend)
  - `CLOUD_NATS_URL=nats://<cloud-nats-ip>:4222` (cloud messaging)
  - `DB_PATH=/app/data/parking.db` (persistent session storage)
- **Dependencies**: Requires NATS service to be running
- **Volumes**: `edge-db-data:/app/data` for SQLite database persistence
- **Network**: parking-net (bridge network)

### Network Architecture

All services are connected via the `parking-net` bridge network, enabling:

- Service discovery by container name
- Isolated network namespace
- Secure inter-service communication

### Data Persistence

**Volumes**:

- `edge-db-data`: Persistent storage for edge server SQLite database
- `./data`: Host-mounted directory for camera simulation images

This ensures parking session data survives container restarts.

### Getting Started with Docker

#### Prerequisites

- Docker and Docker Compose installed
- Image dataset placed in `./data` directory (Cars\*.png and Empty.png files)

#### Building and Running

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# View logs from specific service
docker-compose logs -f camera
docker-compose logs -f edge-server
docker-compose logs -f nats

# Stop all services
docker-compose down

# Remove volumes as well
docker-compose down -v
```

#### Verifying Services

```bash
# Check running containers
docker-compose ps

# Access NATS monitoring UI
# Open browser to http://localhost:8222

# Check container logs
docker logs camera-simulator
docker logs edge-server
```

## AWS Deployment with Terraform

### Prerequisites

1. AWS CLI configured with credentials (`aws configure`)
2. Terraform installed (`terraform --version`)
3. EC2 key pair created in AWS and private key saved locally
4. Built artifacts:
   - Akka JAR: `src/ticketless_parking_system/cloud/target/parking-system-1.0-SNAPSHOT.jar`
   - Webapp: `src/ticketless_parking_system/webapp/dist/`

### Build Steps

```bash
# Build Akka application (requires Java 17+ and Maven)
cd src/ticketless_parking_system/cloud
mvn clean package
cd ../../..

# Build webapp (requires Node.js and npm)
cd src/ticketless_parking_system/webapp
npm install
npm run build
cd ../../..
```

### Deploy

```bash
# Initialize Terraform
terraform init

# Create terraform.tfvars file
cat > terraform.tfvars <<EOF
key_name = "your-ec2-key-name"
aws_region = "us-east-1"
EOF

# Ensure SSH key is accessible
# The key should be at ~/.ssh/your-ec2-key-name.pem

# Review deployment plan
terraform plan

# Deploy infrastructure
terraform apply

# Get public IPs
terraform output
```

### Access Services

After deployment completes:

- **Akka API**: `http://<akka_app_public_ip>:8080/api/parking-lots`
- **NATS**: `nats://<nats_public_ip>:4222` (for edge servers)
- **Webapp**: `http://<webapp_public_ip>`

### Terraform Outputs and Edge Server Configuration

After a successful deployment, Terraform prints the public IP addresses of the created services:

Apply complete! Resources: 4 added, 0 changed, 0 destroyed.

Outputs:

```
akka_app_public_ip = "13.221.85.90"
nats_public_ip     = "54.226.212.72"
webapp_public_ip   = "54.152.140.32"
```

These outputs are required to configure the **edge server**, which connects to the cloud-hosted Akka backend and NATS instance.

### Configure Edge Server (`docker-compose.yml`)

In the edge server’s `docker-compose.yml`, replace the placeholder values with the Terraform outputs:

```
edge-server:
  build:
    context: ./src/ticketless_parking_system/edge
  container_name: edge-server
  restart: always
  environment:
    - EDGE_NATS_URL=nats://nats:4222
    - CLOUD_URL=http://<akka-cloud-ip>:8080
    - CLOUD_NATS_URL=nats://<cloud-nats-ip>:4222
    - DB_PATH=/app/data/parking.db
```

Replace the placeholders as follows:

- `<akka-cloud-ip>` → value of `akka_app_public_ip`
- `<cloud-nats-ip>` → value of `nats_public_ip`

Example:

- CLOUD_URL=http://13.221.85.90:8080
- CLOUD_NATS_URL=nats://54.226.212.72:4222

### Notes

- The **webapp** is automatically configured during deployment to point to the Akka backend.
- The **edge server** must be configured manually because it runs outside the Terraform-managed infrastructure.
- If Terraform is re-applied and IPs change, the edge server configuration must be updated accordingly.

### Cleanup

```bash
terraform destroy
```
