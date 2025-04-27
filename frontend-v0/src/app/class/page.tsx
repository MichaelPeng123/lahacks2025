'use client';

import { useState } from 'react';
import Link from 'next/link';

// Mock data for classes
const mockClasses = [
  {
    id: 1,
    code: 'CS101',
    title: 'Introduction to Computer Science',
    instructor: 'Dr. Jane Bob',
    schedule: 'Mon, Wed, Fri 10:00 AM - 11:30 AM',
    status: 'In Progress',
  },
  {
    id: 2,
    code: 'MATH202',
    title: 'Linear Algebra',
    instructor: 'Dr. Michael Johnson',
    schedule: 'Tue, Thu 2:00 PM - 3:30 PM',
    status: 'In Progress',
  },
  {
    id: 3,
    code: 'PHYS101',
    title: 'Introduction to Physics',
    instructor: 'Dr. Robert Chen',
    schedule: 'Mon, Wed 1:00 PM - 2:30 PM',
    status: 'In Progress',
  },
  {
    id: 4,
    code: 'ENG205',
    title: 'Technical Writing',
    instructor: 'Prof. Sarah Wilson',
    schedule: 'Fri 9:00 AM - 12:00 PM',
    status: 'In Progress',
  },
];

export default function ClassListing() {
  const [classes] = useState(mockClasses);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-900">My Classes</h1>
            <Link href="/" className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700">
              Back to Home
            </Link>
          </div>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {classes.map((classItem) => (
              <li key={classItem.id}>
                <Link 
                  href="/class/dashboard" 
                  className="block hover:bg-gray-50"
                >
                  <div className="px-6 py-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-xl font-medium text-blue-600">{classItem.title}</div>
                        <div className="text-sm text-gray-500 mt-1">{classItem.code}</div>
                      </div>
                      <div className="flex-shrink-0">
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
                          {classItem.status}
                        </span>
                      </div>
                    </div>
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium text-gray-500">Instructor</p>
                        <p className="mt-1 text-sm text-gray-900">{classItem.instructor}</p>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-500">Schedule</p>
                        <p className="mt-1 text-sm text-gray-900">{classItem.schedule}</p>
                      </div>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
} 