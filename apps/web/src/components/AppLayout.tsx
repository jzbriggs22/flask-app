import { Outlet, Link, useLocation } from "react-router-dom";
import { FolderOpen, Settings, Building2 } from "lucide-react";

const navItems = [
  { path: "/projects", label: "Projects", icon: FolderOpen },
  { path: "/admin", label: "Settings", icon: Settings },
];

export function AppLayout() {
  const location = useLocation();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-16 flex-col items-center border-r border-gray-200 bg-white py-4">
        <Link to="/" className="mb-8 flex items-center justify-center">
          <Building2 className="h-8 w-8 text-brand-600" />
        </Link>
        <nav className="flex flex-1 flex-col items-center gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-600"
                    : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                }`}
                title={item.label}
              >
                <Icon className="h-5 w-5" />
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

/** Breadcrumb bar shown on inner pages */
export function PageHeader({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <h1 className="text-lg font-semibold">{title}</h1>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </header>
  );
}
