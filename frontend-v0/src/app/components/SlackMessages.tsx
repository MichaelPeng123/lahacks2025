'use client';

import { useState, useEffect, useRef } from 'react';
import { fetchSlackEntities } from '../utils/api';

interface SlackMessage {
  id: string;
  slackId: string;
  channelId: string;
  text: string;
  threadTs: string | null;
  createdAt: string;
}

export default function SlackMessages() {
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<SlackMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  // Default refresh interval is 30 seconds
  const [refreshInterval, setRefreshInterval] = useState(30);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchMessages = async () => {
    try {
      const response = await fetchSlackEntities();
      if (response.status === 'success' && response.data && response.data.messages) {
        setMessages(response.data.messages);
        setLastUpdated(new Date());
      } else {
        setError('Invalid response format');
      }
    } catch (err) {
      setError('Failed to fetch messages');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Start periodic refresh
  useEffect(() => {
    // Initial fetch
    fetchMessages();

    // Set up periodic refresh
    timerRef.current = setInterval(() => {
      fetchMessages();
    }, refreshInterval * 1000);

    // Cleanup on unmount
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [refreshInterval]);

  // Function to manually refresh
  const handleRefresh = () => {
    setLoading(true);
    fetchMessages();
  };

  // Function to change refresh interval
  const handleIntervalChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newInterval = parseInt(e.target.value, 10);
    setRefreshInterval(newInterval);
    
    // Reset the timer with new interval
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    
    timerRef.current = setInterval(() => {
      fetchMessages();
    }, newInterval * 1000);
  };

  if (loading && !messages.length) return <div className="text-center p-4">Loading messages...</div>;
  if (error) return <div className="text-red-500 p-4">{error}</div>;
  if (messages.length === 0) return <div className="text-center p-4">No messages found</div>;

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-gray-500">Slack Messages</h2>
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-500">
            {lastUpdated && (
              <span>Last updated: {lastUpdated.toLocaleTimeString()}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="refresh-interval" className="text-sm text-gray-500">
              Refresh every:
            </label>
            <select 
              id="refresh-interval" 
              value={refreshInterval} 
              onChange={handleIntervalChange}
              className="text-sm border border-gray-300 rounded p-1 text-gray-600"
            >
              <option value="10">10 seconds</option>
              <option value="30">30 seconds</option>
              <option value="60">1 minute</option>
              <option value="300">5 minutes</option>
            </select>
          </div>
          <button 
            onClick={handleRefresh} 
            className="text-sm bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded transition-colors rounded-md"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </div>
      </div>
      
      <div className="space-y-4">
        {messages.map((message) => (
          <div key={message.id} className="border-b pb-2 text-gray-500">
            <div className="flex justify-between">
              <span className="font-semibold text-gray-500">{message.slackId}</span>
              <span className="text-sm text-gray-500">
                {new Date(message.createdAt).toLocaleString()}
              </span>
            </div>
            <p className="mt-1">{message.text}</p>
            {message.threadTs && (
              <div className="mt-1 text-sm text-blue-500">
                Thread: {message.threadTs}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
} 