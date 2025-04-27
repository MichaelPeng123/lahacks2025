import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Slack API endpoints
export const fetchMonitoredChannels = async () => {
  const response = await api.get('/slack/monitored-channels');
  return response.data;
};

export const fetchChannelHistory = async (channelId: string, limit = 100) => {
  const response = await api.get(`/slack/monitor/history/${channelId}?limit=${limit}`);
  return response.data;
};

export const fetchSlackEntities = async () => {
  const response = await api.get('/slack/entities');
  return response.data;
};

export const addChannelToMonitor = async (channel: string) => {
  const response = await api.post(`/slack/monitor/${channel}`);
  return response.data;
};

export const fetchThreadReplies = async (channelId: string, threadTs: string) => {
  const response = await api.get(`/slack/thread/${channelId}/${threadTs}`);
  return response.data;
};

export default api; 