import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User } from 'lucide-react';
import axios from 'axios';

const ChatInterface = () => {
    const [messages, setMessages] = useState([
        { role: 'assistant', content: 'Operator, Swarm Intelligence is online. Logs are synchronized. Ready for queries.' }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    useEffect(() => {
        const handleEnd = () => {
            setMessages(prev => [...prev, { role: 'assistant', content: 'Simulation playback completed. All units holding final positions.' }]);
        };
        window.addEventListener('swarm-simulation-end', handleEnd);
        return () => window.removeEventListener('swarm-simulation-end', handleEnd);
    }, []);

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            // API Call
            const res = await axios.post('http://localhost:8000/query', { query: userMsg.content });
            setMessages(prev => [...prev, { role: 'assistant', content: res.data.answer }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Comms link failure. Check backend connection.' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full glass-panel rounded-xl overflow-hidden shadow-2xl border border-slate-700">
            {/* Header */}
            <div className="bg-slate-800/50 p-4 border-b border-slate-700 flex items-center gap-2">
                <Bot className="text-cyan-400" />
                <h2 className="font-semibold text-slate-100">Swarm Comms</h2>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] p-3 rounded-xl text-sm leading-relaxed 
              ${msg.role === 'user'
                                ? 'bg-cyan-600/20 border border-cyan-500/30 text-cyan-50 rounded-br-none'
                                : 'bg-slate-700/50 border border-slate-600 text-slate-200 rounded-bl-none'}`}>
                            {msg.content}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-slate-700/50 p-3 rounded-xl rounded-bl-none text-slate-400 text-xs italic animate-pulse">
                            Analyzing logs...
                        </div>
                    </div>
                )}
                <div ref={scrollRef} />
            </div>

            {/* Input */}
            <div className="p-4 bg-slate-800/30 border-t border-slate-700">
                <div className="flex gap-2">
                    <input
                        type="text"
                        className="flex-1 bg-slate-900/50 border border-slate-600 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
                        placeholder="Ask about swarm health, errors, or positions..."
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleSend()}
                    />
                    <button
                        onClick={handleSend}
                        disabled={loading}
                        className="bg-cyan-600 hover:bg-cyan-500 text-white p-2 rounded-lg transition-colors disabled:opacity-50"
                    >
                        <Send size={18} />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ChatInterface;
