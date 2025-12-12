import React from 'react';

export const Button = ({ children, onClick, disabled, loading, variant = "primary", className = "" }) => {
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