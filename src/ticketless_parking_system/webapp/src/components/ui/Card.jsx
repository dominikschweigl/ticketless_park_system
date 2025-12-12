import React from 'react';

export const Card = ({ title, children, className = "", footer }) => (
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