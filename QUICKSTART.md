# 🚀 Schnellstart-Anleitung: Python ↔ Akka Kommunikation

## Zusammenfassung der Lösung

Ihr Python Edge Server kommuniziert jetzt mit dem Akka Cloud System über **HTTP REST API**:

```
Python Edge Server  ──HTTP──>  Akka Cloud System
     (server.py)               (Java + Akka HTTP)
         │                            │
         ├─ CloudParkingClient        ├─ HttpServer
         ├─ ParkingLotTracker         ├─ ParkingLotManagerActor
         └─ YOLO + OCR                └─ ParkingLotActor(s)
```

## API Endpunkte

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| GET | `/health` | Health Check |
| POST | `/api/parking-lots` | Parking Lot registrieren |
| POST | `/api/occupancy` | Occupancy Update senden |
| GET | `/api/parking-lots/{id}` | Status abfragen |

## 🏃 Schnellstart

### 1. Akka System starten

```powershell
cd src\ticketless_parking_system\cloud
java -jar target\parking-system.jar
```

**Erwartete Ausgabe:**
```
14:52:45.123 [main] INFO  c.t.p.app.ParkingSystemApp - Starting Ticketless Parking System
14:52:45.456 [main] INFO  c.t.p.http.HttpServer - HTTP Server started at http://0.0.0.0:8080/
Edge servers registering parking lots...
Parking System is running. Press Ctrl+C to exit.
```

### 2. Test mit curl (in neuem Terminal)

```powershell
# Health Check
curl http://localhost:8080/health

# Parking Lot registrieren
curl -Method POST -Uri "http://localhost:8080/api/parking-lots" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"parkId":"lot-test","maxCapacity":100,"edgeServerId":"test-edge"}'

# Occupancy Update
curl -Method POST -Uri "http://localhost:8080/api/occupancy" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"parkId":"lot-test","currentOccupancy":25,"edgeServerId":"test-edge"}'

# Status abfragen
curl http://localhost:8080/api/parking-lots/lot-test
```

### 3. Python Test-Suite ausführen

```powershell
cd src\ticketless_parking_system\edge
pip install httpx  # Falls noch nicht installiert
python test_cloud_client.py
```

### 4. Edge Server starten

```powershell
$env:CLOUD_URL="http://localhost:8080"
$env:CAR_PARK_ID="lot-01"
$env:CAR_PARK_CAPACITY="50"
$env:EDGE_SERVER_ID="edge-01"
# ... weitere ENV Variablen ...

python server.py
```

## 📁 Wichtige Dateien

### Java (Akka Cloud System)

- **`cloud/src/main/java/com/ticketless/parking/http/HttpServer.java`**
  - HTTP Server mit Akka HTTP
  - Routen-Definitionen
  - JSON Marshalling mit Gson

- **`cloud/src/main/java/com/ticketless/parking/actors/ParkingLotManagerActor.java`**
  - Verwaltet alle Parking Lot Actors
  - Routet Messages zu korrekten Actors

- **`cloud/src/main/java/com/ticketless/parking/messages/*.java`**
  - Message-Klassen für Actor-Kommunikation
  - Serialisierbar für Akka

### Python (Edge Server)

- **`edge/cloud_client.py`**
  - `CloudParkingClient` - HTTP Client
  - `ParkingLotTracker` - High-level Interface
  - Async/await basiert

- **`edge/server.py`**
  - Hauptanwendung
  - Integriert Cloud Client
  - Sendet Occupancy Updates

- **`edge/test_cloud_client.py`**
  - Automatische Tests
  - Validiert Kommunikation

## 🔍 Wie es funktioniert

### 1. System-Start

```java
// ParkingSystemApp.java
httpServer = new HttpServer(actorSystem, parkingLotManager);
httpServer.start("0.0.0.0", 8080);
```

Der HTTP Server startet und wartet auf Requests.

### 2. Parking Lot Registrierung

**Python Edge Server:**
```python
client = CloudParkingClient("http://localhost:8080")
await client.register_parking_lot("lot-01", 50, "edge-01")
```

**HTTP Request:**
```http
POST /api/parking-lots
Content-Type: application/json

{"parkId": "lot-01", "maxCapacity": 50, "edgeServerId": "edge-01"}
```

**Java (HttpServer):**
```java
private Route registerParkingLot(String jsonBody) {
    RegisterParkRequest request = gson.fromJson(jsonBody, ...);
    RegisterParkMessage message = new RegisterParkMessage(...);
    CompletionStage<Object> response = Patterns.ask(parkingLotManager, message, ASK_TIMEOUT);
    // ... return response
}
```

**Java (ParkingLotManagerActor):**
```java
private void handleRegisterPark(RegisterParkMessage message) {
    ActorRef parkActor = getContext().actorOf(
        ParkingLotActor.props(parkId, maxCapacity),
        "park-" + parkId
    );
    parkActors.put(parkId, parkActor);
    sender().tell(new ParkRegisteredMessage(...), self());
}
```

### 3. Occupancy Update

**Python Edge Server:**
```python
# Auto fährt ein
await tracker.increment_occupancy()
```

**HTTP Request:**
```http
POST /api/occupancy
{"parkId": "lot-01", "currentOccupancy": 15, "edgeServerId": "edge-01"}
```

**Java (HttpServer):**
```java
private Route updateOccupancy(String jsonBody) {
    OccupancyUpdateRequest request = gson.fromJson(jsonBody, ...);
    ParkingLotOccupancyMessage message = new ParkingLotOccupancyMessage(...);
    parkingLotManager.tell(message, ActorRef.noSender()); // Fire-and-forget
    return complete(StatusCodes.ACCEPTED, ...);
}
```

**Java (ParkingLotManagerActor):**
```java
private void handleOccupancyUpdate(ParkingLotOccupancyMessage message) {
    ActorRef parkActor = parkActors.get(message.getParkId());
    parkActor.tell(message, sender());
}
```

**Java (ParkingLotActor):**
```java
private void handleOccupancy(ParkingLotOccupancyMessage message) {
    this.currentOccupancy = message.getCurrentOccupancy();
    log.info("Updated occupancy to {}/{}", currentOccupancy, maxCapacity);
}
```

## 📊 Datenfluss-Diagramm

```
┌───────────────────────────────────────────────────────────────┐
│                     Python Edge Server                         │
│                                                                │
│  Camera → YOLO → OCR → checkpoint_handler()                   │
│                           │                                    │
│                           ├─> db.register_entry()              │
│                           └─> tracker.increment_occupancy()    │
│                                     │                          │
│                          cloud_client.send_occupancy_update()  │
│                                     │                          │
└─────────────────────────────────────┼──────────────────────────┘
                                      │
                      HTTP POST /api/occupancy
                                      │
┌─────────────────────────────────────▼──────────────────────────┐
│                     Akka Cloud System                          │
│                                                                │
│  HttpServer                                                    │
│     │                                                          │
│     ├─> Parse JSON (Gson)                                     │
│     └─> Create ParkingLotOccupancyMessage                     │
│              │                                                 │
│              ▼                                                 │
│  ParkingLotManagerActor                                        │
│     │                                                          │
│     ├─> Lookup parkActors.get(parkId)                         │
│     └─> Forward to ParkingLotActor                            │
│              │                                                 │
│              ▼                                                 │
│  ParkingLotActor                                               │
│     └─> Update internal state (currentOccupancy = 15)         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## ✅ Vorteile dieser Lösung

1. **Standard HTTP/JSON** - Keine proprietären Protokolle
2. **Lose Kopplung** - Python kennt nur HTTP API
3. **Einfach zu testen** - curl, Postman, Python tests
4. **Akka Ask Pattern** - Request/Response für Registrierung
5. **Fire-and-Forget** - Schnelle Occupancy Updates
6. **Production-Ready** - Fehlerbehandlung, Logging, Config

## 🎯 Nächste Schritte

1. ✅ Implementierung fertig - **Kommunikation funktioniert!**
2. ⏭️ Payment-Check implementieren (REST API für WebApp)
3. ⏭️ Persistent Storage (DynamoDB statt In-Memory)
4. ⏭️ Load Balancing (mehrere Edge Server)
5. ⏭️ Monitoring & Metrics (Prometheus/Grafana)

## 📚 Weitere Dokumentation

- **PYTHON_AKKA_COMMUNICATION.md** - Vollständige Anleitung
- **edge/COMMUNICATION_GUIDE.md** - API Referenz
- **edge/test_cloud_client.py** - Code-Beispiele

---

**🎉 Ihre Python ↔ Akka Kommunikation ist jetzt vollständig implementiert und einsatzbereit!**

