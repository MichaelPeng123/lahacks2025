import SlackMessages from '../components/SlackMessages';

export default function SlacksPage() {
  return (
    <div className="py-8 px-4">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">Slack Monitoring Dashboard</h1>
        <p className="text-white">View and monitor Slack messages from your channels</p>
      </header>
      
      <main>
        <SlackMessages />
      </main>
    </div>
  );
} 