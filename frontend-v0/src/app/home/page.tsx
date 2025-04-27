import Chatbot from '../components/Chatbot';

export default function Home() {
  return (
    <div className="min-h-screen p-8">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold">DevAtlas Assistant</h1>
        <p className="text-gray-600">Ask me anything about your project</p>
      </header>
      
      <main>
        <Chatbot />
      </main>
    </div>
  );
} 