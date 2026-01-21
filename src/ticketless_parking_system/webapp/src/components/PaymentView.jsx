import React, { useState } from 'react';
import { Car, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from './ui/Button';
import { Card } from './ui/Card';
import { paymentCheck, paymentPay, paymentExit } from "../services/parkingApi";

export const PaymentView = ({ showNotification }) => {
  const [plate, setPlate] = useState('');
  const [loading, setLoading] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState(null); // null, 'checking', 'results', 'paid'
  const [billData, setBillData] = useState(null);

    const formatDuration = (ms) => {
    const totalMin = Math.max(0, Math.round(ms / 60000));
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    if (h <= 0) return `${m} min`;
    return `${h}h ${m}m`;
  };

  const toBillData = (ps) => {
    const unknown = !ps.entryTimestamp || ps.entryTimestamp === 0;

    if (unknown) {
      return {
        status: "NONE",
        amount: 0,
        entryTime: "",
        duration: "",
        raw: ps,
      };
    }

    const amount = (ps.priceCents || 0) / 100.0;
    const durationMs = (ps.currentTimestamp || Date.now()) - ps.entryTimestamp;

    return {
      status: ps.paid ? "PAID" : "UNPAID",
      amount,
      entryTime: new Date(ps.entryTimestamp).toLocaleString(),
      duration: formatDuration(durationMs),
      raw: ps,
    };
  };


  const checkPlate = async (e) => {
  e.preventDefault();
  if (!plate) return;

  setLoading(true);
  setPaymentStatus("checking");
  setBillData(null);

  try {
    const ps = await paymentCheck(plate);
    const data = toBillData(ps);

    setBillData(data);
    setPaymentStatus("results");
  } catch (err) {
    console.error(err);
    if (showNotification) showNotification("error", err.message || "Check failed");
    setPaymentStatus(null);
  } finally {
    setLoading(false);
  }
};


  const handlePay = async () => {
  setLoading(true);
  try {
    const ps = await paymentPay(plate);
    setBillData(toBillData(ps));
    setPaymentStatus("paid");
    if (showNotification) showNotification("success", "Payment successful! Gate will open automatically.");
  } catch (err) {
    console.error(err);
    if (showNotification) showNotification("error", err.message || "Payment failed");
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2 mb-8">
        <h2 className="text-3xl font-bold text-slate-800">Pay for Parking</h2>
        <p className="text-slate-500">Enter your license plate to check for outstanding fees.</p>
      </div>

      <Card className="border-t-4 border-t-blue-600">
        {!paymentStatus || paymentStatus === 'checking' ? (
          <form onSubmit={checkPlate} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">License Plate Number</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Car className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="text"
                  value={plate}
                  onChange={(e) => setPlate(e.target.value)}
                  className="block w-full pl-10 pr-3 py-4 text-lg border border-slate-300 rounded-md focus:ring-blue-500 focus:border-blue-500 tracking-widest font-mono bg-slate-50 placeholder-slate-400"
                  placeholder="ABC-1234"
                />
              </div>
            </div>
            <Button type="submit" loading={loading} className="w-full py-3 text-lg">
              Check Fees
            </Button>
          </form>
        ) : paymentStatus === 'paid' ? (
          <div className="text-center py-8">
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <h3 className="text-2xl font-bold text-slate-800 mb-2">Payment Complete</h3>
            <p className="text-slate-600 mb-6">You may now exit the parking facility.</p>
            <div className="bg-slate-50 p-4 rounded-md border border-slate-200 inline-block text-left mb-6">
              <p className="text-sm text-slate-500">Transaction ID: <span className="font-mono text-slate-800">TXN-83921</span></p>
              <p className="text-sm text-slate-500">Plate: <span className="font-mono text-slate-800">{plate}</span></p>
            </div>
            <Button onClick={() => { setPaymentStatus(null); setPlate(''); }} variant="secondary" className="w-full">
              Pay for another vehicle
            </Button>
          </div>
        ) : (
          <div className="space-y-6 animate-fadeIn">
            {String(billData?.status || "").toUpperCase() === "UNPAID" ? (
              <>
                <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                   <div>
                     <h3 className="text-lg font-bold text-slate-800">Outstanding Balance</h3>
                     <p className="text-sm text-slate-500">{billData.entryTime} - Now ({billData.duration})</p>
                   </div>
                   <span className="text-3xl font-bold text-blue-600">${billData.amount.toFixed(2)}</span>
                </div>
                
                <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <AlertCircle className="h-5 w-5 text-yellow-400" aria-hidden="true" />
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-yellow-700">
                        Gate will not open until payment is confirmed.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-3 pt-2">
                  <Button onClick={handlePay} loading={loading} className="w-full py-3 text-lg" variant="success">
                     Pay Now with Credit Card
                  </Button>
                  <Button onClick={() => setPaymentStatus(null)} variant="ghost" className="w-full">
                     Cancel
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-center py-6">
                <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-3" />
                <h3 className="text-xl font-medium text-slate-800">No Fees Due</h3>
                <p className="text-slate-500 mt-2">This vehicle is either not in the lot or has already paid.</p>
                <Button onClick={() => setPaymentStatus(null)} variant="secondary" className="mt-6 w-full">
                  Check Another
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
};