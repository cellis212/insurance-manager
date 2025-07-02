'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/auth-store';
import { gameApi } from '@/lib/api-services';
import { ErrorBoundary } from '@/components/error-boundary';
import { 
  HomeIcon, 
  BuildingOfficeIcon, 
  MapIcon, 
  CubeIcon, 
  BanknotesIcon, 
  UserGroupIcon,
  ClipboardDocumentListIcon,
  ArrowRightOnRectangleIcon
} from '@heroicons/react/24/outline';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Company', href: '/dashboard/company', icon: BuildingOfficeIcon },
  { name: 'Expansion', href: '/dashboard/expansion', icon: MapIcon },
  { name: 'Products', href: '/dashboard/products', icon: CubeIcon },
  { name: 'Investments', href: '/dashboard/investments', icon: BanknotesIcon },
  { name: 'Employees', href: '/dashboard/employees', icon: UserGroupIcon },
  { name: 'Decisions', href: '/dashboard/decisions', icon: ClipboardDocumentListIcon },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, logout, user } = useAuthStore();
  const [hasCheckedCompany, setHasCheckedCompany] = useState(false);

  // Check if user has a company
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['dashboard-check'],
    queryFn: gameApi.getDashboard,
    enabled: isAuthenticated(),
    retry: false,
  });

  useEffect(() => {
    // Redirect to login if not authenticated
    if (!isAuthenticated()) {
      router.push('/auth/login');
      return;
    }

    // If we've loaded and there's an error (no company), redirect to company creation
    if (!isLoading && !dashboard && isAuthenticated()) {
      router.push('/company/create');
      return;
    }

    // Mark that we've checked for company
    if (!isLoading && dashboard) {
      setHasCheckedCompany(true);
    }
  }, [isAuthenticated, isLoading, dashboard, router]);

  const handleLogout = () => {
    logout();
    router.push('/auth/login');
  };

  // Don't render anything while checking authentication or company status
  if (!isAuthenticated() || isLoading || !hasCheckedCompany) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-gray-900">Loading...</h1>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="flex h-screen">
        {/* Sidebar */}
        <div className="flex flex-col w-64 bg-white border-r border-gray-200">
          <div className="flex-1 flex flex-col pt-5 pb-4 overflow-y-auto">
            <div className="flex items-center flex-shrink-0 px-4">
              <h1 className="text-xl font-semibold text-gray-900">Insurance Manager</h1>
            </div>
            <nav className="mt-8 flex-1 px-2 space-y-1">
              {navigation.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`
                      group flex items-center px-2 py-2 text-sm font-medium rounded-md
                      ${isActive
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }
                    `}
                  >
                    <item.icon
                      className={`
                        mr-3 flex-shrink-0 h-6 w-6
                        ${isActive
                          ? 'text-indigo-700'
                          : 'text-gray-400 group-hover:text-gray-500'
                        }
                      `}
                      aria-hidden="true"
                    />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex-shrink-0 flex border-t border-gray-200 p-4">
            <div className="flex items-center justify-between w-full">
              <div className="flex-shrink-0 group block">
                <div className="flex items-center">
                  <div>
                    <p className="text-sm font-medium text-gray-700 group-hover:text-gray-900">
                      {user?.email}
                    </p>
                  </div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="flex-shrink-0 p-1 text-gray-400 rounded-full hover:bg-gray-100 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-y-auto">
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
} 