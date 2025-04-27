'use client';

import { useState, useEffect } from 'react';

interface GitCommit {
  id: string;
  message: string;
  author: string;
  date: string;
}

export default function GitHistory() {
  const [commits, setCommits] = useState<GitCommit[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // This would be replaced with an actual API call in production
    const fetchGitHistory = async () => {
      try {
        setLoading(true);
        // Mock data for demonstration purposes
        // In a real app, you would fetch this from a backend API
        const mockCommits: GitCommit[] = [
          {
            id: 'abc1234',
            message: 'Add new navbar component',
            author: 'Jane Doe',
            date: '2023-04-15T10:30:00Z',
          },
          {
            id: 'def5678',
            message: 'Fix styling issues in the dashboard',
            author: 'John Smith',
            date: '2023-04-14T09:15:00Z',
          },
          {
            id: 'ghi9012',
            message: 'Implement user authentication',
            author: 'Jane Doe',
            date: '2023-04-13T14:20:00Z',
          },
          {
            id: 'jkl3456',
            message: 'Initial commit',
            author: 'John Smith',
            date: '2023-04-12T08:45:00Z',
          },
        ];
        
        setCommits(mockCommits);
      } catch (error) {
        console.error('Error fetching git history:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchGitHistory();
  }, []);

  // Format date to a more readable format
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="bg-gray-900 rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4 text-white">Git Commit History</h2>
      
      {loading ? (
        <div className="text-center py-8">
          <p className="text-gray-400">Loading commit history...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {commits.map((commit) => (
            <div key={commit.id} className="border border-gray-800 rounded-md p-4 bg-gray-800">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-medium text-blue-400 truncate">{commit.message}</h3>
                <span className="text-xs text-gray-500 whitespace-nowrap ml-2">{commit.id.substring(0, 7)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">{commit.author}</span>
                <span className="text-gray-500">{formatDate(commit.date)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
} 