import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Navigation, AlertTriangle } from 'lucide-react';

const MapVisualizer = ({ boats, isPlaying }) => {
    // 1. Calculate Bounding Box
    const bounds = useMemo(() => {
        if (!boats.length) return { minLat: 0, maxLat: 1, minLon: 0, maxLon: 1 };

        let minLat = Infinity, maxLat = -Infinity;
        let minLon = Infinity, maxLon = -Infinity;

        boats.forEach(b => {
            minLat = Math.min(minLat, b.lat);
            maxLat = Math.max(maxLat, b.lat);
            minLon = Math.min(minLon, b.lon);
            maxLon = Math.max(maxLon, b.lon);
        });

        // Add padding
        const latSpan = maxLat - minLat || 0.1;
        const lonSpan = maxLon - minLon || 0.1;
        const padding = 0.1; // 10% padding

        return {
            minLat: minLat - latSpan * padding,
            maxLat: maxLat + latSpan * padding,
            minLon: minLon - lonSpan * padding,
            maxLon: maxLon + lonSpan * padding
        };
    }, [boats]);

    // Helper to normalize coordinates to 0-100%
    const getPos = (lat, lon) => {
        const y = ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * 100; // Lat increases upwards, screen y downwards
        const x = ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * 100;
        return { x: `${x}%`, y: `${y}%` };
    };

    return (
        <div className="relative w-full h-full bg-slate-900 overflow-hidden rounded-xl border border-slate-700 shadow-2xl">
            {/* Grid Lines */}
            <div className="absolute inset-0 opacity-20 pointer-events-none"
                style={{ backgroundImage: 'linear-gradient(#334155 1px, transparent 1px), linear-gradient(90deg, #334155 1px, transparent 1px)', backgroundSize: '40px 40px' }}>
            </div>

            {/* Map Content */}
            <div className="relative w-full h-full">
                {boats.map((boat) => {
                    const { x, y } = getPos(boat.lat, boat.lon);
                    const isError = boat.status === 'ERROR';

                    return (
                        <motion.div
                            key={boat.boat_id}
                            className="absolute w-8 h-8 -ml-4 -mt-4 flex items-center justify-center"
                            initial={{ left: x, top: y }}
                            animate={{ left: x, top: y }}
                            transition={{ duration: 1, ease: "linear" }}
                        >
                            <div className="relative group cursor-pointer">
                                {/* Status Indicator Ring */}
                                <div className={`absolute inset-0 rounded-full opacity-30 blur-sm 
                  ${isError ? 'bg-red-500 animate-pulse' : 'bg-cyan-500'} 
                  ${(isPlaying && boat.status === 'MOVING') ? 'animate-ping' : ''}`}
                                />

                                {/* Icon */}
                                <div className={`relative z-10 p-1 rounded-full shadow-lg border border-white/20 
                  ${isError ? 'bg-red-600 text-white' : 'bg-slate-800 text-cyan-400'}`}>
                                    {isError ? <AlertTriangle size={16} /> :
                                        <Navigation size={16} style={{ transform: `rotate(${boat.course_deg}deg)` }} />}
                                </div>

                                {/* Tooltip on Hover */}
                                <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-max max-w-xs p-2 rounded bg-slate-800 border border-slate-600 shadow-xl opacity-0 group-hover:opacity-100 transition-opacity z-20 text-xs text-slate-200 pointer-events-none">
                                    <p className="font-bold text-white">Unit {boat.boat_id}</p>
                                    <p>Status: <span className={isError ? 'text-red-400' : 'text-green-400'}>{boat.status}</span></p>
                                    <p>Bat: {boat.battery}%</p>
                                    {isError && <p className="text-red-300 mt-1">{boat.error_details}</p>}
                                </div>
                            </div>
                        </motion.div>
                    );
                })}
            </div>

            {/* Overlay Info */}
            <div className="absolute top-4 left-4 glass-panel px-3 py-1 rounded text-xs text-slate-400 font-mono">
                Sector: TAIWAN STRAIT<br />
                Lat: {bounds.minLat.toFixed(2)} - {bounds.maxLat.toFixed(2)}<br />
                Lon: {bounds.minLon.toFixed(2)} - {bounds.maxLon.toFixed(2)}
            </div>
        </div>
    );
};

export default MapVisualizer;
