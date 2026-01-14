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
