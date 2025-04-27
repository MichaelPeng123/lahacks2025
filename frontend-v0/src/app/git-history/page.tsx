import GitHistory from '../components/GitHistory';

export default function GitHistoryPage() {
  return (
    <div className="py-8 px-4">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">Git Commit History</h1>
        <p className="text-white">Track and monitor git commits for your project</p>
      </header>
      
      <main>
        <GitHistory />
      </main>
    </div>
  );
} 