# ticketless_park_system

## Overview

A distributed parking system that uses license plate detection to enable ticketless parking. Vehicles are detected at entry and exit points, and customers can pay using their license plate number through a web application or payment station.

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

## Docker Setup

### Overview

This project uses Docker and Docker Compose to orchestrate multiple services: the NATS message broker, the camera simulator, and the edge server. This containerized approach ensures consistency across environments and simplifies deployment.

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
- **Dependencies**: Requires NATS service to be running
- **Data Volume**: Mounts `./data` directory for car and empty street images
- **Network**: parking-net (bridge network)

#### Edge Server
- **Role**: Processes video streams and detects license plates
- **Dockerfile**: Located at `src/ticketless_parking_system/edge/dockerfile`
- **Environment**:
  - `NATS_URL=nats://nats:4222`
- **Dependencies**: Requires NATS service to be running
- **Network**: parking-net (bridge network)

Can also be run locally with the following command and assuming that the nast and camera containers are running. 

```
NATS_URL=nats://localhost:4222 DETECTION_MODEL_PATH="./src/ticketless_parking_system/edge/yolov11s-license-plate.pt" uv run src/ticketless_parking_system/edge/server.py
```

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