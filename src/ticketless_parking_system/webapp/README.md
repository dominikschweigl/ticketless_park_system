# Frontend

A distributed parking system frontend built with React, Tailwind CSS and Vite. This web application allows users to pay for parking using their license plate number, view real-time parking capacity, and book spots in advance.

### Features

#### Payment View

- **License Plate Payment**: Pay for parking by entering license plate number
- **Real-time Price Calculation**: Shows parking duration and calculated fee
- **Payment Status**: Visual feedback on payment success/failure
- **Exit Notification**: Confirms barrier will open after payment

#### Find & Book View

- **Geolocation**: Automatically detects user location
- **Nearby Parking**: Shows parking lots sorted by distance
- **Live Occupancy**: Real-time availability for each parking lot
- **Advance Booking**: Reserve parking spots before arrival
- **Map Integration**: Opens Google Maps directions to selected parking lot
- **Search**: Filter parking lots by name or ID

#### User Interface

- **Responsive Design**: Works on desktop and mobile devices
- **Notifications**: Toast-style alerts for actions and errors
- **Real-time Data**: Updates parking availability dynamically
- **Visual Indicators**: Color-coded occupancy levels (green/yellow/red)

### Tech Stack

Framework: React (Vite)

Styling: Tailwind CSS

Icons: Lucide React

State Management: React Hooks (useState, useEffect)

### Configuration

The webapp uses environment-based configuration:

**Development** (`vite.config.js`):

- Proxies `/api` and `/health` requests to `http://localhost:8080`
- Hot module replacement for rapid development

**Production**:

- API base URL configured via `window.APP_CONFIG.API_BASE_URL`
- Configured during Terraform deployment via `config.js` injection

### Installation & Setup

Since this project relies on specific Node.js bindings, it is recommended to run this inside a Linux environment (native Linux or WSL2).

Install Dependencies:

```
npm install
```

Start Development Server:

```
npm run dev
```

### Building

```bash
cd src/ticketless_parking_system/webapp

# Install dependencies
npm install

# Production build
npm run build
```

### API Integration

The webapp communicates with the cloud backend via REST API:

**Payment Operations** (`parkingApi.js`):

- `paymentCheck(licensePlate)` - Check payment status
- `paymentPay(licensePlate)` - Process payment
- `paymentExit(licensePlate)` - Cleanup after exit

**Parking Lot Queries**:

- `getRegisteredParkingLots()` - Get all lots
- `getNearbyParkingLots({lat, lng, limit, onlyAvailable})` - Find nearby
- `getParkingLotStatus(parkId)` - Get specific lot status

**Booking Operations**:

- `createBooking(parkId, licensePlate)` - Create reservation

### Deployment

The webapp is deployed to AWS EC2 via Terraform:

1. Vite builds static files to `dist/` directory
2. Terraform provisions EC2 instance with nginx
3. Static files uploaded and served
4. API base URL injected via `config.js`

Access after deployment: `http://<webapp_public_ip>`
