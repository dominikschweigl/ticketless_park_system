import React, { useState } from 'react';
import { Car, Menu, X } from 'lucide-react';

export const Navbar = ({ activeTab, setActiveTab }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0 flex items-center gap-2">
              <div className="bg-blue-600 p-1.5 rounded-lg">
                <Car className="h-6 w-6 text-white" />
              </div>
              <span className="font-bold text-xl tracking-tight text-slate-800">Smart<span className="text-blue-600">Park</span></span>
            </div>
            
            {/* Desktop Nav */}
            <div className="hidden sm:ml-10 sm:flex sm:space-x-8">
              <button 
                onClick={() => setActiveTab('pay')}
                className={`${activeTab === 'pay' ? 'border-blue-500 text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'} inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium h-16 transition-colors`}
              >
                Payments
              </button>
              <button 
                onClick={() => setActiveTab('book')}
                className={`${activeTab === 'book' ? 'border-blue-500 text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'} inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium h-16 transition-colors`}
              >
                Find & Book
              </button>
            </div>
          </div>

          <div className="flex items-center sm:hidden">
            <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="p-2 rounded-md text-slate-400 hover:text-slate-500 hover:bg-slate-100">
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="sm:hidden bg-white border-b border-slate-200">
          <div className="pt-2 pb-3 space-y-1">
            <button 
              onClick={() => { setActiveTab('pay'); setMobileMenuOpen(false); }}
              className={`${activeTab === 'pay' ? 'bg-blue-50 border-blue-500 text-blue-700' : 'border-transparent text-slate-500 hover:bg-slate-50 hover:border-slate-300'} block pl-3 pr-4 py-2 border-l-4 text-base font-medium w-full text-left`}
            >
              Payments
            </button>
            <button 
              onClick={() => { setActiveTab('book'); setMobileMenuOpen(false); }}
              className={`${activeTab === 'book' ? 'bg-blue-50 border-blue-500 text-blue-700' : 'border-transparent text-slate-500 hover:bg-slate-50 hover:border-slate-300'} block pl-3 pr-4 py-2 border-l-4 text-base font-medium w-full text-left`}
            >
              Find & Book
            </button>
          </div>
        </div>
      )}
    </nav>
  );
};