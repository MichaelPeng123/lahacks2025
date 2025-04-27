'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Chatbot from './components/Chatbot';

export default function HomePage() {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/home');
  }, [router]);
  
  return null; // No UI rendered as we're redirecting
}
