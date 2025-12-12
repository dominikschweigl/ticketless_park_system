import React, { useState, useEffect } from 'react';
import { Search, MapPin, Navigation } from 'lucide-react';

// --- DEPENDENCIES (Included inline for preview compatibility) ---
// In your local project, you should import these from their respective files:
// import { Button } from './ui/Button';
// import { Card } from './ui/Card';
// import { mockApi } from '../services/mockApi';

const mockApi = {
  getParkingLots: async () => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([
          { id: 1, name: "Central Station Plaza", address: "12 Station Rd", total: 150, free: 12, price: 4.5, dist: "0.4 km" },
          { id: 2, name: "Downtown Market", address: "88 Main St", total: 80, free: 0, price: 5.0, dist: "1.2 km" },
          { id: 3, name: "Westside Garage", address: "420 West Ave", total: 200, free: 145, price: 3.0, dist: "2.5 km" },
          { id: 4, name: "Harbor View", address: "1 Dockside Ln", total: 60, free: 5, price: 6.5, dist: "3.1 km" },
        ]);
      }, 800);
    });
  },
  bookSpot: async (lotId, plate, time) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, bookingRef: "BK-" + Math.floor(Math.random() * 9999) });
      }, 1000);
    });
  }
};

const Button = ({ children, onClick, disabled, loading, variant = "primary", className = "" }) => {
  const baseStyles = "px-4 py-2 rounded-md font-medium transition-all duration-200 flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-offset-1";
  const variants = {
    primary: "bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500 shadow-sm",
    secondary: "bg-slate-100 hover:bg-slate-200 text-slate-700 focus:ring-slate-400 border border-slate-200",
    success: "bg-emerald-600 hover:bg-emerald-700 text-white focus:ring-emerald-500 shadow-sm",
    danger: "bg-red-500 hover:bg-red-600 text-white focus:ring-red-500",
    ghost: "bg-transparent hover:bg-slate-100 text-slate-600"
  };

  return (
    <button 
      onClick={onClick} 
      disabled={disabled || loading} 
      className={`${baseStyles} ${variants[variant]} ${disabled || loading ? 'opacity-60 cursor-not-allowed' : ''} ${className}`}
    >
      {loading && <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>}
      {children}
    </button>
  );
};

const Card = ({ title, children, className = "", footer }) => (
  <div className={`bg-white rounded-lg shadow-md border border-slate-200 overflow-hidden ${className}`}>
    {title && (
      <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
        <h3 className="text-xl font-semibold text-slate-800">{title}</h3>
      </div>
    )}
    <div className="p-6">
      {children}
    </div>
    {footer && (
      <div className="bg-slate-50 px-6 py-4 border-t border-slate-100">
        {footer}
      </div>
    )}
  </div>
);
// ----------------------------------------------------------------

export const FindAndBookView = ({ showNotification }) => {
  const [lots, setLots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedLot, setSelectedLot] = useState(null);
  const [bookingPlate, setBookingPlate] = useState('');
  const [bookingLoading, setBookingLoading] = useState(false);

  useEffect(() => {
    mockApi.getParkingLots().then(data => {
      setLots(data);
      setLoading(false);
    });
  }, []);

  const handleBook = async (e) => {
    e.preventDefault();
    if (!bookingPlate) return;
    setBookingLoading(true);
    await mockApi.bookSpot(selectedLot.id, bookingPlate, 'NOW');
    setBookingLoading(false);
    setSelectedLot(null);
    if (showNotification) showNotification('success', `Spot reserved at ${selectedLot.name} for ${bookingPlate}!`);
    setBookingPlate('');
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-800">Find Parking</h2>
          <p className="text-slate-500">Real-time capacity and reservations.</p>
        </div>
        <div className="relative w-full md:w-96">
          <input 
            type="text" 
            placeholder="Search destination..." 
            className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm"
          />
          <Search className="absolute left-3 top-2.5 h-5 w-5 text-slate-400" />
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1,2,3].map(i => (
            <div key={i} className="h-64 bg-slate-100 rounded-lg animate-pulse"></div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* List of Lots */}
          <div className="lg:col-span-2 space-y-4">
            {lots.map(lot => {
              const occupancy = Math.round(((lot.total - lot.free) / lot.total) * 100);
              const isFull = lot.free === 0;
              
              return (
                <div key={lot.id} className="bg-white p-5 rounded-lg shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-bold text-slate-800">{lot.name}</h3>
                        {lot.free > 0 && lot.free < 10 && (
                          <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full font-medium">High Demand</span>
                        )}
                      </div>
                      <p className="text-slate-500 text-sm flex items-center gap-1 mt-1">
                        <MapPin className="h-3 w-3" /> {lot.address} • {lot.dist} away
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="block text-xl font-bold text-slate-800">${lot.price.toFixed(2)}<span className="text-sm font-normal text-slate-500">/hr</span></span>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="flex justify-between text-sm mb-1">
                      <span className={`font-medium ${isFull ? 'text-red-600' : 'text-slate-600'}`}>
                        {isFull ? 'Full' : `${lot.free} spots available`}
                      </span>
                      <span className="text-slate-400">{occupancy}% Full</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                      <div 
                        className={`h-2.5 rounded-full ${isFull ? 'bg-red-500' : occupancy > 80 ? 'bg-orange-400' : 'bg-green-500'}`} 
                        style={{ width: `${occupancy}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="mt-5 flex gap-3">
                    <Button 
                      variant="primary" 
                      className="flex-1" 
                      disabled={isFull}
                      onClick={() => setSelectedLot(lot)}
                    >
                      {isFull ? 'Waitlist' : 'Book Spot'}
                    </Button>
                    <Button variant="secondary" className="flex-1">
                      <Navigation className="h-4 w-4" /> Route
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Selected Booking Panel (Sticky on Desktop) */}
          <div className="lg:col-span-1">
            <div className="sticky top-6">
              {selectedLot ? (
                <Card title="Complete Booking" className="border-t-4 border-t-blue-600 animate-slideUp">
                  <div className="space-y-4">
                    <div>
                      <p className="text-sm text-slate-500">Location</p>
                      <p className="font-medium text-slate-800">{selectedLot.name}</p>
                    </div>
                    <div>
                      <p className="text-sm text-slate-500">Rate</p>
                      <p className="font-medium text-slate-800">${selectedLot.price.toFixed(2)} / hour</p>
                    </div>
                    
                    <form onSubmit={handleBook} className="space-y-4 pt-2">
                       <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Plate Number</label>
                        <input 
                          required
                          type="text" 
                          className="w-full border border-slate-300 rounded-md p-2 uppercase font-mono"
                          placeholder="ABC-1234"
                          value={bookingPlate}
                          onChange={e => setBookingPlate(e.target.value.toUpperCase())}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Duration (Est.)</label>
                        <select className="w-full border border-slate-300 rounded-md p-2 bg-white">
                          <option>1 Hour</option>
                          <option>2 Hours</option>
                          <option>4 Hours</option>
                          <option>All Day</option>
                        </select>
                      </div>
                      
                      <div className="flex gap-2 pt-2">
                        <Button type="submit" loading={bookingLoading} className="flex-1" variant="success">Confirm</Button>
                        <Button onClick={() => setSelectedLot(null)} type="button" variant="secondary">Cancel</Button>
                      </div>
                    </form>
                  </div>
                </Card>
              ) : (
                <div className="bg-slate-50 rounded-lg border border-dashed border-slate-300 p-8 text-center">
                  <MapPin className="h-10 w-10 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500">Select a parking lot from the list to reserve a spot.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};