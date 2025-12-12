import React from 'react';

export const Footer = () => {
  return (
    <footer className="bg-white border-t border-slate-200 mt-auto">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center">
          <div className="mb-4 md:mb-0">
            <p className="text-center md:text-left text-sm text-slate-500">
              &copy; 2025 SmartPark Distributed Systems. All rights reserved.
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Powered by Edge Computing & Akka Cloud Actors
            </p>
          </div>
          <div className="flex space-x-6 text-slate-400">
            <span className="text-sm">Adzic Nikola</span>
            <span className="text-sm">Dominik Schweigel</span>
            <span className="text-sm">Daniel Wenger</span>
          </div>
        </div>
      </div>
    </footer>
  );
};