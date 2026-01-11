import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, RefreshCw, Activity } from 'lucide-react';
import MapVisualizer from './components/MapVisualizer';
import ChatInterface from './components/ChatInterface';

// Configure Axios
axios.defaults.baseURL = 'http://localhost:8000';

const App = () => {
  const [boats, setBoats] = useState([]);
  const [stats, setStats] = useState({ total: 0, online: 0, error: 0 });
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);

  // Track previous playing state to detect completion
  const prevPlayingRef = React.useRef(false);

  // Fetch Map Data
  const fetchMapData = async () => {
    try {
      const res = await axios.get('/map-data');

      // Handle new response format
      const boatData = res.data.boats || [];
      const active = res.data.is_active || false;

      setBoats(boatData);
      setIsPlaying(active);
      if (res.data.speed) setPlaybackSpeed(res.data.speed);

      // Detect simulation end (True -> False transition)
      if (prevPlayingRef.current && !active) {
        // Dispatch custom event for ChatInterface to pick up
        window.dispatchEvent(new CustomEvent('swarm-simulation-end'));
      }
      prevPlayingRef.current = active;

      // Calculate Stats
      const errs = boatData.filter(b => b.status === 'ERROR').length;
      setStats({
        total: boatData.length,
        online: boatData.length - errs,
        error: errs
      });
    } catch (err) {
      console.error("Failed to fetch map data:", err);
    }
  };

  useEffect(() => {
    fetchMapData();
    const interval = setInterval(fetchMapData, 500); // Poll every 500ms
    return () => clearInterval(interval);
  }, []);

  // File Upload Handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    console.log("Drag event:", e.type);
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    console.log("File dropped!");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      console.log("Found file:", e.dataTransfer.files[0].name);
      handleUpload(e.dataTransfer.files[0]);
    } else {
      console.log("No files found in drop event.");
    }
  };

  const handleUpload = async (file) => {
    console.log("Starting upload for:", file.name);
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post('/upload', formData);
      // alert("Logs ingested successfully!"); // Alert interrupts flow, removing it
      fetchMapData();
    } catch (err) {
      alert("Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      className="h-screen w-full flex flex-col p-6 gap-6 relative"
      onDragEnter={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      {/* Upload Drag Overlay */}
      {(dragActive || uploading) && (
        <div
          className="absolute inset-0 z-50 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center border-4 border-dashed border-cyan-500 rounded-xl m-4"
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="text-center animate-bounce">
            <Upload className="w-16 h-16 mx-auto text-cyan-400 mb-4" />
            <h2 className="text-2xl font-bold text-white">
              {uploading ? "Ingesting Logs..." : "Drop .bag or .jsonl Log File"}
            </h2>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex justify-between items-center glass-panel p-4 rounded-xl">
        <div className="flex items-center gap-3">
          <Activity className="text-cyan-400" />
          <h1 className="text-xl font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-fuchsia-500">
            SWARM INTELLIGENCE ASSISTANT
          </h1>
        </div>

        {/* Stats Row */}
        <div className="flex gap-6 text-sm">
          <div className="flex flex-col items-center">
            <span className="text-slate-400 text-xs">UNITS</span>
            <span className="font-mono text-xl font-bold text-white">{stats.total}</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-slate-400 text-xs text-green-400">ONLINE</span>
            <span className="font-mono text-xl font-bold text-green-400">{stats.online}</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-slate-400 text-xs text-red-400">ERRORS</span>
            <span className="font-mono text-xl font-bold text-red-500 animate-pulse">{stats.error}</span>
          </div>
          <button onClick={fetchMapData} className="p-2 hover:bg-slate-700 rounded-full transition-colors">
            <RefreshCw size={18} className="text-slate-400" />
          </button>

          {/* Live Sim Controls */}
          <button
            onClick={async () => {
              try {
                if (isPlaying) {
                  await axios.post('/simulation/stop');
                } else {
                  await axios.post('/simulation/start');
                }
                fetchMapData();
              } catch (e) {
                console.error(e);
                alert("Operation failed");
              }
            }}
            className={`flex items-center gap-2 p-2 px-4 rounded-lg cursor-pointer transition-colors font-semibold text-white
              ${isPlaying ? 'bg-red-600 hover:bg-red-500' : 'bg-green-600 hover:bg-green-500'}`}
          >
            <Activity size={18} />
            <span>{isPlaying ? "Stop Sim" : "Start Live Sim"}</span>
          </button>

          <label className="flex items-center gap-2 p-2 px-4 bg-cyan-600 hover:bg-cyan-500 rounded-lg cursor-pointer transition-colors text-white font-semibold">
            <Upload size={18} />
            <span>Upload Logs</span>
            <input
              type="file"
              className="hidden"
              accept=".jsonl,.bag"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  console.log("Manual file select:", e.target.files[0].name);
                  handleUpload(e.target.files[0]);
                }
              }}
            />
          </label>
        </div>
      </header>

      {/* Playback Controls */}
      {isPlaying && (
        <div className="flex justify-center -mt-4 mb-2 z-10 relative">
          <div className="glass-panel px-4 py-2 rounded-full flex gap-2 items-center">
            <span className="text-xs text-slate-400 font-mono">PLAYBACK SPEED:</span>
            {[1, 2, 5, 10].map(s => (
              <button
                key={s}
                onClick={async () => {
                  try {
                    setPlaybackSpeed(s);
                    axios.post('/playback/speed', { speed: s });
                  } catch (e) { console.error(e); }
                }}
                className={`text-xs px-2 py-1 rounded font-bold transition-all ${playbackSpeed === s ? 'bg-cyan-500 text-white shadow-lg shadow-cyan-500/50' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Grid */}
      <main className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 min-h-0">
        {/* Left: Map */}
        <section className="flex flex-col h-full min-h-0">
          <div className="flex-1 relative">
            <MapVisualizer boats={boats} isPlaying={isPlaying} />
          </div>
        </section>

        {/* Right: Chat */}
        <section className="flex flex-col h-full min-h-0">
          <ChatInterface />
        </section>
      </main>
    </div>
  );
};

export default App;
