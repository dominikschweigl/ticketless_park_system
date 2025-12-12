import React, { useState } from 'react';
import { AlertCircle, CheckCircle } from 'lucide-react';

import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { PaymentView } from './components/PaymentView';
import { FindAndBookView } from './components/FindAndBookView';

export default function SmartParkApp() {
const [activeTab, setActiveTab] = useState('pay');
const [notification, setNotification] = useState(null);

// Helper to show temporary toasts
const showNotification = (type, message) => {
setNotification({ type, message });
setTimeout(() => setNotification(null), 4000);
};

return (
<div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex flex-col">

  {/* Navigation Bar */}
  <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

  {/* --- MAIN CONTENT --- */}
  <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full flex-grow">
    
    {/* Notification Toast */}
    {notification && (
      <div className={`fixed top-20 right-4 z-50 p-4 rounded-md shadow-lg flex items-center gap-3 animate-slideIn ${notification.type === 'error' ? 'bg-red-50 text-red-800 border border-red-200' : 'bg-emerald-50 text-emerald-800 border border-emerald-200'}`}>
        {notification.type === 'error' ? <AlertCircle className="h-5 w-5" /> : <CheckCircle className="h-5 w-5" />}
        <span className="font-medium">{notification.message}</span>
      </div>
    )}

    {/* View Switcher Logic */}
    {activeTab === 'pay' ? (
      <PaymentView showNotification={showNotification} />
    ) : (
      <FindAndBookView showNotification={showNotification} />
    )}

  </main>

  {/* Footer */}
  <Footer />

  {/* Global Styles for Animations */}
  <style>{`
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .animate-fadeIn {
      animation: fadeIn 0.4s ease-out forwards;
    }
    @keyframes slideIn {
      from { opacity: 0; transform: translateX(20px); }
      to { opacity: 1; transform: translateX(0); }
    }
    .animate-slideIn {
      animation: slideIn 0.3s ease-out forwards;
    }
    .animate-slideUp {
        animation: fadeIn 0.4s ease-out forwards;
    }
  `}</style>
</div>


);
}