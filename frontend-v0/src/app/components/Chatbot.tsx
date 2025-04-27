'use client';

import { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot';
  timestamp: Date;
}

export default function Chatbot() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Hello! I\'m your DevAtlas assistant. How can I help you today?',
      sender: 'bot',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messageEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!inputValue.trim()) return;
    
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: 'user',
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    
    // Simulate bot response (would be replaced with actual API call)
    setTimeout(() => {
      const botResponses = [
        "I'm working on implementing that feature for you.",
        "Let me check the documentation for that.",
        "That's an interesting question about the project.",
        "I can help you analyze that part of the codebase.",
        "Would you like me to show you the recent commits related to that?",
      ];
      
      const randomResponse = botResponses[Math.floor(Math.random() * botResponses.length)];
      
      const botMessage: Message = {
        id: Date.now().toString(),
        content: randomResponse,
        sender: 'bot',
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, botMessage]);
      setIsLoading(false);
    }, 1000);
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="flex flex-col h-[80vh] max-w-2xl mx-auto bg-gray-900 rounded-lg shadow-lg overflow-hidden">
      <div className="p-4 bg-gray-800 text-white">
        <h2 className="text-xl font-bold">DevAtlas Assistant</h2>
      </div>
      
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-4">
          {messages.map((message) => (
            <div 
              key={message.id} 
              className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div 
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.sender === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-800 text-gray-200'
                }`}
              >
                <p>{message.content}</p>
                <div className={`text-xs mt-1 ${
                  message.sender === 'user' ? 'text-blue-200' : 'text-gray-500'
                }`}>
                  {formatTime(message.timestamp)}
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 text-white rounded-lg p-3">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse"></div>
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse delay-100"></div>
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse delay-200"></div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messageEndRef} />
        </div>
      </div>
      
      <form onSubmit={handleSendMessage} className="p-4 bg-gray-800 border-t border-gray-700">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 bg-gray-700 text-white rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-2 w-10 h-10 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
} 