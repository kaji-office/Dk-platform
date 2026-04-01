import React from 'react';

const StatsCard = ({ title, value, icon, trend, trendValue }) => {
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-500 mb-1">{title}</p>
          <h3 className="text-3xl font-bold text-neutral-900">{value}</h3>
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-sm font-medium ${trend === 'up' ? 'text-green-600' : 'text-red-600'}`}>
              <span>{trend === 'up' ? '+' : '-'}{trendValue}%</span>
              <span className="text-neutral-400 font-normal ml-1">vs last month</span>
            </div>
          )}
        </div>
        <div className="p-3 bg-primary-50 text-primary-600 rounded-xl">
          {icon}
        </div>
      </div>
    </div>
  );
};

export default StatsCard;
