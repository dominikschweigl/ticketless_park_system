import React, { useEffect, useMemo, useState } from "react";
import { Search, MapPin, Navigation } from "lucide-react";
import {
  getNearbyParkingLots,
  getRegisteredParkingLots,
  getParkingLotStatus,
  createBooking,
} from "../services/parkingApi";
import { Button } from './ui/Button';
import { Card } from './ui/Card';

const cn = (...xs) => xs.filter(Boolean).join(" ");

const Input = ({ className, ...props }) => (
  <input
    className={cn(
      "w-full px-3 py-2 rounded-lg bg-white text-slate-800 placeholder:text-slate-400",
      "focus:outline-none focus:ring-2 focus:ring-blue-500 border border-slate-200 shadow-sm",
      className
    )}
    {...props}
  />
);

const Modal = ({ open, title, onClose, children, footer }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-800">{title}</h3>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="p-6">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-slate-100 bg-slate-50">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

function formatDistance(distanceMeters) {
  if (typeof distanceMeters !== "number" || Number.isNaN(distanceMeters)) return "";
  if (distanceMeters < 1000) return `${Math.round(distanceMeters)} m`;
  return `${(distanceMeters / 1000).toFixed(1)} km`;
}

export const FindAndBookView = ({ showNotification }) => {
  const [lotsRaw, setLotsRaw] = useState([]);
  const [loading, setLoading] = useState(true);

  const [searchTerm, setSearchTerm] = useState("");

  const [selectedLot, setSelectedLot] = useState(null);
  const [bookingPlate, setBookingPlate] = useState("");
  const [bookingLoading, setBookingLoading] = useState(false);

  const [userLoc, setUserLoc] = useState(null); // { lat, lng } | null
  const [geoFailed, setGeoFailed] = useState(false);

  useEffect(() => {
    if (!navigator.geolocation) {
      setGeoFailed(true);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      (err) => {
        console.warn("Geolocation denied/unavailable:", err);
        setGeoFailed(true);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, []);

  useEffect(() => {
    let alive = true;

    (async () => {
      try {
        setLoading(true);

        if (userLoc?.lat != null && userLoc?.lng != null) {
          const data = await getNearbyParkingLots({
            lat: userLoc.lat,
            lng: userLoc.lng,
            limit: 10,
            onlyAvailable: true,
          });

          const results = data?.results ?? [];

          const uiLots = results.map((r) => ({
            id: r.parkId,
            name: r.parkId,
            address: "",
            total: r.maxCapacity ?? 0,
            free: r.availableSpaces ?? 0,
            price: 4.5,
            dist: formatDistance(r.distanceMeters),
            distMeters: typeof r.distanceMeters === "number" ? r.distanceMeters : null,
            lat: typeof r.lat === "number" ? r.lat : 0,
            lng: typeof r.lng === "number" ? r.lng : 0,
          }));

          if (alive) setLotsRaw(uiLots);
          return;
        }

        if (!geoFailed) return;

        const reg = await getRegisteredParkingLots();
        const parks = reg.parks || {};
        const ids = Object.keys(parks);

        const statuses = await Promise.all(ids.map((id) => getParkingLotStatus(id)));

        const uiLots = statuses.map((s) => ({
          id: s.parkId,
          name: s.parkId,
          address: "",
          total: s.maxCapacity ?? 0,
          free: s.availableSpaces ?? 0,
          price: 4.5,
          dist: "",
          distMeters: null,
          lat: typeof s.lat === "number" ? s.lat : 0,
          lng: typeof s.lng === "number" ? s.lng : 0,
        }));

        if (alive) setLotsRaw(uiLots);
      } catch (e) {
        console.error(e);
        if (showNotification) {
          showNotification("error", e.message || "Failed to load parking lots");
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, [userLoc, geoFailed, showNotification]);

  const lots = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();

    const filtered = q
      ? lotsRaw.filter((l) => {
          const hay = `${l.name} ${l.address ?? ""}`.toLowerCase();
          return hay.includes(q);
        })
      : lotsRaw;

    // If we have distances, sort by nearest
    const hasDistances = filtered.some((l) => typeof l.distMeters === "number");
    if (!hasDistances) return filtered;

    return [...filtered].sort((a, b) => {
      const da =
        typeof a.distMeters === "number" ? a.distMeters : Number.POSITIVE_INFINITY;
      const db =
        typeof b.distMeters === "number" ? b.distMeters : Number.POSITIVE_INFINITY;
      return da - db;
    });
  }, [lotsRaw, searchTerm]);

  const openRoute = (lot) => {
    const hasCoords =
      lot &&
      typeof lot.lat === "number" &&
      typeof lot.lng === "number" &&
      !(lot.lat === 0 && lot.lng === 0);

    if (!hasCoords) {
      if (showNotification)
        showNotification("error", "No coordinates for this parking lot yet.");
      return;
    }

    const url = `https://www.google.com/maps/dir/?api=1&destination=${lot.lat},${lot.lng}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const handleBook = async (e) => {
    e.preventDefault();

    if (!bookingPlate || !selectedLot?.id) {
      if (showNotification) showNotification("error", "Please enter a license plate.");
      return;
    }

    setBookingLoading(true);
    try {
      const res = await createBooking(selectedLot.id, bookingPlate);

      if (showNotification) {
        showNotification(
          "success",
          `Booked ${res.parkId} for ${res.licensePlate} (${res.status})`
        );
      }

      setSelectedLot(null);
      setBookingPlate("");
    } catch (err) {
      console.error(err);
      if (showNotification)
        showNotification("error", err.message || "Booking failed");
    } finally {
      setBookingLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 py-10">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h2 className="text-3xl font-bold text-slate-800">Find Parking</h2>
            <p className="text-slate-500">
              Distances are computed by the backend (nearby endpoint).
            </p>
          </div>

          <div className="relative w-full md:w-96">
            <Input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search parking lot…"
              className="pl-10"
            />
            <Search className="absolute left-3 top-2.5 h-5 w-5 text-slate-400" />
          </div>
        </div>

        {loading ? (
          <Card className="text-center">
            <div className="text-slate-700 font-semibold">Loading parking lots…</div>
            <div className="text-slate-500 text-sm mt-1">
              {userLoc ? "Fetching nearby lots…" : geoFailed ? "Loading lots…" : "Getting your location…"}
            </div>
          </Card>
        ) : lots.length === 0 ? (
          <Card className="text-center">
            <div className="text-slate-700 font-semibold">No lots found.</div>
            <div className="text-slate-500 text-sm mt-1">
              Try a different search, or ensure the backend has registered lots.
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* List */}
            <div className="lg:col-span-2 space-y-4">
              {lots.map((lot) => {
                const occupancy =
                  lot.total > 0
                    ? Math.round(((lot.total - lot.free) / lot.total) * 100)
                    : 0;

                const isFull = lot.free === 0;

                return (
                  <div
                    key={lot.id}
                    className="bg-white p-5 rounded-lg shadow-sm border border-slate-200 hover:shadow-md transition-shadow"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="text-lg font-bold text-slate-800">
                            {lot.name}
                          </h3>
                          {lot.free > 0 && lot.free < 10 && (
                            <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full font-medium">
                              High Demand
                            </span>
                          )}
                        </div>

                        <p className="text-slate-500 text-sm flex items-center gap-1 mt-1">
                          <MapPin className="h-3 w-3" />
                          {lot.dist ? `${lot.dist} away` : "distance unknown"}
                        </p>
                      </div>

                      <div className="text-right">
                        <span className="block text-xl font-bold text-slate-800">
                          ${lot.price.toFixed(2)}
                          <span className="text-sm font-normal text-slate-500">
                            /hr
                          </span>
                        </span>
                        <span className="text-slate-500 text-sm">
                          {lot.free}/{lot.total} free
                        </span>
                      </div>
                    </div>

                    <div className="mt-4">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-500">Occupancy</span>
                        <span
                          className={cn(
                            "font-semibold",
                            occupancy > 90
                              ? "text-red-600"
                              : occupancy > 70
                              ? "text-orange-600"
                              : "text-green-600"
                          )}
                        >
                          {occupancy}%
                        </span>
                      </div>
                      <div className="mt-2 h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            occupancy > 90
                              ? "bg-red-500"
                              : occupancy > 70
                              ? "bg-orange-500"
                              : "bg-green-500"
                          )}
                          style={{
                            width: `${Math.min(100, Math.max(0, occupancy))}%`,
                          }}
                        />
                      </div>
                    </div>

                    <div className="mt-5 flex gap-3">
                      <Button
                        className="flex-1"
                        disabled={isFull}
                        onClick={() => setSelectedLot(lot)}
                      >
                        {isFull ? "Full" : "Book Spot"}
                      </Button>

                      <Button
                        variant="secondary"
                        className="flex-1"
                        onClick={() => openRoute(lot)}
                      >
                        <Navigation className="h-4 w-4" /> Route
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Side */}
            <div className="space-y-4">
              <Card>
                <div className="text-slate-800 font-bold text-lg">Location</div>
                <div className="text-slate-600 text-sm mt-2 space-y-1">
                  <div>
                    <span className="font-semibold">Status:</span>{" "}
                    {userLoc ? (
                      <span className="text-green-600">available</span>
                    ) : geoFailed ? (
                      <span className="text-red-600">unavailable/denied</span>
                    ) : (
                      <span className="text-slate-500">requesting…</span>
                    )}
                  </div>
                  {userLoc && (
                    <div>
                      <span className="font-semibold">Coords:</span>{" "}
                      <span className="font-mono">
                        {userLoc.lat.toFixed(5)}, {userLoc.lng.toFixed(5)}
                      </span>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        )}

        <Modal
          open={!!selectedLot}
          title={selectedLot ? `Book: ${selectedLot.name}` : "Book"}
          onClose={() => {
            setSelectedLot(null);
            setBookingPlate("");
          }}
          footer={
            <div className="flex gap-3 justify-end">
              <Button
                variant="secondary"
                onClick={() => {
                  setSelectedLot(null);
                  setBookingPlate("");
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleBook} loading={bookingLoading}>
                Confirm Booking
              </Button>
            </div>
          }
        >
          <form onSubmit={handleBook} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">
                License Plate
              </label>
              <Input
                value={bookingPlate}
                onChange={(e) => setBookingPlate(e.target.value)}
                placeholder="e.g. IN-AB1234"
              />
            </div>

            <div className="text-sm text-slate-600">
              Available:{" "}
              <span className="font-semibold text-slate-800">
                {selectedLot?.free}/{selectedLot?.total}
              </span>
              {selectedLot?.dist ? (
                <>
                  {" "}
                  • Distance:{" "}
                  <span className="font-semibold text-slate-800">
                    {selectedLot.dist}
                  </span>
                </>
              ) : null}
            </div>
          </form>
        </Modal>
      </div>
    </div>
  );
};
